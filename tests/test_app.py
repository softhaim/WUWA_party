import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ResonanceLabTests(unittest.TestCase):
    def test_static_bundle_supports_direct_file_open(self):
        index = (server.STATIC / "index.html").read_text(encoding="utf-8")
        app = (server.STATIC / "app.js").read_text(encoding="utf-8")
        self.assertIn('href="./styles.css"', index)
        self.assertIn('src="./app.js?', index)
        self.assertIn('location.protocol === "file:"', app)
        self.assertIn("http://127.0.0.1:8000", app)
        self.assertIn("imageUrl(m.image)", app)

    def test_catalog_is_valid_and_unique(self):
        characters = server.load_characters()
        self.assertEqual(len(characters), 55)
        self.assertEqual(len({c["id"] for c in characters}), 55)
        self.assertTrue(all(c["image"].startswith("/api/image/") for c in characters))
        self.assertTrue(all(c["image_source"].startswith("https://") for c in characters))

    def test_xuanling_is_distinct_from_base_yangyang(self):
        characters = {character["id"]: character for character in server.load_characters()}
        self.assertEqual(characters["yangyang"]["element_ko"], "기류")
        self.assertEqual(characters["yangyang-xuanling"]["element_ko"], "인멸")
        self.assertTrue(characters["yangyang-xuanling"]["preview"])

    def test_dynamic_score_rewards_complete_latest_bis(self):
        ids = ("hiyuki", "lucilla", "chisa")
        complete = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "sequence": 6, "signature_weapon": True}
            for cid in ids
        }
        unfinished = {
            cid: {"owned": True, "level": 80, "build_status": "육성 중", "max_uses": 1, "sequence": 0, "signature_weapon": False}
            for cid in ids
        }
        complete_team = server.recommend({"roster": complete, "team_count": 1})["teams"][0]
        unfinished_team = server.recommend({"roster": unfinished, "team_count": 1})["teams"][0]
        self.assertEqual(complete_team["score"], 100)
        self.assertGreater(complete_team["score"], unfinished_team["score"])
        self.assertEqual(set(complete_team["score_details"]), {"composition", "meta", "investment", "build"})

    def test_sequence_and_weapon_change_visible_team_score(self):
        ids = ("hiyuki", "lucilla", "chisa")
        base = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "sequence": 0, "signature_weapon": False}
            for cid in ids
        }
        invested = {cid: dict(state) for cid, state in base.items()}
        invested["hiyuki"].update({"sequence": 2, "signature_weapon": True})
        base_team = server.recommend({"roster": base, "team_count": 1})["teams"][0]
        invested_team = server.recommend({"roster": invested, "team_count": 1})["teams"][0]
        self.assertGreater(invested_team["score"], base_team["score"])
        self.assertGreater(
            invested_team["score_details"]["investment"],
            base_team["score_details"]["investment"],
        )

    def test_complete_high_sequence_older_team_can_beat_unfinished_latest_team(self):
        old_roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "sequence": 6, "signature_weapon": True}
            for cid in ("camellya", "roccia", "shorekeeper")
        }
        latest_roster = {
            cid: {"owned": True, "level": 80, "build_status": "육성 중", "max_uses": 1, "sequence": 0, "signature_weapon": False}
            for cid in ("hiyuki", "lucilla", "chisa")
        }
        old_score = server.recommend({"roster": old_roster, "team_count": 1})["teams"][0]["score"]
        latest_score = server.recommend({"roster": latest_roster, "team_count": 1})["teams"][0]["score"]
        self.assertGreater(old_score, latest_score)

    def test_xuanling_suisui_chisa_preview_core_is_recommended(self):
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ("yangyang-xuanling", "suisui", "chisa")}
        team = server.recommend({"roster": roster, "team_count": 1})["teams"][0]
        self.assertEqual({member["id"] for member in team["members"]}, set(roster))
        self.assertEqual(team["confidence"], "프리뷰")
        self.assertIn("출시 전", team["reason"])

    def test_suisui_unlocks_hiyuki_lucilla_preview_team(self):
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ("hiyuki", "lucilla", "suisui")}
        team = server.recommend({"roster": roster, "team_count": 1})["teams"][0]
        self.assertEqual({member["id"] for member in team["members"]}, set(roster))
        self.assertEqual(team["confidence"], "프리뷰")

    def test_no_suisui_preserves_current_hiyuki_core(self):
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ("hiyuki", "lucilla", "chisa")}
        team = server.recommend({"roster": roster, "team_count": 1})["teams"][0]
        self.assertEqual({member["id"] for member in team["members"]}, set(roster))
        self.assertEqual(team["confidence"], "높음")

    def test_single_suisui_goes_to_xuanling_when_hiyuki_has_current_core(self):
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ("yangyang-xuanling", "suisui", "chisa", "hiyuki", "lucilla", "shorekeeper")}
        roster["chisa"]["max_uses"] = 2
        teams = [{member["id"] for member in team["members"]} for team in server.recommend({"roster": roster, "team_count": 2})["teams"]]
        self.assertIn({"yangyang-xuanling", "suisui", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "chisa"}, teams)

    def test_two_suisui_uses_complete_xuanling_and_hiyuki_while_chisa_flexes(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "yangyang-xuanling", "suisui", "chisa",
                "hiyuki", "lucilla",
                "aemeath", "denia", "mornye",
            )
        }
        roster["suisui"]["max_uses"] = 2
        roster["chisa"]["max_uses"] = 2
        teams = [
            {member["id"] for member in team["members"]}
            for team in server.recommend({"roster": roster, "team_count": 3})["teams"]
        ]
        self.assertIn({"yangyang-xuanling", "suisui", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "suisui"}, teams)
        self.assertIn({"aemeath", "denia", "chisa"}, teams)

    def test_hiyuki_uses_suisui_so_chisa_can_complete_aemeath_core(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("hiyuki", "lucilla", "suisui", "aemeath", "denia", "chisa")
        }
        teams = [
            {member["id"] for member in team["members"]}
            for team in server.recommend({"roster": roster, "team_count": 2})["teams"]
        ]
        self.assertIn({"hiyuki", "lucilla", "suisui"}, teams)
        self.assertIn({"aemeath", "denia", "chisa"}, teams)

    def test_saved_roster_boundary_prefers_xuanling_and_suisui_in_primary_allocation(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "yangyang-xuanling", "suisui", "chisa",
                "hiyuki", "lucilla", "aemeath", "denia",
                "phrolova", "cantarella", "qiuyuan",
            )
        }
        roster["suisui"]["max_uses"] = 2
        roster["chisa"]["max_uses"] = 2
        roster["aemeath"].update({"sequence": 3, "signature_weapon": True})
        roster["hiyuki"].update({"sequence": 2, "signature_weapon": True})
        teams = [
            {member["id"] for member in team["members"]}
            for team in server.recommend({"roster": roster, "team_count": 3})["teams"]
        ]
        self.assertIn({"yangyang-xuanling", "suisui", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "suisui"}, teams)
        self.assertIn({"aemeath", "denia", "chisa"}, teams)

    def test_recommendation_uses_owned_characters(self):
        roster = {
            "camellya": {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "preference": "필수"},
            "sanhua": {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "preference": "보통"},
            "shorekeeper": {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1, "preference": "보통"},
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(len(result["teams"]), 1)
        ids = {m["id"] for m in result["teams"][0]["members"]}
        self.assertEqual(ids, set(roster))
        self.assertIn("카멜리아 일반 공격", result["teams"][0]["reason"])
        self.assertEqual(result["teams"][0]["confidence"], "높음")

    def test_hiyuki_meta_team_is_recognized_without_role_slots(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("hiyuki", "lucilla", "chisa")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual({m["id"] for m in result["teams"][0]["members"]}, set(roster))
        self.assertIn("최고점", result["teams"][0]["reason"])

    def test_s2_hiyuki_gets_premium_support_when_chisa_is_consumed(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "aemeath", "denia", "chisa",
                "hiyuki", "lucilla", "shorekeeper",
                "phrolova", "cantarella", "verina",
            )
        }
        roster["hiyuki"].update({"sequence": 2, "signature_weapon": True})
        result = server.recommend({"roster": roster, "team_count": 3})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"aemeath", "denia", "chisa"}, teams)
        self.assertTrue(any(
            {"hiyuki", "lucilla"} < team and team & {"shorekeeper", "verina", "mornye"}
            for team in teams
        ))
        self.assertTrue(any(
            {"phrolova", "cantarella"} < team and team & {"shorekeeper", "verina"}
            for team in teams
        ))
        self.assertFalse(any({"hiyuki", "lucilla", "baizhi"} <= team for team in teams))

    def test_liberation_fallback_uses_iuno_with_lynae_mornye(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("iuno", "lynae", "mornye")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual({m["id"] for m in result["teams"][0]["members"]}, set(roster))
        self.assertIn("조화도 파괴", result["teams"][0]["reason"])

    def test_augusta_ownership_promotes_augusta_iuno_bis(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("augusta", "iuno", "shorekeeper", "lynae", "mornye")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(
            {member["id"] for member in result["teams"][0]["members"]},
            {"augusta", "iuno", "shorekeeper"},
        )
        self.assertEqual(
            [(member["id"], member["slot"]) for member in result["teams"][0]["members"]],
            [("augusta", "메인 딜러"), ("iuno", "서브 딜러"), ("shorekeeper", "서포터")],
        )
        self.assertIn("최고점", result["teams"][0]["reason"])

    def test_augusta_and_luuk_cores_split_iuno_from_lynae_mornye(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("augusta", "iuno", "shorekeeper", "luuk-herssen", "lynae", "mornye")
        }
        result = server.recommend({"roster": roster, "team_count": 2})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"augusta", "iuno", "shorekeeper"}, teams)
        self.assertIn({"luuk-herssen", "lynae", "mornye"}, teams)

    def test_level_90_augusta_iuno_are_not_treated_as_level_1_unbuilt(self):
        roster = {
            cid: {
                "owned": True,
                "level": 90,
                "build_status": "미육성" if cid in ("augusta", "iuno") else "완성",
                "max_uses": 1,
                "signature_weapon": cid in ("augusta", "iuno"),
            }
            for cid in ("augusta", "iuno", "shorekeeper", "xiangli-yao", "lynae", "mornye")
        }
        roster["xiangli-yao"]["build_status"] = "육성 중"
        result = server.recommend({"roster": roster, "team_count": 2})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"augusta", "iuno", "shorekeeper"}, teams)
        self.assertIn({"xiangli-yao", "lynae", "mornye"}, teams)

    def test_iuno_takes_lynae_mornye_before_xiangli_yao_without_augusta(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("iuno", "xiangli-yao", "lynae", "mornye")
        }
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        roster["xiangli-yao"]["build_status"] = "육성 중"
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(
            {member["id"] for member in result["teams"][0]["members"]},
            {"iuno", "lynae", "mornye"},
        )

    def test_every_main_damage_character_has_verified_team(self):
        characters = server.load_characters()
        rules = server.load_team_rules()
        template_leads = {template["members"][0] for template in rules["templates"]}
        carries = {
            character["id"]
            for character in characters
            if server.profile_for(character, rules).get("position") == "carry"
        }
        self.assertFalse(carries - template_leads, f"템플릿 누락: {sorted(carries - template_leads)}")

    def test_every_catalog_character_is_covered_by_meta_graph(self):
        character_ids = {character["id"] for character in server.load_characters()}
        covered_ids = {
            member_id
            for template in server.load_team_rules()["templates"]
            for member_id in template["members"]
        }
        self.assertEqual(character_ids, covered_ids)

    def test_declared_current_high_end_cores_exist_as_verified_templates(self):
        rules = server.load_team_rules()
        template_cores = {frozenset(template["members"]) for template in rules["templates"]}
        missing = [core for core in rules["high_end_cores"] if frozenset(core) not in template_cores]
        self.assertFalse(missing, f"최신 최고점 템플릿 누락: {missing}")

    def test_three_chisa_uses_fill_all_three_verified_premium_cores(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "aemeath", "denia", "chisa",
                "hiyuki", "lucilla",
                "cartethyia", "ciaccona",
            )
        }
        roster["chisa"]["max_uses"] = 3
        result = server.recommend({"roster": roster, "team_count": 3})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"aemeath", "denia", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "chisa"}, teams)
        self.assertIn({"cartethyia", "ciaccona", "chisa"}, teams)

    def test_two_chisa_uses_respect_replacement_opportunity_cost(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "aemeath", "denia", "chisa",
                "hiyuki", "lucilla", "shorekeeper",
                "cartethyia", "ciaccona", "rover-aero",
            )
        }
        roster["hiyuki"].update({"sequence": 2, "signature_weapon": True})
        roster["chisa"]["max_uses"] = 2
        result = server.recommend({"roster": roster, "team_count": 3})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"aemeath", "denia", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "chisa"}, teams)
        self.assertIn({"cartethyia", "ciaccona", "rover-aero"}, teams)
        self.assertNotIn({"cartethyia", "ciaccona", "chisa"}, teams)

    def test_chisa_one_two_three_use_boundary_matrix(self):
        ids = (
            "aemeath", "denia", "mornye", "chisa",
            "hiyuki", "lucilla", "shorekeeper",
            "cartethyia", "ciaccona", "rover-aero",
        )
        expected_chisa_carries = {
            1: {"hiyuki"},
            2: {"hiyuki", "aemeath"},
            3: {"hiyuki", "aemeath", "cartethyia"},
        }
        for uses, expected in expected_chisa_carries.items():
            roster = {
                cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
                for cid in ids
            }
            roster["hiyuki"].update({"sequence": 2, "signature_weapon": True})
            roster["chisa"]["max_uses"] = uses
            result = server.recommend({"roster": roster, "team_count": 3})
            actual = {
                next(member["id"] for member in team["members"] if member["slot"] == "메인 딜러")
                for team in result["teams"]
                if any(member["id"] == "chisa" for member in team["members"])
            }
            self.assertEqual(actual, expected, f"치사 사용 횟수 {uses} 경계 배분 오류")
            if uses < 3:
                teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
                self.assertIn({"cartethyia", "ciaccona", "rover-aero"}, teams)

    def test_aemeath_denia_mornye_meta_and_slot_order(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("aemeath", "denia", "mornye", "sanhua")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        team = result["teams"][0]
        self.assertEqual([m["id"] for m in team["members"]], ["aemeath", "denia", "mornye"])
        self.assertEqual([m["slot"] for m in team["members"]], ["메인 딜러", "서브 딜러", "서포터"])
        self.assertIn("이상 효과", team["reason"])

    def test_chisa_second_use_enables_aemeath_best_team_and_alternatives(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 2 if cid == "chisa" else 1}
            for cid in ("hiyuki", "lucilla", "chisa", "aemeath", "denia", "lynae", "mornye")
        }
        result = server.recommend({"roster": roster, "team_count": 2})
        self.assertGreaterEqual(len(result["configurations"]), 2)
        allocations = [
            [{member["id"] for member in team["members"]} for team in config["teams"]]
            for config in result["configurations"]
        ]
        self.assertIn({"aemeath", "denia", "chisa"}, allocations[0])
        self.assertTrue(any({"aemeath", "lynae", "mornye"} in allocation for allocation in allocations))

    def test_all_uses_roster_capacity_instead_of_four_team_cap(self):
        ids = ("hiyuki", "lucilla", "chisa", "aemeath", "denia", "mornye", "camellya", "sanhua", "shorekeeper", "jinhsi", "zhezhi", "verina", "jiyan", "mortefi", "baizhi")
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ids}
        result = server.recommend({"roster": roster, "team_count": "all"})
        self.assertEqual(result["maximum_team_count"], 5)
        self.assertGreaterEqual(len(result["teams"]), 5)

    def test_rover_forms_share_one_usage_slot_by_default(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "cartethyia", "ciaccona", "rover-aero",
                "zani", "rover-spectro", "shorekeeper",
                "rover-havoc", "roccia", "verina",
            )
        }
        result = server.recommend({"roster": roster, "team_count": "all"})
        rover_ids = {
            member["id"]
            for team in result["teams"]
            for member in team["members"]
            if member["id"].startswith("rover-")
        }
        self.assertLessEqual(len(rover_ids), 1)
        self.assertGreaterEqual(len(rover_ids), 1)

    def test_rover_forms_cannot_share_the_same_team(self):
        chars = {c["id"]: c for c in server.load_characters()}
        rules = server.load_team_rules()
        members = []
        for cid in ("rover-havoc", "yangyang", "rover-aero"):
            member = dict(chars[cid])
            member["state"] = {"build_status": "완성", "level": 90, "max_uses": 2}
            member["power"] = 34.6
            member["usage_key"] = server.usage_key(cid)
            members.append(member)
        self.assertIsNone(server.evaluate_team(tuple(members), rules))

    def test_rover_shared_usage_can_be_raised_for_multi_use_modes(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "cartethyia", "ciaccona", "rover-aero",
                "zani", "rover-spectro", "shorekeeper",
                "rover-havoc", "roccia", "verina",
            )
        }
        for cid in ("rover-aero", "rover-spectro", "rover-havoc"):
            roster[cid]["max_uses"] = 2
        result = server.recommend({"roster": roster, "team_count": "all"})
        rover_uses = sum(
            1
            for team in result["teams"]
            for member in team["members"]
            if member["id"].startswith("rover-")
        )
        self.assertLessEqual(rover_uses, 2)
        self.assertGreaterEqual(rover_uses, 2)
        for team in result["teams"]:
            self.assertLessEqual(
                sum(1 for member in team["members"] if member["id"].startswith("rover-")),
                1,
            )

    def test_lucy_rebecca_mornye_is_current_meta_core(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("lucy", "rebecca", "mornye", "yinlin", "shorekeeper")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        team = result["teams"][0]
        self.assertEqual([member["id"] for member in team["members"]], ["lucy", "rebecca", "mornye"])
        self.assertIn("Hack 최고점", team["reason"])

    def test_built_galbrena_core_precedes_older_built_carries(self):
        roster = {
            cid: {
                "owned": True,
                "level": 90,
                "build_status": "완성",
                "max_uses": 1,
                "signature_weapon": cid in ("galbrena", "carlotta", "camellya"),
            }
            for cid in (
                "galbrena", "qiuyuan", "shorekeeper",
                "carlotta", "zhezhi", "verina",
                "camellya", "sanhua", "baizhi",
            )
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(
            {member["id"] for member in result["teams"][0]["members"]},
            {"galbrena", "qiuyuan", "shorekeeper"},
        )

    def test_galbrena_iuno_shorekeeper_is_verified_alternative(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("galbrena", "iuno", "shorekeeper")
        }
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(result["teams"][0]["confidence"], "높음")
        self.assertIn("갈브레나·유노", result["teams"][0]["reason"])

    def test_galbrena_uses_iuno_when_qiuyuan_is_spent_by_phrolova(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("phrolova", "cantarella", "qiuyuan", "galbrena", "iuno", "mortefi", "verina")
        }
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        roster["mortefi"].update({"level": 1, "build_status": "미육성"})
        result = server.recommend({"roster": roster, "team_count": "all"})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"phrolova", "cantarella", "qiuyuan"}, teams)
        self.assertIn({"galbrena", "iuno", "verina"}, teams)
        self.assertNotIn({"galbrena", "mortefi", "verina"}, teams)

    def test_latest_galbrena_gets_shorekeeper_over_older_camellya_fallback(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "phrolova", "cantarella", "qiuyuan",
                "galbrena", "iuno", "shorekeeper",
                "camellya", "sanhua", "baizhi",
            )
        }
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": "all"})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"phrolova", "cantarella", "qiuyuan"}, teams)
        self.assertIn({"galbrena", "iuno", "shorekeeper"}, teams)
        self.assertIn({"camellya", "sanhua", "baizhi"}, teams)
        self.assertNotIn({"camellya", "sanhua", "shorekeeper"}, teams)

    def test_denia_roster_does_not_spend_shorekeeper_on_unbuilt_chixia_changli(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in (
                "aemeath", "denia", "chisa",
                "hiyuki", "lucilla",
                "phrolova", "cantarella", "qiuyuan",
                "galbrena", "iuno", "shorekeeper",
                "camellya", "sanhua", "baizhi",
                "changli", "chixia", "lumi",
            )
        }
        roster["chisa"]["max_uses"] = 2
        roster["shorekeeper"]["max_uses"] = 2
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        roster["changli"]["build_status"] = "실전 가능"
        roster["chixia"].update({"level": 1, "build_status": "미육성"})
        roster["lumi"].update({"level": 1, "build_status": "미육성"})
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": "all"})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"aemeath", "denia", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "chisa"}, teams)
        self.assertIn({"phrolova", "cantarella", "qiuyuan"}, teams)
        self.assertIn({"galbrena", "iuno", "shorekeeper"}, teams)
        self.assertNotIn({"changli", "chixia", "shorekeeper"}, teams)

    def test_unbuilt_iuno_is_used_as_galbrena_amplifier_before_onfield_carry(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("galbrena", "iuno", "shorekeeper", "lynae", "mornye")
        }
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        result = server.recommend({"roster": roster, "team_count": 1})
        self.assertEqual(
            {member["id"] for member in result["teams"][0]["members"]},
            {"galbrena", "iuno", "shorekeeper"},
        )

    def test_galbrena_iuno_falls_back_to_baizhi_before_unbuilt_mortefi(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("phrolova", "cantarella", "qiuyuan", "galbrena", "iuno", "mortefi", "baizhi")
        }
        roster["iuno"].update({"build_status": "미육성", "signature_weapon": True})
        roster["mortefi"].update({"level": 1, "build_status": "미육성"})
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": "all"})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"phrolova", "cantarella", "qiuyuan"}, teams)
        self.assertIn({"galbrena", "iuno", "baizhi"}, teams)
        self.assertNotIn({"galbrena", "mortefi", "baizhi"}, teams)

    def test_global_allocation_expands_carlotta_and_jinhsi_cores(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 2 if cid == "verina" else 1}
            for cid in ("carlotta", "zhezhi", "jinhsi", "yinlin", "verina", "xiangli-yao", "yangyang", "baizhi", "shorekeeper")
        }
        roster["xiangli-yao"]["build_status"] = "육성 중"
        roster["yangyang"]["build_status"] = "미육성"
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": 2})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertTrue(any({"carlotta", "zhezhi"} < team for team in teams))
        self.assertTrue(any({"jinhsi", "yinlin"} < team for team in teams))

    def test_unbuilt_core_does_not_take_premium_support_from_ready_core(self):
        chars = {c["id"]: c for c in server.load_characters()}
        rules = server.load_team_rules()
        def member(cid, status):
            value = dict(chars[cid]); value["state"] = {"build_status": status}; value["power"] = server.BUILD_POINTS[status] + 9.6; return value
        ready = server.evaluate_team(tuple(member(cid, status) for cid, status in (("camellya", "완성"), ("sanhua", "완성"), ("shorekeeper", "완성"))), rules)
        weak = server.evaluate_team(tuple(member(cid, status) for cid, status in (("camellya", "완성"), ("yangyang", "미육성"), ("shorekeeper", "완성"))), rules)
        self.assertIsNotNone(ready)
        self.assertIsNone(weak)

    def test_premium_support_is_allocated_to_ready_core(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("galbrena", "qiuyuan", "jinhsi", "yuanwu", "shorekeeper", "baizhi")
        }
        roster["yuanwu"]["build_status"] = "미육성"
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": 2})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"galbrena", "qiuyuan", "shorekeeper"}, teams)
        self.assertIn({"jinhsi", "yuanwu", "baizhi"}, teams)

    def test_verified_roster_expansion_teams_are_recognized(self):
        expected = (
            ("phrolova", "cantarella", "shorekeeper"),
            ("galbrena", "qiuyuan", "shorekeeper"),
            ("iuno", "lynae", "mornye"),
            ("carlotta", "sanhua", "baizhi"),
        )
        for members in expected:
            roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in members}
            result = server.recommend({"roster": roster, "team_count": 1})
            self.assertEqual({member["id"] for member in result["teams"][0]["members"]}, set(members))
            self.assertEqual(result["teams"][0]["confidence"], "높음")

    def test_carlotta_keeps_zhezhi_while_camellya_uses_sanhua(self):
        roster = {
            cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1}
            for cid in ("carlotta", "zhezhi", "verina", "camellya", "sanhua", "baizhi")
        }
        roster["baizhi"]["build_status"] = "실전 가능"
        result = server.recommend({"roster": roster, "team_count": 2})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"carlotta", "zhezhi", "verina"}, teams)
        self.assertIn({"camellya", "sanhua", "baizhi"}, teams)
        self.assertNotIn({"carlotta", "sanhua", "baizhi"}, teams)

    def test_chisa_stays_with_aemeath_and_baizhi_stays_with_camellya(self):
        ids = ("aemeath", "denia", "chisa", "hiyuki", "lucilla", "camellya", "sanhua", "baizhi", "iuno", "lynae", "mornye")
        roster = {cid: {"owned": True, "level": 90, "build_status": "완성", "max_uses": 1} for cid in ids}
        roster["chisa"]["max_uses"] = 2
        roster["baizhi"]["build_status"] = "실전 가능"
        roster["iuno"]["build_status"] = "미육성"
        result = server.recommend({"roster": roster, "team_count": 4})
        teams = [{member["id"] for member in team["members"]} for team in result["teams"]]
        self.assertIn({"aemeath", "denia", "chisa"}, teams)
        self.assertIn({"hiyuki", "lucilla", "chisa"}, teams)
        self.assertIn({"camellya", "sanhua", "baizhi"}, teams)
        self.assertIn({"iuno", "lynae", "mornye"}, teams)

    def test_unrelated_generic_team_is_rejected(self):
        chars = {c["id"]: c for c in server.load_characters()}
        rules = server.load_team_rules()
        members = []
        for cid in ("phrolova", "sanhua", "shorekeeper"):
            member = dict(chars[cid]); member["state"] = {"build_status": "완성"}; member["power"] = 34.6; members.append(member)
        self.assertIsNone(server.evaluate_team(tuple(members), rules))

    def test_official_korean_names_are_used(self):
        names = {c["id"]: c["name_ko"] for c in server.load_characters()}
        self.assertEqual(names["zhezhi"], "절지")
        self.assertEqual(names["baizhi"], "설지")
        self.assertEqual(names["denia"], "데니아")
        self.assertEqual(names["aemeath"], "에이메스")

    def test_roster_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.db"
            with patch.object(server, "DB_PATH", db):
                server.init_db()
                server.save_roster([{"character_id": "jinhsi", "owned": True, "sequence": 2, "level": 90, "build_status": "실전 가능", "max_uses": 1, "signature_weapon": True, "weapon_rank": 2}])
                row = server.get_roster()["jinhsi"]
                self.assertEqual(row["sequence"], 2)
                self.assertEqual(row["build_status"], "실전 가능")
                self.assertEqual(row["max_uses"], 1)
                self.assertEqual(row["signature_weapon"], 1)
                self.assertEqual(row["weapon_rank"], 2)


if __name__ == "__main__":
    unittest.main()
