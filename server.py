from __future__ import annotations

import json
import mimetypes
import ssl
import sqlite3
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
DATA = ROOT / "data"
DB_PATH = ROOT / "roster.db"
CACHE = ROOT / ".cache" / "characters"


def load_characters() -> list[dict[str, Any]]:
    characters = json.loads((DATA / "characters.json").read_text(encoding="utf-8"))
    for character in characters:
        character["image_source"] = character["image"]
        character["image"] = f"/api/image/{character['id']}"
    return characters


def character_image(character_id: str) -> tuple[bytes, str]:
    character = next((c for c in load_characters() if c["id"] == character_id), None)
    if not character:
        raise KeyError(character_id)
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{character_id}.png"
    if not cached.exists():
        request = urllib.request.Request(
            character["image_source"],
            headers={"User-Agent": "ResonanceLab/0.1 (+local roster planner)"},
        )
        # Python.org macOS builds may not be connected to the system CA store.
        # These are public, non-sensitive game thumbnails; verification is scoped
        # only to this image download and never used for account/API traffic.
        image_context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=20, context=image_context) as response:
            cached.write_bytes(response.read())
    return cached.read_bytes(), "image/png"


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS roster (
                character_id TEXT PRIMARY KEY,
                owned INTEGER NOT NULL DEFAULT 0,
                sequence INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
                build_status TEXT NOT NULL DEFAULT '미육성',
                max_uses INTEGER NOT NULL DEFAULT 1,
                preference TEXT NOT NULL DEFAULT '보통',
                signature_weapon INTEGER NOT NULL DEFAULT 0,
                weapon_rank INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in con.execute("PRAGMA table_info(roster)")}
        if "signature_weapon" not in columns:
            con.execute("ALTER TABLE roster ADD COLUMN signature_weapon INTEGER NOT NULL DEFAULT 0")
        if "weapon_rank" not in columns:
            con.execute("ALTER TABLE roster ADD COLUMN weapon_rank INTEGER NOT NULL DEFAULT 1")


def get_roster() -> dict[str, dict[str, Any]]:
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM roster").fetchall()
    return {row["character_id"]: dict(row) for row in rows}


def storage_status() -> dict[str, Any]:
    roster = get_roster()
    timestamps = [row.get("updated_at") for row in roster.values() if row.get("updated_at")]
    return {
        "persistent": True,
        "engine": "SQLite",
        "file": DB_PATH.name,
        "records": len(roster),
        "last_saved": max(timestamps) if timestamps else None,
    }


def save_roster(items: list[dict[str, Any]]) -> None:
    with sqlite3.connect(DB_PATH) as con:
        for item in items:
            con.execute(
                """
                INSERT INTO roster(character_id, owned, sequence, level, build_status, max_uses, preference, signature_weapon, weapon_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(character_id) DO UPDATE SET
                    owned=excluded.owned,
                    sequence=excluded.sequence,
                    level=excluded.level,
                    build_status=excluded.build_status,
                    max_uses=excluded.max_uses,
                    preference=excluded.preference,
                    signature_weapon=excluded.signature_weapon,
                    weapon_rank=excluded.weapon_rank,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    item["character_id"],
                    int(bool(item.get("owned"))),
                    max(0, min(6, int(item.get("sequence", 0)))),
                    max(1, min(90, int(item.get("level", 1)))),
                    item.get("build_status", "미육성"),
                    max(0, min(10, int(item.get("max_uses", 1)))),
                    item.get("preference", "보통"),
                    int(bool(item.get("signature_weapon"))),
                    max(1, min(5, int(item.get("weapon_rank", 1)))),
                ),
            )


BUILD_POINTS = {"미육성": 0, "육성 중": 8, "실전 가능": 18, "완성": 25}
BUILD_READINESS = {"미육성": 0.0, "육성 중": 0.45, "실전 가능": 0.78, "완성": 1.0}
MIN_INFERRED_TEAM_SCORE = 60.0
SCORE_WEIGHTS = {"composition": 44, "meta": 10, "investment": 33, "build": 13}
SEQUENCE_QUALITY = {0: 0.78, 1: 0.83, 2: 0.87, 3: 0.91, 4: 0.94, 5: 0.97, 6: 1.0}


def load_team_rules() -> dict[str, Any]:
    return json.loads((DATA / "team_rules.json").read_text(encoding="utf-8"))


def profile_for(character: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    profile = dict(rules["profiles"].get(character["id"], {}))
    if not profile:
        position = {"딜러": "carry", "서브딜러": "amplifier", "서포터": "support"}[character["role"]]
        profile = {"position": position, "archetypes": [character["element_ko"]]}
        if position == "carry":
            profile["damage"] = [character["element_ko"]]
        else:
            profile["provides"] = [character["element_ko"]]
        if position == "support":
            profile["sustain"] = True
    return profile


def effective_readiness(member: dict[str, Any]) -> float:
    """Combine the explicit build label with concrete investment signals.

    A hypothetical Lv.90 character with a signature weapon should not receive
    the same zero-readiness score as a truly untouched Lv.1 character. The
    explicit label remains authoritative once it is '실전 가능' or '완성'.
    """
    state = member["state"]
    readiness = BUILD_READINESS.get(state.get("build_status", "미육성"), 0.0)
    level = int(state.get("level", 1))
    level_floor = 0.0
    if level >= 90:
        level_floor = 0.55
    elif level >= 80:
        level_floor = 0.42
    elif level >= 70:
        level_floor = 0.28
    if state.get("signature_weapon"):
        level_floor = min(0.68, level_floor + 0.10)
    return max(readiness, level_floor)


def investment_quality(member: dict[str, Any]) -> float:
    """Return 0..1 investment from sequence and signature weapon state.

    S0 is a functional character rather than zero investment. Sequences have
    enough headroom to let an older, highly invested carry overtake a newer
    low-investment carry when the rest of the team is genuinely complete.
    """
    state = member["state"]
    sequence = max(0, min(6, int(state.get("sequence", 0))))
    quality = SEQUENCE_QUALITY[sequence]
    if state.get("signature_weapon"):
        quality += 0.12 + max(0, int(state.get("weapon_rank", 1)) - 1) * 0.025
    return min(1.0, quality)


def weighted_member_average(
    members: tuple[dict[str, Any], ...],
    positions: dict[str, str],
    values: dict[str, float],
) -> float:
    role_weights = {"carry": 0.50, "amplifier": 0.30, "support": 0.20}
    weighted = [
        (values[member["id"]], role_weights.get(positions[member["id"]], 0.25))
        for member in members
    ]
    total_weight = sum(weight for _, weight in weighted)
    return sum(value * weight for value, weight in weighted) / max(total_weight, 0.01)


def evaluate_team(members: tuple[dict[str, Any], ...], rules: dict[str, Any]) -> dict[str, Any] | None:
    member_ids = {member["id"] for member in members}
    template = next((item for item in rules["templates"] if set(item["members"]) == member_ids), None)
    profiles = {member["id"]: profile_for(member, rules) for member in members}
    carries = [member for member in members if profiles[member["id"]].get("position") == "carry"]
    if not carries:
        return None

    member_positions = template.get("positions", {}) if template else {}
    resolved_positions = {
        member["id"]: member_positions.get(member["id"], profiles[member["id"]].get("position", "amplifier"))
        for member in members
    }
    investment = sum(member["power"] for member in members) / len(members)
    readiness = {}
    for member in members:
        value = effective_readiness(member)
        if member["state"].get("build_status") == "미육성":
            if resolved_positions[member["id"]] == "carry":
                value = min(value, 0.35)
            elif resolved_positions[member["id"]] == "amplifier":
                value = min(value, 0.65)
        readiness[member["id"]] = value
    investments = {member["id"]: investment_quality(member) for member in members}
    readiness_penalty = sum(1.0 - value for value in readiness.values()) * 8
    core_members = [member for member in members if resolved_positions[member["id"]] != "support"]
    core_readiness = sum(readiness[member["id"]] for member in core_members) / max(1, len(core_members))
    weakest_core_readiness = min((readiness[member["id"]] for member in core_members), default=1.0)
    support_leverage = sum(
        profile.get("support_value", 3) * core_readiness * 1.2
        for profile in profiles.values()
        if profile.get("position") == "support"
    )
    if template:
        preview = template.get("status") == "preview"
        reason = f"{'출시 전 프리뷰' if preview else '메타 조합'} · {template['label']}"
        tags = template["tags"]
        confidence = "프리뷰" if preview else "높음"
    else:
        best_carry = carries[0]
        carry_profile = profiles[best_carry["id"]]
        damage = set(carry_profile.get("damage", []))
        carry_archetypes = set(carry_profile.get("archetypes", []))
        matched_buffs: set[str] = set()
        archetype_hits: set[str] = set()
        synergy_hits = 0
        for member in members:
            if member["id"] == best_carry["id"]:
                continue
            member_profile = profiles[member["id"]]
            matched_buffs |= damage & set(member_profile.get("provides", []))
            archetype_hits |= carry_archetypes & set(member_profile.get("archetypes", []))
            if member["id"] in best_carry.get("synergy", []):
                synergy_hits += 1
        sustain = any(profile.get("sustain") for profile in profiles.values())
        amplifiers = [profile for profile in profiles.values() if profile.get("position") == "amplifier"]
        supports = [profile for profile in profiles.values() if profile.get("position") == "support"]
        # A generic team is eligible only when its carry has a real mechanical
        # connection to an amplifier. Roster capacity must never be filled with
        # three individually strong but compositionally unrelated characters.
        if not amplifiers or not (matched_buffs or archetype_hits or synergy_hits):
            return None
        score = 38 + investment * 0.72 + len(matched_buffs) * 9 + len(archetype_hits) * 5
        score += synergy_hits * 4 + (5 if sustain else 0) + support_leverage - readiness_penalty
        score -= max(0, len(carries) - 1) * 3
        score -= (10 if not amplifiers else 0) + max(0, len(supports) - 1) * 8
        # Inferred compatibility must not outrank a verified current-meta core.
        # Its purpose is to fill and expand the roster after known pairings.
        score = min(91.0, score)
        tags = sorted(matched_buffs | archetype_hits)
        compatible = ", ".join(tags) if tags else "육성도와 속성"
        reason = f"호환 조합 · {best_carry['name_ko']}의 {compatible} 조건을 공유"
        confidence = "중간" if tags else "낮음"

    primary_carries = [
        member for member in members if resolved_positions[member["id"]] == "carry"
    ] or carries
    primary_carry = max(
        primary_carries,
        key=lambda member: profiles[member["id"]].get("meta_value", 5),
    )
    composition_quality = (template["score"] if template else min(88.0, score)) / 100
    meta_quality = min(1.0, profiles[primary_carry["id"]].get("meta_value", 5) / 10)
    investment_average = weighted_member_average(members, resolved_positions, investments)
    readiness_average = weighted_member_average(members, resolved_positions, readiness)
    score_details = {
        "composition": round(composition_quality * SCORE_WEIGHTS["composition"], 1),
        "meta": round(meta_quality * SCORE_WEIGHTS["meta"], 1),
        "investment": round(investment_average * SCORE_WEIGHTS["investment"], 1),
        "build": round(readiness_average * SCORE_WEIGHTS["build"], 1),
    }
    score = min(100.0, sum(score_details.values()))

    support_alignment = sum(
        profile.get("support_value", 3) * core_readiness * 2
        for profile in profiles.values()
        if profile.get("position") == "support"
    )
    # Verified team tiers are deliberately separate from combat score. This lets
    # the global allocator prefer a character's actual BiS core, while retaining
    # alternatives for roster expansion after a contested unit is consumed.
    tier_bonus = {"bis": 10, "high": 7, "alternative": 3, "expansion": 0}
    high_end_cores = {
        frozenset(core)
        for core in rules.get("high_end_cores", []) + rules.get("preview_high_end_cores", [])
    }
    if frozenset(member_ids) in high_end_cores:
        effective_tier = "bis"
    elif template and template["score"] >= 95:
        effective_tier = "high"
    elif template and template["score"] >= 90:
        effective_tier = "alternative"
    else:
        effective_tier = template.get("tier") if template else None
    # Verified template scores already include the support's contribution.
    # Adding support_value again double-counted premium supports and made a team
    # hoard Chisa even when it had an excellent Aero Rover replacement.
    allocation_score = score + (3 if template else 0)
    if template:
        allocation_score += tier_bonus.get(effective_tier, 0)
        # A tiny recency tie-breaker keeps newly released/preview BiS cores from
        # losing to an older core only because of a few tenths of scarcity math.
        # It is intentionally too small to overcome a real composition or build gap.
        if template.get("status") == "preview" and effective_tier == "bis":
            allocation_score += 1.0
    premium_support_value = max(
        (
            profiles[member["id"]].get("support_value", 0)
            for member in members
            if resolved_positions[member["id"]] == "support"
        ),
        default=0,
    )
    # If an old or fallback team contains an unbuilt core, it should not spend a
    # scarce premium support just because the static template is verified. This
    # keeps teams such as Lv.1 Chixia + Changli from taking Shorekeeper while
    # newer/complete teams still need that crit support. Combat score remains
    # visible; this only changes global resource allocation priority.
    if premium_support_value >= 8 and weakest_core_readiness < 0.70:
        allocation_score -= (0.70 - weakest_core_readiness) * premium_support_value * 2.8
    premium_core_mismatch = premium_support_value >= 8 and weakest_core_readiness < 0.45
    # Allocation value is account-aware: recent high-value carries with actual
    # investment should receive contested premium supports before older or
    # low-investment cores. Combat score remains separate and visible in the UI.
    carry_investment = max(
        (
            profiles[member["id"]].get("meta_value", 5) * 0.8
            + int(member["state"].get("sequence", 0)) * 2
            + (1.5 if member["state"].get("signature_weapon") else 0)
        ) * readiness[member["id"]]
        for member in carries
    )
    allocation_score += carry_investment
    return {
        "key": ":".join(sorted(member_ids)),
        "members": members,
        "score": round(score, 1),
        "allocation_score": round(allocation_score, 1),
        "reason": reason,
        "tags": tags,
        "confidence": confidence,
        "readiness": round(sum(readiness.values()) / len(readiness) * 100),
        "score_details": score_details,
        "member_positions": member_positions,
        "effective_tier": effective_tier,
        "primary_carry_id": primary_carry["id"],
        "carry_investment": round(carry_investment, 1),
        "opportunity_bonus": 0.0,
        "premium_core_mismatch": premium_core_mismatch,
    }


def apply_opportunity_value(candidates: list[dict[str, Any]]) -> None:
    """Price a contested teammate by the combat loss when they are removed."""
    by_carry: dict[str, list[dict[str, Any]]] = {}
    member_carries: dict[str, set[str]] = {}
    for candidate in candidates:
        carry_id = candidate["primary_carry_id"]
        by_carry.setdefault(carry_id, []).append(candidate)
        for member in candidate["members"]:
            if member["id"] != carry_id:
                member_carries.setdefault(member["id"], set()).add(carry_id)

    for candidate in candidates:
        carry_id = candidate["primary_carry_id"]
        marginal_losses: list[float] = []
        for member in candidate["members"]:
            member_id = member["id"]
            position = candidate.get("member_positions", {}).get(member_id, member.get("_position"))
            # Opportunity pricing is for the contested flex/sustain slot. Core
            # amplifiers such as Lucilla or Ciaccona are not interchangeable
            # supports and must not inflate every variant of the same core.
            if (
                member_id == carry_id
                or position != "support"
                or len(member_carries.get(member_id, set())) < 2
            ):
                continue
            alternatives = [
                alternative
                for alternative in by_carry.get(carry_id, [])
                if member_id not in {item["id"] for item in alternative["members"]}
            ]
            if alternatives:
                best_alternative = max(alternatives, key=lambda item: item["score"])
                loss = max(0.0, candidate["score"] - best_alternative["score"])
                # Two verified BiS variants within a small practical margin are
                # interchangeable. Pricing that tiny difference as scarcity made
                # Hiyuki hoard Chisa even though Suisui is an equal high-end slot,
                # preventing Xuanling and another Chisa core from being completed.
                if (
                    candidate.get("effective_tier") == "bis"
                    and best_alternative.get("effective_tier") == "bis"
                    and loss <= 1.5
                ):
                    loss = 0.0
                marginal_losses.append(loss)
        # The same raw upgrade is worth more on a recent, highly invested carry.
        # This makes sequence/signature investment affect who receives a scarce
        # support, instead of merely raising both of that carry's variants equally.
        investment_factor = 2 + candidate.get("carry_investment", 0) / 10
        opportunity_bonus = max(marginal_losses, default=0.0) * investment_factor
        candidate["opportunity_bonus"] = round(opportunity_bonus, 1)
        candidate["allocation_score"] = round(candidate["allocation_score"] + opportunity_bonus, 1)


def optimize_teams(candidates: list[dict[str, Any]], team_count: int, alternative_count: int = 3) -> list[list[dict[str, Any]]]:
    # Beam search evaluates allocations globally instead of greedily consuming the
    # best support in the first team. Usage limits are enforced across every team.
    states: list[tuple[list[dict[str, Any]], dict[str, int], float]] = [([], {}, 0.0)]
    beam_width = 3000 if team_count > 4 else 450
    for _ in range(team_count):
        expanded: list[tuple[list[dict[str, Any]], dict[str, int], float]] = []
        for selected, counts, total in states:
            selected_keys = {team["key"] for team in selected}
            for candidate in candidates:
                if candidate["key"] in selected_keys:
                    continue
                next_counts = dict(counts)
                allowed = True
                for member in candidate["members"]:
                    next_counts[member["id"]] = next_counts.get(member["id"], 0) + 1
                    if next_counts[member["id"]] > int(member["state"].get("max_uses", 1)):
                        allowed = False
                        break
                if allowed:
                    diversity = len(set(next_counts)) * 0.15
                    expanded.append((selected + [candidate], next_counts, total + candidate["allocation_score"] + diversity))
        if not expanded:
            break
        expanded.sort(key=lambda item: item[2], reverse=True)
        states = expanded[:beam_width]
    states.sort(key=lambda item: (len(item[0]), item[2]), reverse=True)
    alternatives: list[list[dict[str, Any]]] = []
    seen: set[tuple[str, ...]] = set()
    for selected, _, _ in states:
        allocation_key = tuple(sorted(team["key"] for team in selected))
        if allocation_key in seen:
            continue
        seen.add(allocation_key)
        alternatives.append(selected)
        if len(alternatives) >= alternative_count:
            break
    return alternatives


def complete_roster_allocation(
    candidates: list[dict[str, Any]],
    available: list[dict[str, Any]],
    team_count: int,
    excluded_key: str | None = None,
) -> list[dict[str, Any]]:
    """Greedily choose the strongest teams while reserving enough slots to finish.

    This path is used for the roster-wide view. Unlike a score-only beam cutoff,
    it scans every valid triple and never spends characters needed to reach the
    dynamically calculated maximum number of teams.
    """
    selected: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    selected_keys: set[str] = set()
    limits = {member["id"]: int(member["state"].get("max_uses", 1)) for member in available}
    positions = {member["id"]: member.get("_position") for member in available}

    for depth in range(team_count):
        viable: list[dict[str, Any]] = []
        teams_left = team_count - depth - 1
        for candidate in candidates:
            if candidate["key"] == excluded_key:
                continue
            if candidate["key"] in selected_keys:
                continue
            next_counts = dict(counts)
            if any(next_counts.get(member["id"], 0) + 1 > limits[member["id"]] for member in candidate["members"]):
                continue
            for member in candidate["members"]:
                next_counts[member["id"]] = next_counts.get(member["id"], 0) + 1
            remaining_total = sum(limits[cid] - next_counts.get(cid, 0) for cid in limits)
            remaining_carries = sum(
                limits[cid] - next_counts.get(cid, 0)
                for cid in limits
                if positions[cid] == "carry"
            )
            if remaining_total >= teams_left * 3 and remaining_carries >= teams_left:
                viable.append(candidate)
        if not viable:
            break
        chosen = viable[0]
        selected.append(chosen)
        selected_keys.add(chosen["key"])
        for member in chosen["members"]:
            counts[member["id"]] = counts.get(member["id"], 0) + 1
    return selected


def candidate_shortlist(candidates: list[dict[str, Any]], available: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep meta leaders plus enough options for every owned character.

    A score-only cutoff strands lower-investment characters when 'all' is chosen.
    Per-character coverage lets the allocator reach the dynamically calculated
    roster maximum without evaluating every possible triple at every beam step.
    """
    selected = {candidate["key"]: candidate for candidate in candidates[:240]}
    for member in available:
        covered = 0
        for candidate in candidates:
            if member["id"] in {item["id"] for item in candidate["members"]}:
                selected[candidate["key"]] = candidate
                covered += 1
                if covered >= 16:
                    break
    return sorted(selected.values(), key=lambda item: item["allocation_score"], reverse=True)


def serialize_teams(selected: list[dict[str, Any]], rules: dict[str, Any]) -> list[dict[str, Any]]:
    selected = sorted(selected, key=lambda item: item["score"], reverse=True)
    teams = []
    position_order = {"carry": 0, "amplifier": 1, "support": 2}
    slot_names = {"carry": "메인 딜러", "amplifier": "서브 딜러", "support": "서포터"}
    for index, candidate in enumerate(selected, 1):
        member_positions = candidate.get("member_positions", {})
        ordered_members = sorted(
            candidate["members"],
            key=lambda member: position_order.get(
                member_positions.get(member["id"], profile_for(member, rules).get("position")), 9
            ),
        )
        teams.append({
            "id": index,
            "score": candidate["score"],
            "members": [
                {
                    **{k: member[k] for k in ("id", "name_ko", "image", "role", "element_ko")},
                    "slot": slot_names.get(
                        member_positions.get(member["id"], profile_for(member, rules).get("position")),
                        member["role"],
                    ),
                }
                for member in ordered_members
            ],
            "reason": candidate["reason"],
            "tags": candidate["tags"],
            "confidence": candidate["confidence"],
            "readiness": candidate.get("readiness", 0),
            "score_details": candidate.get("score_details", {}),
        })
    return teams


def recommend(payload: dict[str, Any]) -> dict[str, Any]:
    chars = {c["id"]: c for c in load_characters()}
    rules = load_team_rules()
    roster = payload.get("roster") or get_roster()
    requested_count = payload.get("team_count", 3)
    available: list[dict[str, Any]] = []
    for cid, state in roster.items():
        if (
            cid not in chars
            or not state.get("owned")
            or int(state.get("max_uses", 1)) <= 0
        ):
            continue
        char = dict(chars[cid])
        char["state"] = state
        char["_position"] = profile_for(char, rules).get("position")
        char["power"] = BUILD_POINTS.get(state.get("build_status"), 0) + int(state.get("level", 1)) / 10
        char["power"] += int(state.get("sequence", 0)) * 0.7
        char["power"] += (4 if state.get("signature_weapon") else 0) + int(state.get("weapon_rank", 1)) * 0.6
        available.append(char)

    if len(available) < 3:
        return {"teams": [], "configurations": [], "message": "보유 캐릭터를 최소 3명 선택해 주세요."}

    maximum_count = max(1, sum(int(member["state"].get("max_uses", 1)) for member in available) // 3)
    team_count = maximum_count if str(requested_count) == "all" else max(1, min(maximum_count, int(requested_count)))

    candidates = [evaluated for group in combinations(available, 3) if (evaluated := evaluate_team(group, rules))]
    if str(requested_count) == "all":
        candidates = [
            candidate
            for candidate in candidates
            if candidate["score"] >= MIN_INFERRED_TEAM_SCORE
            and not candidate.get("premium_core_mismatch")
        ]
    apply_opportunity_value(candidates)
    candidates.sort(key=lambda item: item["allocation_score"], reverse=True)
    if str(requested_count) == "all":
        allocations = []
        for target_count in range(team_count, 0, -1):
            # Build one complete baseline first, then perturb each team in that
            # allocation. Excluding only the global top-N candidates repeatedly
            # produced the same maximum-size result and collapsed the UI to one
            # configuration. Baseline-team perturbations preserve capacity while
            # discovering meaningfully different support/core assignments.
            baseline = complete_roster_allocation(candidates, available, target_count)
            excluded_keys = [None]
            excluded_keys.extend(team["key"] for team in baseline)
            excluded_keys.extend(candidate["key"] for candidate in candidates[:12])
            excluded_keys = list(dict.fromkeys(excluded_keys))
            completed = [complete_roster_allocation(candidates, available, target_count, key) for key in excluded_keys]
            completed = [allocation for allocation in completed if len(allocation) == target_count]
            if completed:
                unique: dict[tuple[str, ...], list[dict[str, Any]]] = {}
                for allocation in completed:
                    key = tuple(sorted(team["key"] for team in allocation))
                    unique[key] = allocation
                allocations = sorted(
                    unique.values(),
                    key=lambda allocation: sum(team["allocation_score"] for team in allocation),
                    reverse=True,
                )[:3]
                team_count = target_count
                break
    else:
        allocations = optimize_teams(candidate_shortlist(candidates, available), team_count)
    configurations = []
    for index, allocation in enumerate(allocations, 1):
        teams = serialize_teams(allocation, rules)
        configurations.append({
            "id": index,
            "label": f"추천 구성 {chr(64 + index)}",
            "team_count": len(teams),
            "total_score": round(sum(team["allocation_score"] for team in allocation), 1),
            "combat_score": round(sum(team["score"] for team in teams), 1),
            "teams": teams,
        })

    primary_teams = configurations[0]["teams"] if configurations else []
    actual_count = len(primary_teams)
    count_note = f"보유풀로 가능한 {actual_count}개" if str(requested_count) == "all" else f"{actual_count}개"

    return {
        "teams": primary_teams,
        "configurations": configurations,
        "maximum_team_count": actual_count,
        "capacity_upper_bound": maximum_count,
        "message": f"메타와 사용 횟수를 반영해 {count_note} 파티의 서로 다른 배분안 {len(configurations)}가지를 계산했습니다.",
        "engine": "hybrid-meta-v2",
        "rules_version": rules["version"],
        "meta_patch": rules.get("meta_patch"),
        "meta_updated_at": rules.get("meta_updated_at"),
    }


class AppHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # Allow the bundled index.html to work even when it was opened directly
        # through file:// instead of through the local HTTP server.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/characters":
            self._json(load_characters())
            return
        if path == "/api/roster":
            self._json(get_roster())
            return
        if path == "/api/storage":
            self._json(storage_status())
            return
        if path == "/api/health":
            self._json({"ok": True, "characters": len(load_characters())})
            return
        if path.startswith("/api/image/"):
            character_id = path.removeprefix("/api/image/")
            try:
                body, content_type = character_image(character_id)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (KeyError, OSError):
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self._payload()
            if path == "/api/roster":
                items = payload if isinstance(payload, list) else payload.get("items", [])
                save_roster(items)
                self._json({"ok": True, "saved": len(items), "saved_at": datetime.now().isoformat(timespec="seconds"), "storage": "SQLite · roster.db"})
                return
            if path == "/api/recommend":
                self._json(recommend(payload))
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def translate_path(self, path: str) -> str:
        clean = urlparse(path).path.lstrip("/") or "index.html"
        return str(STATIC / clean)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[web] {self.address_string()} {fmt % args}")


def main() -> None:
    init_db()
    mimetypes.add_type("text/javascript", ".js")
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler)
    print("Wuwa Roster Lab: http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
