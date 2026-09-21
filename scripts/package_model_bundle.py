"""Create an MLX, Transformers, or universal runtime bundle.

Training datasets, run logs, roster data, virtual environments, and secrets are
deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "local_ai"
RUNTIMES = {
    "mlx": (
        LOCAL_AI / "models" / "qwen3-4b-instruct-2507-mlx-4bit",
        LOCAL_AI / "adapters" / "qwen3-4b-mlx",
    ),
    "transformers": (
        LOCAL_AI / "models" / "qwen3-4b-instruct-2507-hf",
        LOCAL_AI / "adapters" / "qwen3-4b-cuda",
    ),
}
OUTPUT = LOCAL_AI / "dist" / "resonance-qwen3-4b-runtime.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive 업로드용 모델+LoRA 번들 생성")
    parser.add_argument("--runtime", choices=("auto", "mlx", "transformers", "universal"), default="auto")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    available = {}
    for name, (model, adapter) in RUNTIMES.items():
        adapter_weight = "adapters.safetensors" if name == "mlx" else "adapter_model.safetensors"
        if (model / "config.json").is_file() and (adapter / "adapter_config.json").is_file() and (adapter / adapter_weight).is_file():
            available[name] = (model, adapter)
    if args.runtime == "universal":
        selected = ["mlx", "transformers"]
    elif args.runtime == "auto":
        selected = list(available)
    else:
        selected = [args.runtime]
    missing = [name for name in selected if name not in available]
    if missing or not selected:
        raise SystemExit(
            "요청한 런타임 파일이 없습니다: " + ", ".join(missing or ["mlx/transformers"])
            + "\nscripts/download_local_model.py --backend all 로 필요한 기본 모델을 준비하세요."
        )
    folders = [folder for name in selected for folder in RUNTIMES[name]]
    files = sorted({path for folder in folders for path in folder.rglob("*") if path.is_file() and ".cache" not in path.parts})
    manifest = {
        "format": 2,
        "runtimes": selected,
        "model_sources": {
            "mlx": "https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit",
            "transformers": "https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507",
        },
        "base_model": "Qwen/Qwen3-4B-Instruct-2507",
        "license": "Apache-2.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {str(path.relative_to(LOCAL_AI)): sha256(path) for path in files},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # The safetensors file is already densely encoded; ZIP_STORED avoids a long,
    # mostly useless recompression pass and supports files larger than 2 GB.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        archive.writestr("bundle-manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in files:
            relative = path.relative_to(LOCAL_AI)
            print(f"[add] {relative}")
            archive.write(path, relative.as_posix())
    print(f"\n[done] {output}\n[runtimes] {', '.join(selected)}")


if __name__ == "__main__":
    main()
