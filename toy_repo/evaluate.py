from __future__ import annotations

import csv
from pathlib import Path

from model import predict


def load_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def score(data_path: str | Path) -> dict[str, object]:
    rows = load_rows(data_path)
    if not rows:
        raise ValueError("evaluation data is empty")
    correct = sum(1 for row in rows if predict(row) == int(row["label"]))
    return {"accuracy": correct / len(rows), "correct": correct, "total": len(rows)}


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(score(sys.argv[1]), indent=2))
