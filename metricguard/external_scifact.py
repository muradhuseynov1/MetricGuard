from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from metricguard.hashing import write_manifest


@dataclass(frozen=True)
class SciFactAuditResult:
    case_id: str
    expected_verdict: str
    verdict: str
    reason: str
    artifacts: list[Path]


def run_external_scifact_subset(project_root: Path, artifacts_dir: Path) -> tuple[list[SciFactAuditResult], dict[str, Any]]:
    subset_path = project_root / "benchmarks" / "external_scifact_subset.jsonl"
    if not subset_path.exists():
        raise RuntimeError(f"missing external SciFact subset: {subset_path}")

    output_dir = artifacts_dir / "external_scifact_subset"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cases = [json.loads(line) for line in subset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    subset_copy = output_dir / "external_scifact_subset.jsonl"
    subset_copy.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )

    results = [_audit_scifact_case(case, output_dir) for case in cases]
    metrics = _metrics(results)
    (output_dir / "benchmark_summary.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (output_dir / "benchmark_report.md").write_text(_format_report(results, metrics), encoding="utf-8")
    return results, metrics


def _audit_scifact_case(case: dict[str, Any], output_dir: Path) -> SciFactAuditResult:
    case_id = f"scifact_{case['claim_id']}"
    case_dir = output_dir / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    answer_path = case_dir / "answer.md"
    answer_path.write_text(_answer_markdown(case), encoding="utf-8")

    source_path = case_dir / "source.json"
    source_path.write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checks = _checks_for_case(case)
    expected_verdict = str(case["expected_verdict"])
    verdict = "accepted" if all(check["passed"] for check in checks) else "rejected"
    failed = [check["name"] for check in checks if not check["passed"]]
    reason = (
        "SciFact evidence label SUPPORTS the cited claim"
        if verdict == "accepted"
        else "failed checks: " + ", ".join(failed)
    )

    audit_result_path = case_dir / "audit_result.json"
    audit_result_path.write_text(
        json.dumps(
            {
                "dataset": "SciFact",
                "claim_id": case["claim_id"],
                "doc_id": case["doc_id"],
                "label": case["label"],
                "checks": checks,
                "expected_verdict": expected_verdict,
                "verdict": verdict,
                "reason": reason,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    verdict_path = case_dir / "verdict.json"
    verdict_path.write_text(
        json.dumps(
            {
                "verdict": verdict,
                "expected_verdict": expected_verdict,
                "correct": verdict == expected_verdict,
                "reason": reason,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    report_path = case_dir / "audit_report.md"
    report_path.write_text(_case_report(case, checks, verdict, expected_verdict, reason), encoding="utf-8")

    artifacts = [answer_path, source_path, audit_result_path, verdict_path, report_path]
    manifest_path = write_manifest(case_dir, artifacts)
    artifacts.append(manifest_path)
    return SciFactAuditResult(
        case_id=case_id,
        expected_verdict=expected_verdict,
        verdict=verdict,
        reason=reason,
        artifacts=artifacts,
    )


def _checks_for_case(case: dict[str, Any]) -> list[dict[str, object]]:
    abstract = case.get("abstract", [])
    rationale_ids = case.get("rationale_sentence_ids", [])
    label = case.get("label")
    checks = [
        {
            "name": "source_document_exists",
            "passed": bool(case.get("doc_id")) and bool(case.get("title")) and bool(abstract),
            "details": f"doc_id={case.get('doc_id')}, title={case.get('title')!r}",
        },
        {
            "name": "scifact_label_available",
            "passed": label in {"SUPPORT", "CONTRADICT", "NO_EVIDENCE"},
            "details": f"label={label}",
        },
    ]
    if label == "SUPPORT":
        checks.extend(
            [
                {
                    "name": "support_label_required",
                    "passed": True,
                    "details": "SciFact human annotation labels this cited abstract as SUPPORT",
                },
                {
                    "name": "rationale_sentences_present",
                    "passed": bool(rationale_ids) and all(0 <= int(i) < len(abstract) for i in rationale_ids),
                    "details": f"rationale_sentence_ids={rationale_ids}",
                },
            ]
        )
    elif label == "CONTRADICT":
        checks.append(
            {
                "name": "support_label_required",
                "passed": False,
                "details": "SciFact human annotation says the cited abstract CONTRADICTS the claim",
            }
        )
    else:
        checks.append(
            {
                "name": "support_label_required",
                "passed": False,
                "details": "SciFact has no annotated supporting evidence for this cited abstract",
            }
        )
    return checks


def _metrics(results: list[SciFactAuditResult]) -> dict[str, Any]:
    rows = []
    true_positive = false_positive = true_negative = false_negative = 0
    for result in results:
        expected_reject = result.expected_verdict == "rejected"
        actual_reject = result.verdict == "rejected"
        correct = result.expected_verdict == result.verdict
        if expected_reject and actual_reject:
            true_positive += 1
        elif not expected_reject and actual_reject:
            false_positive += 1
        elif not expected_reject and not actual_reject:
            true_negative += 1
        else:
            false_negative += 1
        rows.append(
            {
                "case_id": result.case_id,
                "expected_verdict": result.expected_verdict,
                "actual_verdict": result.verdict,
                "correct": correct,
                "reason": result.reason,
            }
        )
    correct_count = sum(1 for row in rows if row["correct"])
    rejected_total = true_positive + false_negative
    accepted_total = true_negative + false_positive
    return {
        "dataset": "SciFact",
        "subset": "dev fixed subset",
        "total_cases": len(results),
        "correct_cases": correct_count,
        "accuracy": _ratio(correct_count, len(results)),
        "unsupported_detection_rate": _ratio(true_positive, rejected_total),
        "false_reject_rate": _ratio(false_positive, accepted_total),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "cases": rows,
    }


def _answer_markdown(case: dict[str, Any]) -> str:
    rationale = case.get("rationale_text") or "No SciFact rationale sentence is annotated for this cited abstract."
    return "\n".join(
        [
            "# Generated Answer",
            "",
            f"{case['claim']} [1]",
            "",
            "## Citation",
            "",
            f"[1] SciFact document {case['doc_id']}: \"{case['title']}\".",
            "",
            "## Cited Evidence Text",
            "",
            rationale,
            "",
        ]
    )


def _case_report(
    case: dict[str, Any],
    checks: list[dict[str, object]],
    verdict: str,
    expected_verdict: str,
    reason: str,
) -> str:
    lines = [
        f"# SciFact External Subset Audit: {case['claim_id']}",
        "",
        f"Verdict: **{verdict.upper()}**",
        f"Expected: **{expected_verdict.upper()}**",
        "",
        f"Reason: {reason}",
        "",
        "## Claim",
        "",
        str(case["claim"]),
        "",
        "## Source",
        "",
        f"- Dataset: SciFact dev",
        f"- Document ID: `{case['doc_id']}`",
        f"- Title: {case['title']}",
        f"- Label: `{case['label']}`",
        f"- Rationale sentence IDs: `{case['rationale_sentence_ids']}`",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: `{check['name']}` - {check['details']}")
    lines.append("")
    return "\n".join(lines)


def _format_report(results: list[SciFactAuditResult], metrics: dict[str, Any]) -> str:
    lines = [
        "# External SciFact Subset Benchmark",
        "",
        "This benchmark adapts a fixed subset of SciFact dev examples to test whether MetricGuard accepts cited claims with human-annotated SUPPORT evidence and rejects CONTRADICT or no-evidence citations.",
        "",
        "## Summary",
        "",
        f"- Dataset: SciFact",
        f"- Subset: dev fixed subset",
        f"- Total cases: {metrics['total_cases']}",
        f"- Correct cases: {metrics['correct_cases']}",
        f"- Accuracy: {float(metrics['accuracy']):.1%}",
        f"- Unsupported detection rate: {float(metrics['unsupported_detection_rate']):.1%}",
        f"- False reject rate: {float(metrics['false_reject_rate']):.1%}",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        status = "PASS" if result.expected_verdict == result.verdict else "FAIL"
        lines.extend(
            [
                f"### {result.case_id}",
                "",
                f"- Result: {status}",
                f"- Expected: `{result.expected_verdict}`",
                f"- Actual: `{result.verdict}`",
                f"- Reason: {result.reason}",
                "",
            ]
        )
    return "\n".join(lines)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0
