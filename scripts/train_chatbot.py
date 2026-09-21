"""Run reproducible Qwen3 4B QLoRA training on Apple Silicon.

This wrapper is the single entry point for Mac training. It regenerates the
dataset, creates a timestamped run directory, streams MLX output to both the
terminal and training.log, extracts losses into metrics.jsonl, records W&B
offline by default, evaluates the test split, and promotes the resulting LoRA
adapter to the service directory only after success.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from training_metrics import parse_metric, read_metrics, write_html_report


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "local_ai" / "configs" / "mlx_qwen3_4b.yaml"
MODEL = ROOT / "local_ai" / "models" / "qwen3-4b-instruct-2507-mlx-4bit"
DEPLOY_ADAPTER = ROOT / "local_ai" / "adapters" / "qwen3-4b-mlx"
RUNS = ROOT / "local_ai" / "runs"


def stream(command: list[str], run_dir: Path, env: dict[str, str]) -> int:
    """Stream a child process while preserving raw and machine-readable logs."""
    log_path = run_dir / "training.log"
    metrics_path = run_dir / "metrics.jsonl"
    with log_path.open("a", encoding="utf-8") as log, metrics_path.open("a", encoding="utf-8") as metrics:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
            if record := parse_metric(line):
                metrics.write(json.dumps(record, ensure_ascii=False) + "\n")
                metrics.flush()
        return process.wait()


def finalize(run_dir: Path, manifest: dict, code: int) -> None:
    """Finalize reports and promote only a fully evaluated adapter."""
    manifest["status"] = "completed" if code == 0 else "failed"
    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["exit_code"] = code
    (run_dir / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = read_metrics(run_dir / "metrics.jsonl")
    write_html_report(run_dir, manifest, metrics)
    if code != 0:
        raise SystemExit(code)
    DEPLOY_ADAPTER.mkdir(parents=True, exist_ok=True)
    for filename in ("adapter_config.json", "adapters.safetensors"):
        shutil.copy2(run_dir / "adapter" / filename, DEPLOY_ADAPTER / filename)
    (RUNS / "latest.txt").write_text(manifest["run_id"] + "\n", encoding="utf-8")
    print(f"\n[done] 서비스 어댑터: {DEPLOY_ADAPTER}\n[view] 학습 보고서: {run_dir / 'report.html'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mac MLX용 Qwen3 4B QLoRA 학습")
    parser.add_argument("--wandb-mode", choices=("offline", "online", "disabled"), default="disabled")
    parser.add_argument("--skip-dataset", action="store_true", help="기존 JSONL을 그대로 사용")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--resume-run", help="완료된 학습 실행의 test/보고서/배포만 재개")
    args = parser.parse_args()

    if not MODEL.joinpath("config.json").exists():
        raise SystemExit("기본 모델이 없습니다. 먼저 .venv-ai/bin/python scripts/download_local_model.py 를 실행하세요.")
    if not args.skip_dataset and not args.resume_run:
        subprocess.run([sys.executable, "scripts/build_chat_dataset.py"], cwd=ROOT, check=True)

    cli = str(Path(sys.executable).with_name("mlx_lm.lora"))
    if args.resume_run:
        run_dir = RUNS / args.resume_run
        run_adapter = run_dir / "adapter"
        if not (run_adapter / "adapters.safetensors").exists():
            raise SystemExit(f"재개할 어댑터가 없습니다: {run_adapter}")
        manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        manifest["status"] = "evaluating"
        (run_dir / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        env = os.environ.copy()
        env.update({"WANDB_MODE": "disabled", "PYTHONUNBUFFERED": "1"})
        test_command = [cli, "--model", str(MODEL), "--adapter-path", str(run_adapter), "--data", str(ROOT / "local_ai" / "dataset"), "--test", "--test-batches", "-1", "--batch-size", "1", "--max-seq-length", "512"]
        finalize(run_dir, manifest, stream(test_command, run_dir, env))
        return

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-mlx-qwen3-4b"
    run_dir = RUNS / run_id
    run_adapter = run_dir / "adapter"
    run_dir.mkdir(parents=True)
    # MLX-LM passes adapter_path to wandb.init(dir=...). Create it first so an
    # explicitly enabled W&B run never prints a misleading missing-root warning.
    run_adapter.mkdir(parents=True)
    shutil.copy2(args.config, run_dir / "config.snapshot.yaml")
    manifest = {
        "run_id": run_id,
        "backend": "mlx",
        "base_model": str(MODEL.relative_to(ROOT)),
        "adapter": str(run_adapter.relative_to(ROOT)),
        "dataset": "local_ai/dataset",
        "wandb_mode": args.wandb_mode,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "status": "running",
    }
    manifest_path = run_dir / "run.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    env = os.environ.copy()
    env.update({"WANDB_MODE": args.wandb_mode, "WANDB_DIR": str(run_dir), "PYTHONUNBUFFERED": "1"})
    common = [cli, "--config", str(args.config), "--model", str(MODEL), "--adapter-path", str(run_adapter)]
    if args.wandb_mode != "disabled":
        common += ["--report-to", "wandb", "--project-name", "resonance-lab-local-ai"]
    print(f"\n[run] {run_id}\n[log] {run_dir / 'training.log'}\n[wandb] {args.wandb_mode}\n")
    code = stream(common, run_dir, env)
    if code == 0:
        # Do not reuse the training YAML here because it contains train: true.
        # A standalone test command loads the frozen base + just-trained adapter.
        test_command = [
            cli, "--model", str(MODEL), "--adapter-path", str(run_adapter),
            "--data", str(ROOT / "local_ai" / "dataset"), "--test",
            "--test-batches", "-1", "--batch-size", "1", "--max-seq-length", "512",
        ]
        code = stream(test_command, run_dir, env)

    finalize(run_dir, manifest, code)


if __name__ == "__main__":
    main()
