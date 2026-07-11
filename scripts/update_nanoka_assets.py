from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS_PATH = ROOT / "data" / "characters.json"
OUTPUT_DIR = ROOT / "static" / "characters" / "nanoka"
HEAD_DIR = OUTPUT_DIR / "head"
PILE_DIR = OUTPUT_DIR / "pile"
ICON_DIR = ROOT / "static" / "icons"
NANOKA_CHARACTER_URL = "https://static.nanoka.cc/ww/3.5/character.json"
NANOKA_CHARACTER_DETAIL_URL = "https://static.nanoka.cc/ww/3.5/en/character/{id}.json"
NANOKA_ASSET_PREFIX = "https://static.nanoka.cc/assets/ww"

ELEMENT_ICON_PATHS = {
    1: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriIce.T_IconElementAttriIce",
    2: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriFire.T_IconElementAttriFire",
    3: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriThunder.T_IconElementAttriThunder",
    4: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriWind.T_IconElementAttriWind",
    5: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriLight.T_IconElementAttriLight",
    6: "/Game/Aki/UI/UIResources/Common/Image/IconElementAttri/T_IconElementAttriDark.T_IconElementAttriDark",
}

WEAPON_NAMES = {
    1: "대검",
    2: "직검",
    3: "권총",
    4: "권갑",
    5: "증폭기",
}

WEAPON_ICON_KEYS = {
    1: "Knife",
    2: "Sword",
    3: "Gun",
    4: "Fist",
    5: "Magic",
}

WEAPON_SVG = {
    1: ("M7 5 L17 15 M11 4 L20 13 L17 16 L8 7 Z", "대검"),
    2: ("M12 3 L15 6 L7 18 L4 20 L6 17 Z", "직검"),
    3: ("M4 8 H16 L20 11 L17 14 H11 L9 18 H6 L7 14 H4 Z", "권총"),
    4: ("M6 9 L10 5 H15 L19 9 L17 18 H7 Z", "권갑"),
    5: ("M12 3 A7 7 0 1 1 12 21 A7 7 0 1 1 12 3 M12 7 V17 M7 12 H17", "증폭기"),
}

CHARACTER_ALIASES = {
    "sanhua": "Sanhua",
    "baizhi": "Baizhi",
    "lingyang": "Lingyang",
    "zhezhi": "Zhezhi",
    "youhu": "Youhu",
    "carlotta": "Carlotta",
    "lucilla": "Lucilla",
    "hiyuki": "Hiyuki",
    "chixia": "Chixia",
    "encore": "Encore",
    "mortefi": "Mortefi",
    "changli": "Changli",
    "brant": "Brant",
    "lupa": "Lupa",
    "galbrena": "Galbrena",
    "mornye": "Mornye",
    "aemeath": "Aemeath",
    "denia": "Denia",
    "calcharo": "Calcharo",
    "yinlin": "Yinlin",
    "yuanwu": "Yuanwu",
    "xiangli-yao": "Xiangli Yao",
    "lumi": "Lumi",
    "rover-electro": "Rover: Electro",
    "augusta": "Augusta",
    "buling": "Buling",
    "rebecca": "Rebecca",
    "yangyang": "Yangyang",
    "aalto": "Aalto",
    "jiyan": "Jiyan",
    "jianxin": "Jianxin",
    "ciaccona": "Ciaccona",
    "rover-aero": "Rover: Aero",
    "cartethyia": "Cartethyia",
    "iuno": "Iuno",
    "qiuyuan": "Qiuyuan",
    "sigrika": "Sigrika",
    "verina": "Verina",
    "rover-spectro": "Rover: Spectro",
    "jinhsi": "Jinhsi",
    "shorekeeper": "Shorekeeper",
    "phoebe": "Phoebe",
    "zani": "Zani",
    "lynae": "Lynae",
    "luuk-herssen": "Luuk Herssen",
    "lucy": "Lucy",
    "taoqi": "Taoqi",
    "danjin": "Danjin",
    "camellya": "Camellya",
    "rover-havoc": "Rover: Havoc",
    "roccia": "Roccia",
    "cantarella": "Cantarella",
    "phrolova": "Phrolova",
    "chisa": "Chisa",
    "yangyang-xuanling": "Yangyang: Xuanling",
    "suisui": "Suisui",
}


def nanoka_asset_url(unreal_path: str) -> str:
    normalized = str(unreal_path or "")
    if normalized.startswith(("http://", "https://")):
        return normalized
    asset_path = normalized.replace("/Game/Aki/UI/", "").split(".")[0]
    return f"{NANOKA_ASSET_PREFIX}/{asset_path}.webp"


def nanoka_spine_base(unreal_path: str) -> str:
    normalized = str(unreal_path or "")
    if not normalized:
        return ""
    if normalized.startswith(("http://", "https://")):
        return normalized.rsplit(".", 1)[0]
    if "/Spine/Portraits/" in normalized:
        asset_path = normalized.replace(
            "/Game/Aki/UI/UIResources/Common/Spine/Portraits",
            "portraits",
        ).split(".")[0]
        return f"{NANOKA_ASSET_PREFIX}/{asset_path}"
    return f"{NANOKA_ASSET_PREFIX}/{normalized.replace('/Game/Aki/UI/', '').split('.')[0]}"


def find_spine_sources(payload: object) -> tuple[str, str]:
    if isinstance(payload, dict):
        skel = payload.get("formation_spine_skel")
        atlas = payload.get("formation_spine_atlas")
        if skel and atlas:
            return str(skel), str(atlas)
        for value in payload.values():
            found = find_spine_sources(value)
            if found != ("", ""):
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_spine_sources(value)
            if found != ("", ""):
                return found
    return "", ""


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "ResonanceLab/0.1 asset updater"})
    with urllib.request.urlopen(request, timeout=30, context=ssl._create_unverified_context()) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "ResonanceLab/0.1 asset updater"})
    with urllib.request.urlopen(request, timeout=30, context=ssl._create_unverified_context()) as response:
        target.write_bytes(response.read())


def download_optional(url: str, target: Path) -> bool:
    try:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            download(url, target)
        return True
    except Exception as exc:  # noqa: BLE001 - asset updater should keep going and report.
        print(f"warning: failed to download {url}: {exc}")
        return False


def write_weapon_svg(weapon_id: int, target: Path) -> None:
    path, label = WEAPON_SVG[weapon_id]
    target.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" role="img" aria-label="{label}">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#eef7c6"/><stop offset="1" stop-color="#d7f35c"/></linearGradient></defs>
  <circle cx="12" cy="12" r="10.2" fill="#151b20" stroke="#6f7b45" stroke-width="1.2"/>
  <path d="{path}" fill="none" stroke="url(#g)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
""",
        encoding="utf-8",
    )


def main() -> None:
    characters = json.loads(CHARACTERS_PATH.read_text(encoding="utf-8"))
    nanoka = fetch_json(NANOKA_CHARACTER_URL)
    by_en = {entry["en"].lower(): entry for entry in nanoka.values()}
    HEAD_DIR.mkdir(parents=True, exist_ok=True)
    PILE_DIR.mkdir(parents=True, exist_ok=True)
    (ICON_DIR / "elements").mkdir(parents=True, exist_ok=True)
    (ICON_DIR / "weapons").mkdir(parents=True, exist_ok=True)

    for element_id, unreal_path in ELEMENT_ICON_PATHS.items():
        download_optional(nanoka_asset_url(unreal_path), ICON_DIR / "elements" / f"{element_id}.webp")
    for weapon_id in WEAPON_NAMES:
        webp_path = ICON_DIR / "weapons" / f"{weapon_id}.webp"
        svg_path = ICON_DIR / "weapons" / f"{weapon_id}.svg"
        if not download_optional(f"{NANOKA_ASSET_PREFIX}/Static/SP_IconNor{WEAPON_ICON_KEYS[weapon_id]}.webp", webp_path):
            write_weapon_svg(weapon_id, svg_path)

    missing: list[str] = []
    downloaded = 0
    for character in characters:
        alias = CHARACTER_ALIASES.get(character["id"], character["name"])
        entry = by_en.get(alias.lower())
        if not entry:
            missing.append(f"{character['id']} ({alias})")
            continue

        nanoka_id = next(key for key, value in nanoka.items() if value is entry)
        icon_url = nanoka_asset_url(entry["icon"])
        background_url = nanoka_asset_url(entry["background"])
        icon_extension = Path(urlparse(icon_url).path).suffix or ".webp"
        background_extension = Path(urlparse(background_url).path).suffix or ".webp"
        head_path = HEAD_DIR / f"{character['id']}{icon_extension}"
        pile_path = PILE_DIR / f"{character['id']}{background_extension}"
        if download_optional(icon_url, head_path):
            downloaded += 1
        download_optional(background_url, pile_path)

        try:
            detail = fetch_json(NANOKA_CHARACTER_DETAIL_URL.format(id=nanoka_id))
        except Exception as exc:  # noqa: BLE001
            print(f"warning: failed to fetch detail for {character['id']} ({nanoka_id}): {exc}")
            detail = {}
        spine_skel, spine_atlas = find_spine_sources(detail)

        character["image"] = str(head_path.relative_to(ROOT))
        character["detail_image"] = str(pile_path.relative_to(ROOT))
        character["element_icon"] = str((ICON_DIR / "elements" / f"{entry['element']}.webp").relative_to(ROOT))
        weapon_webp = ICON_DIR / "weapons" / f"{entry['weapon']}.webp"
        weapon_svg = ICON_DIR / "weapons" / f"{entry['weapon']}.svg"
        character["weapon_icon"] = str((weapon_webp if weapon_webp.exists() else weapon_svg).relative_to(ROOT))
        character["nanoka_id"] = nanoka_id
        character["nanoka_icon_source"] = icon_url
        character["nanoka_source"] = background_url
        character["live2d_skeleton_source"] = spine_skel
        character["live2d_atlas_source"] = spine_atlas
        character["live2d_skeleton_url"] = f"{nanoka_spine_base(spine_skel)}.skel" if spine_skel else ""
        character["live2d_atlas_url"] = f"{nanoka_spine_base(spine_atlas)}.atlas" if spine_atlas else ""
        character["live2d_source"] = character["live2d_skeleton_url"]

    if missing:
        raise SystemExit(f"Missing nanoka mapping: {', '.join(missing)}")

    CHARACTERS_PATH.write_text(
        json.dumps(characters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Downloaded {downloaded} nanoka character assets into {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
