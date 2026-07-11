from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS_PATH = ROOT / "data" / "characters.json"


def fetch(url: str, *, timeout: int = 12) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ResonanceLab/0.1 live2d checker"})
    with urllib.request.urlopen(request, timeout=timeout, context=ssl._create_unverified_context()) as response:
        return response.read()


def atlas_pages(text: str) -> list[str]:
    pages: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or ":" in line:
            continue
        if line.endswith((".png", ".webp", ".jpg", ".jpeg")):
            pages.append(line)
    return pages


def check(character: dict) -> tuple[bool, str]:
    skel = character.get("live2d_skeleton_url") or ""
    atlas = character.get("live2d_atlas_url") or ""
    if not skel or not atlas:
        return False, "missing-url"
    try:
        skel_body = fetch(skel)
        if len(skel_body) < 1024:
            return False, f"tiny-skel:{len(skel_body)}"
    except Exception as exc:  # noqa: BLE001
        return False, f"skel:{type(exc).__name__}:{exc}"
    try:
        atlas_text = fetch(atlas).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return False, f"atlas:{type(exc).__name__}:{exc}"
    pages = atlas_pages(atlas_text)
    if not pages:
        return False, "atlas:no-pages"
    for page in pages:
        texture_url = urljoin(atlas.rsplit("/", 1)[0] + "/", page)
        try:
            body = fetch(texture_url)
            if len(body) < 1024:
                return False, f"tiny-texture:{page}:{len(body)}"
        except Exception as exc:  # noqa: BLE001
            return False, f"texture:{page}:{type(exc).__name__}:{exc}"
    return True, f"ok:{len(pages)} texture(s)"


def main() -> int:
    write = "--write" in sys.argv
    characters = json.loads(CHARACTERS_PATH.read_text(encoding="utf-8"))
    failures: list[tuple[str, str, str]] = []
    ok_count = 0
    for character in characters:
        ok, reason = check(character)
        character["live2d_available"] = ok
        character["live2d_check"] = reason
        if ok:
            ok_count += 1
        else:
            failures.append((character["id"], character["name_ko"], reason))
        print(f"{'OK  ' if ok else 'FAIL'} {character['id']:<20} {character['name_ko']:<10} {reason}")
    print(f"\nLive2D available: {ok_count}/{len(characters)}")
    if failures:
        print("Failures:")
        for character_id, name_ko, reason in failures:
            print(f"- {character_id} ({name_ko}): {reason}")
    if write:
        CHARACTERS_PATH.write_text(json.dumps(characters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nUpdated {CHARACTERS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
