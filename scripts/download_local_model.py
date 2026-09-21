"""Download the base model required by the current operating system.

The model is intentionally git-ignored because it is about 2.3 GB. Keeping it
under local_ai/models (instead of Hugging Face's hidden cache) makes the runtime
input unambiguous and lets the service work offline after the first download.
"""

from __future__ import annotations

import argparse
import platform
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKENDS = {
    "mlx": (
        "mlx-community/Qwen3-4B-Instruct-2507-4bit",
        ROOT / "local_ai" / "models" / "qwen3-4b-instruct-2507-mlx-4bit",
    ),
    "transformers": (
        "Qwen/Qwen3-4B-Instruct-2507",
        ROOT / "local_ai" / "models" / "qwen3-4b-instruct-2507-hf",
    ),
}


def auto_backend() -> str:
    apple = platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}
    return "mlx" if apple else "transformers"


def main() -> None:
    parser = argparse.ArgumentParser(description="현재 플랫폼용 Qwen3 4B 기본 모델 다운로드")
    parser.add_argument("--backend", choices=("auto", "mlx", "transformers", "all"), default="auto")
    parser.add_argument("--repo", help="단일 백엔드의 Hugging Face 저장소 덮어쓰기")
    parser.add_argument("--output", type=Path, help="단일 백엔드의 저장 경로 덮어쓰기")
    args = parser.parse_args()

    from huggingface_hub import snapshot_download

    selected = ["mlx", "transformers"] if args.backend == "all" else [auto_backend() if args.backend == "auto" else args.backend]
    if len(selected) > 1 and (args.repo or args.output):
        raise SystemExit("--repo와 --output은 단일 백엔드에서만 사용할 수 있습니다.")
    for backend in selected:
        default_repo, default_destination = BACKENDS[backend]
        repo = args.repo or default_repo
        destination = (args.output or default_destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        print(f"[backend] {backend}\n[model  ] {repo}\n[save   ] {destination}")
        snapshot_download(
            repo_id=repo,
            local_dir=destination,
            ignore_patterns=["*.md", ".gitattributes"],
        )
    print("[done] 기본 모델 다운로드 완료")


if __name__ == "__main__":
    main()
