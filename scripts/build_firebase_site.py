#!/usr/bin/env python3
"""Build the small Firebase Hosting artifact without local models or Python runtimes."""

from __future__ import annotations

import json
import shutil
from urllib.parse import urljoin
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "firebase"
STATIC = ROOT / "static"
CLOUD = ROOT / "cloud"
LIVE2D_SOURCE = ROOT / ".cache" / "live2d-assets"
LIVE2D_PREFIX = "https://static.nanoka.cc/assets/ww/"


def public_path(value: str) -> str:
    if value.startswith("static/"):
        return "/" + value.removeprefix("static/")
    return value


def build_characters() -> list[dict]:
    characters = json.loads((ROOT / "data" / "characters.json").read_text(encoding="utf-8"))
    for character in characters:
        for field in ("image", "detail_image", "element_icon", "weapon_icon"):
            character[field] = public_path(character.get(field, ""))
        for field in ("live2d_skeleton_url", "live2d_atlas_url"):
            value = character.get(field, "")
            if character.get("live2d_available", True) is not False and value.startswith(LIVE2D_PREFIX) and LIVE2D_SOURCE.exists():
                character[field] = "/live2d-assets/" + value.removeprefix(LIVE2D_PREFIX)
    return characters


def live2d_manifest(characters: list[dict]) -> dict:
    """Map every character to the local skeleton, atlas and texture files.

    Firebase Hosting already contains these files.  The manifest lets the
    browser warm its HTTP cache in the background instead of waiting for the
    first character click to start several network requests.
    """
    mapping: dict[str, list[str]] = {}
    all_assets: list[str] = []
    for character in characters:
        if character.get("live2d_available", True) is False:
            continue
        skeleton = character.get("live2d_skeleton_url", "")
        atlas = character.get("live2d_atlas_url", "")
        if not skeleton.startswith("/live2d-assets/") or not atlas.startswith("/live2d-assets/"):
            continue
        assets = [skeleton, atlas]
        atlas_path = OUTPUT / atlas.lstrip("/")
        if atlas_path.is_file():
            lines = atlas_path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n")
            for index, line in enumerate(lines):
                value = line.strip()
                following = lines[index + 1].strip() if index + 1 < len(lines) else ""
                previous = lines[index - 1].strip() if index else ""
                if value and not ":" in value and (not previous or index == 0) and following.startswith("size:"):
                    assets.append(urljoin(atlas, value))
        mapping[character["id"]] = list(dict.fromkeys(assets))
        all_assets.extend(assets)
    return {"version": 1, "characters": mapping, "all": list(dict.fromkeys(all_assets))}


def main() -> None:
    cloud_environment = CLOUD / "cloud-env.js"
    if not cloud_environment.is_file():
        raise SystemExit(
            "cloud/cloud-env.js가 없습니다. cloud/cloud-env.example.js를 복사한 뒤 "
            "Firebase 웹 앱 설정을 입력해 주세요."
        )
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    for name in ("characters", "icons", "vendor"):
        shutil.copytree(STATIC / name, OUTPUT / name)
    for name in ("app.js", "styles.css", "service-worker.js"):
        shutil.copy2(STATIC / name, OUTPUT / name)
    for name in ("index.html", "cloud-runtime.js", "cloud-planner.js", "planner-worker.js"):
        shutil.copy2(CLOUD / name, OUTPUT / name)
    shutil.copy2(cloud_environment, OUTPUT / "cloud-env.js")

    data_dir = OUTPUT / "data"
    data_dir.mkdir()
    characters = build_characters()
    (data_dir / "characters.json").write_text(
        json.dumps(characters, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    if LIVE2D_SOURCE.exists():
        shutil.copytree(LIVE2D_SOURCE, OUTPUT / "live2d-assets")
    shutil.copy2(ROOT / "data" / "team_rules.json", data_dir / "team_rules.json")
    (data_dir / "live2d-manifest.json").write_text(
        json.dumps(live2d_manifest(characters), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    files = [path for path in OUTPUT.rglob("*") if path.is_file()]
    executable = [path for path in files if path.stat().st_mode & 0o111]
    for path in executable:
        path.chmod(path.stat().st_mode & ~0o111)
    total = sum(path.stat().st_size for path in files)
    print(f"Firebase site ready: {len(files)} files, {total / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
