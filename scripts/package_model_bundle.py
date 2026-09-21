"""Create one uploadable runtime bundle for Google Drive or other storage.

The archive contains only what another Mac needs for inference: the visible
MLX 4-bit base checkpoint and the trained MLX LoRA adapter. Training datasets,
runs, W&B logs, roster data, and secrets are deliberately excluded.
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
MODEL = LOCAL_AI / "models" / "qwen3-4b-instruct-2507-mlx-4bit"
ADAPTER = LOCAL_AI / "adapters" / "qwen3-4b-mlx"
OUTPUT = LOCAL_AI / "dist" / "resonance-qwen3-4b-mlx-runtime.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive 업로드용 MLX 모델+LoRA 번들 생성")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    required = [MODEL / "config.json", MODEL / "model.safetensors", ADAPTER / "adapter_config.json", ADAPTER / "adapters.safetensors"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("번들에 필요한 파일이 없습니다:\n- " + "\n- ".join(missing))

    files = sorted(path for folder in (MODEL, ADAPTER) for path in folder.rglob("*") if path.is_file() and ".cache" not in path.parts)
    manifest = {
        "format": 1,
        "model": "mlx-community/Qwen3-4B-Instruct-2507-4bit",
        "model_source": "https://huggingface.co/mlx-community/Qwen3-4B-Instruct-2507-4bit",
        "base_model": "Qwen/Qwen3-4B-Instruct-2507",
        "license": "Apache-2.0",
        "adapter": "resonance-lab-qwen3-4b-mlx-lora",
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
    print(f"\n[done] {output}\nGoogle Drive에는 이 ZIP 파일 하나만 업로드하세요.")


if __name__ == "__main__":
    main()
