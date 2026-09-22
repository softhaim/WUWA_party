"""Pre-download Spine Live2D files into the server's ignored disk cache.

The web app caches a character automatically on first view. Run this helper
when every character should open immediately without that first remote fetch.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402 - project root is added before importing app modules.
from scripts.check_live2d_assets import atlas_pages  # noqa: E402


def relative_asset(url: str) -> str:
    prefix = server.LIVE2D_UPSTREAM + "/"
    if not url.startswith(prefix):
        raise ValueError(f"지원하지 않는 Live2D URL: {url}")
    return url.removeprefix(prefix)


def cache_character(character: dict) -> tuple[str, int, int]:
    skeleton_url = character.get("live2d_skeleton_url", "")
    atlas_url = character.get("live2d_atlas_url", "")
    if not skeleton_url or not atlas_url:
        return character["id"], 0, 0
    total_bytes = 0
    downloaded = 0
    skeleton, _, skeleton_cached = server.live2d_asset(relative_asset(skeleton_url))
    atlas, _, atlas_cached = server.live2d_asset(relative_asset(atlas_url))
    total_bytes += len(skeleton) + len(atlas)
    downloaded += int(not skeleton_cached) + int(not atlas_cached)
    atlas_root = atlas_url.rsplit("/", 1)[0] + "/"
    for page in atlas_pages(atlas.decode("utf-8", errors="replace")):
        texture_url = urljoin(atlas_root, page)
        body, _, cached = server.live2d_asset(relative_asset(texture_url))
        total_bytes += len(body)
        downloaded += int(not cached)
    return character["id"], downloaded, total_bytes


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
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(cache_character, character): character for character in characters}
        for future in as_completed(futures):
            character = futures[future]
            try:
                character_id, downloaded, total_bytes = future.result()
                print(f"OK   {character_id:<22} 새 파일 {downloaded}개 · {total_bytes / 1024 / 1024:.1f}MB")
            except Exception as exc:  # noqa: BLE001 - continue and report every failed character.
                failures.append(character["id"])
                print(f"FAIL {character['id']:<22} {exc}")
    if failures:
        raise SystemExit("캐시 실패: " + ", ".join(failures))


if __name__ == "__main__":
    main()
