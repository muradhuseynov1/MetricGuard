from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluate import score


def test_visible_accuracy_is_nonzero() -> None:
    metrics = score(ROOT / "data" / "visible_test.csv")
    assert metrics["accuracy"] >= 0.60
