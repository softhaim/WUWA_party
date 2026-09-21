"""Windows/Linux NVIDIA CUDA용 Qwen3 4B QLoRA 학습기.

MLX는 Apple Silicon 전용이므로 CUDA에서는 같은 JSONL 데이터로
Transformers + bitsandbytes(4-bit NF4) + PEFT LoRA를 사용합니다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "local_ai" / "configs" / "cuda_qwen3_4b.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="NVIDIA CUDA용 Qwen3 4B QLoRA 학습")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU를 찾지 못했습니다. 이 파일은 Windows/Linux NVIDIA 환경용입니다.")
    tokenizer = AutoTokenizer.from_pretrained(config["base_model"], use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        config["base_model"], quantization_config=quantization, device_map="auto"
    )
    model = prepare_model_for_kbit_training(model)
    peft_config = LoraConfig(
        r=config["lora_rank"],
        lora_alpha=config["lora_alpha"],
        lora_dropout=config["lora_dropout"],
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )
    # PEFT replaces the selected frozen linear layers with trainable low-rank
    # matrices. The 4-bit base weights remain frozen and are never duplicated.
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    dataset = load_dataset(
        "json",
        data_files={name: str(ROOT / "local_ai" / "dataset" / f"{name}.jsonl") for name in ("train", "validation", "test")},
    )

    def tokenize(batch: dict) -> dict:
        texts = [tokenizer.apply_chat_template(messages, tokenize=False) for messages in batch["messages"]]
        return tokenizer(texts, truncation=True, max_length=config["max_length"])

    tokenized = dataset.map(tokenize, batched=True, remove_columns=["messages"])
    output = ROOT / config["output_dir"]
    training = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=config["epochs"],
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        learning_rate=config["learning_rate"],
        eval_strategy="steps",
        eval_steps=10,
        logging_steps=2,
        save_steps=10,
        load_best_model_at_end=True,
        report_to=[],
        run_name="resonance-lab-qwen3-4b-cuda",
        bf16=torch.cuda.is_bf16_supported(),
        fp16=not torch.cuda.is_bf16_supported(),
        seed=config["seed"],
    )
    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    trainer.train()
    metrics = trainer.evaluate(tokenized["test"], metric_key_prefix="test")
    trainer.save_model(str(output))
    (output / "test_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"CUDA LoRA adapter saved to {output}")


if __name__ == "__main__":
    main()
