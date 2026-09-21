"""Convert this project's MLX LoRA weights into PEFT's adapter format.

MLX stores LoRA matrices as (input, rank) and (rank, output), while PEFT
expects (rank, input) and (output, rank). The conversion therefore transposes
both matrices and renames their keys; it does not retrain or merge the model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "local_ai" / "adapters" / "qwen3-4b-mlx"
DEFAULT_OUTPUT = ROOT / "local_ai" / "adapters" / "qwen3-4b-cuda"


def convert(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT) -> Path:
    from safetensors import safe_open
    from safetensors.numpy import save_file

    source = source.resolve()
    output = output.resolve()
    source_config = json.loads((source / "adapter_config.json").read_text(encoding="utf-8"))
    lora = source_config["lora_parameters"]
    converted = {}
    layers: set[int] = set()
    with safe_open(source / "adapters.safetensors", framework="numpy") as weights:
        for key in weights.keys():
            match = key.split(".")
            if len(match) < 6 or match[-1] not in {"lora_a", "lora_b"}:
                continue
            layer = int(match[2])
            module = match[-2]
            suffix = "lora_A.weight" if match[-1] == "lora_a" else "lora_B.weight"
            peft_key = f"base_model.model.model.layers.{layer}.self_attn.{module}.{suffix}"
            converted[peft_key] = weights.get_tensor(key).T.copy()
            layers.add(layer)
    if not converted:
        raise ValueError(f"변환할 MLX LoRA 가중치가 없습니다: {source}")

    output.mkdir(parents=True, exist_ok=True)
    save_file(converted, output / "adapter_model.safetensors")
    peft_config = {
        "base_model_name_or_path": "Qwen/Qwen3-4B-Instruct-2507",
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "layers_pattern": "layers",
        "layers_to_transform": sorted(layers),
        "lora_alpha": int(lora["scale"]),
        "lora_dropout": float(lora["dropout"]),
        "peft_type": "LORA",
        "r": int(lora["rank"]),
        "target_modules": [key.rsplit(".", 1)[-1] for key in lora["keys"]],
        "task_type": "CAUSAL_LM",
    }
    (output / "adapter_config.json").write_text(
        json.dumps(peft_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="MLX LoRA를 Transformers PEFT 형식으로 변환")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(f"[done] PEFT adapter: {convert(args.source, args.output)}")


if __name__ == "__main__":
    main()
