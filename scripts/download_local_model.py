"""Download the MLX base model into a visible project folder.

The model is intentionally git-ignored because it is about 2.3 GB. Keeping it
under local_ai/models (instead of Hugging Face's hidden cache) makes the runtime
input unambiguous and lets the service work offline after the first download.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
DEFAULT_DESTINATION = ROOT / "local_ai" / "models" / "qwen3-4b-instruct-2507-mlx-4bit"


def main() -> None:
    parser = argparse.ArgumentParser(description="Qwen3 4B MLX 4-bit 기본 모델 다운로드")
    parser.add_argument("--repo", default=REPO_ID)
    parser.add_argument("--output", type=Path, default=DEFAULT_DESTINATION)
    args = parser.parse_args()

    from huggingface_hub import snapshot_download

    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    print(f"[model] {args.repo}")
    print(f"[save ] {destination}")
    snapshot_download(
        repo_id=args.repo,
        local_dir=destination,
        ignore_patterns=["*.md", ".gitattributes"],
    )
    print("[done ] 기본 모델 다운로드 완료")


if __name__ == "__main__":
    main()
