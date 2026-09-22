"""Pre-download Spine Live2D files into the server's ignored disk cache.

The web app caches a character automatically on first view. Run this helper
when every character should open immediately without that first remote fetch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402 - project root is added before importing app modules.


def main() -> None:
    parser = argparse.ArgumentParser(description="Live2D 모델을 로컬 디스크 캐시에 미리 저장")
    parser.add_argument("--owned", action="store_true", help="현재 보유 캐릭터만 캐시")
    parser.add_argument("--workers", type=int, default=3, help="동시 다운로드 수")
    args = parser.parse_args()
    characters = json.loads((ROOT / "data" / "characters.json").read_text(encoding="utf-8"))
    if args.owned:
        roster = server.get_roster()
        characters = [character for character in characters if roster.get(character["id"], {}).get("owned")]
    print(f"Live2D 캐시 대상: {len(characters)}명 → {server.LIVE2D_CACHE}")
    summary = server.preload_live2d_assets(characters, workers=args.workers)
    print(
        f"완료: {summary['characters']}명 · 새 파일 {summary['downloaded_files']}개 · "
        f"{summary['total_bytes'] / 1024 / 1024:.1f}MB"
    )
    if summary["failures"]:
        raise SystemExit("캐시 실패: " + ", ".join(item["id"] for item in summary["failures"]))


if __name__ == "__main__":
    main()
