from __future__ import annotations


THRESHOLD = 0.75


def predict(row: dict[str, str]) -> int:
    return int(float(row["x"]) >= THRESHOLD)
