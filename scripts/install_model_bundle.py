"""Validate and install a downloaded Google Drive runtime ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "local_ai"
ALLOWED_ROOTS = {"models", "adapters"}


def auto_backend() -> str:
    apple = platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}
    return "mlx" if apple else "transformers"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive에서 받은 로컬 모델 번들 설치")
    parser.add_argument("bundle", type=Path, help="resonance-qwen3-4b-mlx-runtime.zip 경로")
    parser.add_argument("--backend", choices=("auto", "mlx", "transformers", "all"), default="auto")
    args = parser.parse_args()
    bundle = args.bundle.expanduser().resolve()
    if not bundle.is_file():
        raise SystemExit(f"번들을 찾을 수 없습니다: {bundle}")

    with tempfile.TemporaryDirectory(prefix="resonance-model-") as temp_name:
        temp = Path(temp_name)
        with zipfile.ZipFile(bundle) as archive:
            names = archive.namelist()
            # Refuse absolute paths and ../ traversal before extracting anything.
            if any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                raise SystemExit("안전하지 않은 ZIP 경로가 포함되어 있습니다.")
            archive.extractall(temp)
        manifest_path = temp / "bundle-manifest.json"
        if not manifest_path.is_file():
            raise SystemExit("bundle-manifest.json이 없는 번들입니다.")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for relative, expected in manifest.get("files", {}).items():
            path = temp / relative
            if Path(relative).parts[0] not in ALLOWED_ROOTS or not path.is_file():
                raise SystemExit(f"허용되지 않거나 누락된 파일입니다: {relative}")
            if sha256(path) != expected:
                raise SystemExit(f"체크섬이 맞지 않습니다: {relative}")
        selected = auto_backend() if args.backend == "auto" else args.backend
        adapter_source = temp / "adapters"
        if adapter_source.exists():
            shutil.copytree(adapter_source, LOCAL_AI / "adapters", dirs_exist_ok=True)
        model_source = temp / "models"
        if model_source.exists():
            for model_dir in model_source.iterdir():
                if not model_dir.is_dir():
                    continue
                is_mlx = "mlx" in model_dir.name
                if selected == "all" or (selected == "mlx" and is_mlx) or (selected == "transformers" and not is_mlx):
                    shutil.copytree(model_dir, LOCAL_AI / "models" / model_dir.name, dirs_exist_ok=True)
    mlx_adapter = LOCAL_AI / "adapters" / "qwen3-4b-mlx"
    peft_adapter = LOCAL_AI / "adapters" / "qwen3-4b-cuda"
    if (mlx_adapter / "adapters.safetensors").exists() and not (peft_adapter / "adapter_model.safetensors").exists():
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from convert_mlx_adapter_to_peft import convert

            convert(mlx_adapter, peft_adapter)
            print("[convert] Windows/Linux용 PEFT 어댑터도 준비했습니다.")
        except ModuleNotFoundError:
            print("[note] safetensors 설치 후 scripts/convert_mlx_adapter_to_peft.py를 실행하면 PEFT 어댑터를 만들 수 있습니다.")
    print(f"[done] {selected}용 모델과 LoRA 어댑터를 local_ai/ 아래에 설치했습니다.")


if __name__ == "__main__":
    main()
