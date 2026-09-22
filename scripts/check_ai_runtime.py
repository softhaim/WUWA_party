"""Print a compact GPU diagnostic without loading the model weights."""

from __future__ import annotations

import importlib.metadata
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_chatbot import PEFT_ADAPTER, TRANSFORMERS_MODEL, transformers_runtime_info  # noqa: E402


def version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def main() -> None:
    runtime = transformers_runtime_info()
    bnb_import_error = None
    bnb_cuda_binary = None
    if runtime.get("bitsandbytes_installed"):
        try:
            importlib.import_module("bitsandbytes")
            try:
                bnb_extension = importlib.import_module("bitsandbytes.cextension")
                bnb_cuda_binary = getattr(getattr(bnb_extension, "lib", None), "compiled_with_cuda", None)
            except Exception:
                # Some releases do not expose this internal flag; a successful
                # public import is still useful and model loading performs the final check.
                pass
        except Exception as exc:  # pragma: no cover - depends on vendor DLLs.
            bnb_import_error = str(exc)
    report = {
        "python": sys.version.split()[0],
        "torch": version("torch"),
        "torch_cuda_build": runtime.get("cuda_build"),
        "cuda_available": runtime.get("cuda_available"),
        "gpu_count": runtime.get("gpu_count"),
        "gpu_name": runtime.get("gpu_name"),
        "transformers": version("transformers"),
        "accelerate": version("accelerate"),
        "bitsandbytes": version("bitsandbytes"),
        "bitsandbytes_import_error": bnb_import_error,
        "bitsandbytes_cuda_binary": bnb_cuda_binary,
        "peft": version("peft"),
        "base_model": (TRANSFORMERS_MODEL / "config.json").is_file(),
        "peft_adapter": (PEFT_ADAPTER / "adapter_model.safetensors").is_file(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["cuda_available"]:
        print("\n[fix] 현재 Python의 PyTorch가 CUDA를 사용하지 못해요. README의 Windows CUDA 설치 단계를 확인해 주세요.")
        raise SystemExit(1)
    if report["bitsandbytes"] == "not installed" or bnb_import_error:
        print("\n[fix] python -m pip install -r requirements-ai-transformers.txt")
        raise SystemExit(1)
    print("\n[ok] CUDA 4-bit 추론 준비가 확인됐어요.")


if __name__ == "__main__":
    main()
