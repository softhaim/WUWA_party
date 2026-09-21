"""Shared parsing and report helpers for local training runs."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


TRAIN_RE = re.compile(
    r"Iter (?P<step>\d+): Train loss (?P<loss>[\d.]+), Learning Rate (?P<lr>[\deE+.-]+), .*?Peak mem (?P<memory>[\d.]+) GB"
)
VAL_RE = re.compile(r"Iter (?P<step>\d+): Val loss (?P<loss>[\d.]+)")
NUMBER = r"\d+(?:\.\d+)?"
TEST_RE = re.compile(rf"Test loss (?P<loss>{NUMBER}), Test ppl (?P<ppl>{NUMBER})")


def parse_metric(line: str) -> dict[str, Any] | None:
    """Turn an MLX terminal line into a stable JSON record."""
    if match := TRAIN_RE.search(line):
        return {
            "type": "train",
            "step": int(match["step"]),
            "loss": float(match["loss"]),
            "learning_rate": float(match["lr"]),
            "peak_memory_gb": float(match["memory"]),
        }
    if match := VAL_RE.search(line):
        return {"type": "validation", "step": int(match["step"]), "loss": float(match["loss"])}
    if match := TEST_RE.search(line):
        return {"type": "test", "loss": float(match["loss"]), "perplexity": float(match["ppl"])}
    return None


def read_metrics(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _polyline(values: list[tuple[int, float]], width: int = 760, height: int = 260) -> str:
    if not values:
        return ""
    max_step = max(step for step, _ in values) or 1
    losses = [loss for _, loss in values]
    lo, hi = min(losses), max(losses)
    span = max(hi - lo, 0.1)
    return " ".join(
        f"{35 + step / max_step * (width - 60):.1f},{20 + (hi - loss) / span * (height - 50):.1f}"
        for step, loss in values
    )


def write_html_report(run_dir: Path, manifest: dict[str, Any], metrics: list[dict[str, Any]]) -> None:
    """Write a dependency-free report so loss curves remain viewable without W&B login."""
    train = [(m["step"], m["loss"]) for m in metrics if m["type"] == "train"]
    valid = [(m["step"], m["loss"]) for m in metrics if m["type"] == "validation"]
    test = next((m for m in reversed(metrics) if m["type"] == "test"), None)
    rows = "".join(
        f"<tr><td>{html.escape(m['type'])}</td><td>{m.get('step', '-')}</td><td>{m.get('loss', '-')}</td>"
        f"<td>{m.get('peak_memory_gb', '-')}</td></tr>" for m in metrics
    )
    page = f"""<!doctype html><meta charset='utf-8'><title>Resonance Lab 학습 보고서</title>
<style>body{{margin:40px auto;max-width:920px;background:#0d1117;color:#e6edf3;font:15px system-ui}}h1{{color:#d8ff50}}.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card,svg,table{{background:#151b23;border:1px solid #30363d;border-radius:12px}}.card{{padding:15px 18px;min-width:150px}}svg{{width:100%;margin:20px 0}}polyline{{fill:none;stroke-width:3}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border-bottom:1px solid #30363d;text-align:left}}small{{color:#8b949e}}</style>
<h1>Qwen3 4B QLoRA 학습 보고서</h1><small>{html.escape(str(manifest.get('run_id', '')))}</small>
<div class='cards'><div class='card'>상태<br><b>{html.escape(str(manifest.get('status', 'unknown')))}</b></div><div class='card'>마지막 train loss<br><b>{train[-1][1] if train else '-'}</b></div><div class='card'>최저 val loss<br><b>{min((x[1] for x in valid), default='-')}</b></div><div class='card'>test loss / PPL<br><b>{f"{test['loss']} / {test['perplexity']}" if test else '-'}</b></div></div>
<svg viewBox='0 0 760 260' role='img' aria-label='loss curve'><line x1='35' y1='230' x2='735' y2='230' stroke='#53606d'/><polyline points='{_polyline(train)}' stroke='#d8ff50'/><polyline points='{_polyline(valid)}' stroke='#69b7ff'/><text x='45' y='250' fill='#8b949e'>초록 train · 파랑 validation</text></svg>
<table><thead><tr><th>구분</th><th>step</th><th>loss</th><th>peak GB</th></tr></thead><tbody>{rows}</tbody></table>"""
    (run_dir / "report.html").write_text(page, encoding="utf-8")
