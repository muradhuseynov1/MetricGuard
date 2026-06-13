from __future__ import annotations

import json
from pathlib import Path

from metricguard.trusted_eval import run_trusted_evaluation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOY_REPO = PROJECT_ROOT / "toy_repo"
TRUSTED_ASSETS = PROJECT_ROOT / "trusted_assets"


def trusted_baseline() -> dict[str, object]:
    metrics = run_trusted_evaluation(TOY_REPO)
    baseline_path = PROJECT_ROOT / "artifacts" / "baseline_metrics.json"
    summary_path = PROJECT_ROOT / "artifacts" / "baseline_summary.md"
    baseline_path.parent.mkdir(exist_ok=True)
    baseline_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(
        f"# Baseline\n\nTrusted baseline accuracy: {metrics['accuracy']:.2%}\n",
        encoding="utf-8",
    )
    return metrics
