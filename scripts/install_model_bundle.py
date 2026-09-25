"""Validate and install a downloaded Google Drive runtime ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_AI = ROOT / "local_ai"
DEFAULT_BUNDLE_DIR = LOCAL_AI / "bundles"
DEFAULT_BUNDLE_NAMES = (
    "resonance-qwen3-4b-runtime.zip",
    "resonance-qwen3-4b-mlx-runtime.zip",
)
ALLOWED_ROOTS = {"models", "adapters"}


def adapter_iterations(adapter: Path) -> int:
    """Return the training step count used for a bundled/deployed MLX adapter."""
    try:
        return int(json.loads((adapter / "adapter_config.json").read_text(encoding="utf-8")).get("iters", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def auto_backend() -> str:
    apple = platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}
    return "mlx" if apple else "transformers"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_bundle(value: Path | None) -> Path:
    """Resolve an explicit ZIP or discover one in local_ai/bundles/."""
    if value is not None:
        return value.expanduser().resolve()
    for name in DEFAULT_BUNDLE_NAMES:
        candidate = DEFAULT_BUNDLE_DIR / name
        if candidate.is_file():
            return candidate.resolve()
    candidates = sorted(DEFAULT_BUNDLE_DIR.glob("*.zip"))
    if len(candidates) == 1:
        return candidates[0].resolve()
    if len(candidates) > 1:
        names = "\n- ".join(path.name for path in candidates)
        raise SystemExit(
            "모델 ZIP이 여러 개라 자동 선택할 수 없어요. 사용할 ZIP 경로를 명령 뒤에 적어 주세요:\n- " + names
        )
    raise SystemExit(
        "모델 ZIP을 찾지 못했어요. 다운로드한 ZIP을 다음 폴더에 넣고 다시 실행해 주세요:\n"
        f"{DEFAULT_BUNDLE_DIR}\n"
        "또는 python scripts/install_model_bundle.py <ZIP 경로> 형식으로 실행할 수 있어요."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Drive에서 받은 로컬 모델 번들 설치")
    parser.add_argument(
        "bundle",
        type=Path,
        nargs="?",
        help="ZIP 경로. 생략하면 local_ai/bundles/에서 자동으로 찾음",
    )
    parser.add_argument("--backend", choices=("auto", "mlx", "transformers", "all"), default="auto")
    parser.add_argument("--no-download", action="store_true", help="번들에 현재 플랫폼 기본 모델이 없어도 자동 다운로드하지 않음")
    args = parser.parse_args()
    bundle = find_bundle(args.bundle)
    if not bundle.is_file():
        raise SystemExit(f"번들을 찾을 수 없습니다: {bundle}")
    print(f"[bundle] {bundle}")

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
            bundled_mlx = adapter_source / "qwen3-4b-mlx"
            deployed_mlx = LOCAL_AI / "adapters" / "qwen3-4b-mlx"
            if adapter_iterations(deployed_mlx) > adapter_iterations(bundled_mlx):
                print("[adapter] ZIP보다 새 학습 어댑터가 이미 있어 기존 파일을 유지합니다.")
            else:
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
    required_models = {
        "mlx": LOCAL_AI / "models" / "qwen3-4b-instruct-2507-mlx-4bit" / "config.json",
        "transformers": LOCAL_AI / "models" / "qwen3-4b-instruct-2507-hf" / "config.json",
    }
    required = list(required_models) if selected == "all" else [selected]
    missing_models = [backend for backend in required if not required_models[backend].is_file()]
    if missing_models and not args.no_download:
        backend = "all" if len(missing_models) > 1 else missing_models[0]
        print(f"[download] 번들에 없는 {backend} 기본 모델을 Hugging Face에서 준비합니다.")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "download_local_model.py"), "--backend", backend],
            cwd=ROOT,
            check=True,
        )
    elif missing_models:
        print("[note] 기본 모델이 없습니다: " + ", ".join(missing_models))
    print(f"[done] {selected}용 모델과 LoRA 어댑터를 local_ai/ 아래에 설치했습니다.")


if __name__ == "__main__":
    main()
