from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from metricguard.hashing import sha256_file

TIMEOUT_SECONDS = 10


def run_trusted_evaluation(candidate_repo: Path) -> dict[str, object]:
    project_root = Path(__file__).resolve().parents[1]
    locked_evaluator = project_root / "toy_repo" / "evaluate.py"
    hidden_data = project_root / "trusted_assets" / "hidden_labels.csv"

    with tempfile.TemporaryDirectory(prefix="metricguard-trusted-") as tmp:
        workdir = Path(tmp) / "candidate"
        shutil.copytree(candidate_repo, workdir)
        shutil.copy2(locked_evaluator, workdir / "evaluate.py")

        code = f'''
import json
import sys
sys.path.insert(0, {str(workdir)!r})
import evaluate
metrics = evaluate.score({str(hidden_data)!r})
print(json.dumps(metrics))
'''
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-c", code],
            text=True,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            env=env,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "trusted evaluation failed: "
                + (completed.stderr.strip() or completed.stdout.strip() or str(completed.returncode))
            )
        metrics = json.loads(completed.stdout)
        metrics["evaluator_hash"] = sha256_file(locked_evaluator)
        return metrics
