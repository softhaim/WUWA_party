from __future__ import annotations

import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "local_ai" / "dataset"
SYSTEM = (
    "너는 명조 전용 한국어 육성 도우미 레조다. 제공된 데이터에 근거해 결론부터 자연스럽고 간결하게 답한다. "
    "딜러·서브딜러·서포터 역할을 바꾸지 않고, 자료에 없는 효과나 대체안을 만들지 않으며, 내부 자료를 그대로 복사하지 않는다. "
    "사용자에게는 모든 문장을 '-합니다', '-입니다', '-해요', '-하세요' 형태의 존댓말로 답한다."
)


def record(question: str, answer: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def build() -> list[dict]:
    characters = json.loads((DATA / "characters.json").read_text(encoding="utf-8"))
    rules = json.loads((DATA / "team_rules.json").read_text(encoding="utf-8"))
    by_id = {character["id"]: character for character in characters}
    rows = [
        record("내 보유풀로 파티 짜줘.", "보유 캐릭터와 사용 횟수를 먼저 확인한 뒤, 앱 추천 엔진의 전체 배분 결과를 기준으로 고점 파티부터 정리해 드릴게요."),
        record("최신 캐릭터니까 무조건 좋은 거지?", "그렇지는 않아요. 최신성보다 실제 조합 완성도, 돌파와 전용 무기, 육성 상태를 함께 봐야 합니다. 검증된 조합이 없으면 최신 캐릭터라도 우선 추천하지 않아요."),
        record("모르는 조합도 아무거나 추천해 줘.", "근거 없는 조합은 추천하지 않아요. 현재 메타 룰이나 피해·버프 호환성이 확인되는 조합만 제시하고, 데이터가 부족하면 갱신이 필요하다고 안내할게요."),
        record("방랑자 속성을 여러 개 같이 쓸 수 있어?", "아니요. 방랑자의 속성별 폼은 같은 캐릭터 슬롯을 공유하므로, 한 속성 폼을 사용하면 다른 속성 폼도 같은 사용 가능 횟수에서 차감됩니다."),
        record("점수는 뭘 기준으로 봐?", "조합 완성도를 가장 크게 보고, 최신 메타 가치, 돌파·전용 무기 투자, 실제 육성 상태를 함께 반영합니다. 높은 고정점수만 말하지 않고 항목별 점수도 확인해야 해요."),
        record(
            "현재 추천 데이터가 '파티 A: 별하(딜러) / 은결(서브딜러) / 새봄(서포터), 96점; 파티 B: 해온(딜러) / 여울(서브딜러) / 다온(서포터), 93점'일 때 핵심 서포터 배분을 설명해 줘.",
            "핵심 서포터는 두 곳에 나뉘어요.\n\n- **새봄**은 96점인 별하 / 은결 파티에 배정됩니다.\n- **다온**은 93점인 해온 / 여울 파티를 완성합니다.\n\n두 파티 모두 서포터를 겹치지 않게 써서 고점 조합을 유지하는 배분이에요.",
        ),
        record("파티 나열 순서만 보고 역할을 정해도 돼?", "아니요. 나열 순서가 아니라 제공된 캐릭터 역할 데이터를 따라야 해요. 서포터 배분을 물었다면 역할이 서포터인 멤버와 그 배정 파티만 간결하게 설명하면 됩니다."),
    ]
    for character in characters:
        profile = rules.get("profiles", {}).get(character["id"], {})
        damage = ", ".join(profile.get("damage", [])) or character["element_ko"]
        provides = ", ".join(profile.get("provides", []))
        detail = f"{character['name_ko']}은(는) {character['element_ko']} 속성 {character['weapon_ko']} 캐릭터이며 역할은 {character['role']}입니다. 주요 피해·조합 태그는 {damage}입니다."
        if provides:
            detail += f" 제공하는 핵심 조건은 {provides}입니다."
        rows.extend([
            record(f"{character['name_ko']} 기본 정보를 알려줘.", detail),
            record(f"{character['name_ko']}은 어떤 조합 조건을 봐야 해?", detail + " 실제 추천은 보유풀과 육성 상태를 넣어 계산한 결과를 우선하세요."),
        ])
    for template in rules.get("templates", []):
        names = [by_id.get(cid, {"name_ko": cid})["name_ko"] for cid in template["members"]]
        joined = " / ".join(names)
        tags = ", ".join(template.get("tags", []))
        answer = f"{joined} 조합은 '{template['label']}'로 등록된 {template.get('tier', '검증')} 조합입니다. 기준점수는 {template.get('score')}이며 핵심 태그는 {tags}입니다. 실제 계정 추천에서는 육성과 사용 횟수까지 반영합니다."
        rows.extend([
            record(f"{names[0]} 파티 하나 추천해 줘.", answer),
            record(f"{joined} 조합은 어때?", answer),
        ])
    return rows


def main() -> None:
    rows = build()
    random.Random(20260921).shuffle(rows)
    train_end = int(len(rows) * 0.82)
    valid_end = int(len(rows) * 0.91)
    splits = {
        "train.jsonl": rows[:train_end],
        "valid.jsonl": rows[train_end:valid_end],
        "test.jsonl": rows[valid_end:],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, items in splits.items():
        path = OUTPUT / filename
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
        print(f"{filename}: {len(items)} examples")


if __name__ == "__main__":
    main()
