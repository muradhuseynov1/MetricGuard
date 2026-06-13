from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from metricguard.citations import LiveCitationConfig, SOURCE_REGISTRY, audit_citation_answer


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    description: str
    expected_verdict: str
    answer: str


@dataclass(frozen=True)
class BenchmarkResult:
    case: BenchmarkCase
    verdict: str
    reason: str
    answer_path: Path
    artifacts: list[Path]


VALID_CITATION = """[1] MetricGuard Demo Team. "MetricGuard Local Citation Audit Fixture." Local
Evidence Fixture, 2026. DOI: 10.0000/metricguard.local.2026
URL: metricguard://sources/local-citation-audit
"""


BENCHMARK_CASES = [
    BenchmarkCase(
        case_id="valid_supported",
        description="Supported answer with matching source metadata.",
        expected_verdict="accepted",
        answer=f"""# Answer

MetricGuard audits generated answers by extracting citations and rejecting
claims when evidence is missing or overclaimed [1].

{VALID_CITATION}""",
    ),
    BenchmarkCase(
        case_id="nonexistent_doi_url",
        description="Fabricated paper, DOI, and URL.",
        expected_verdict="rejected",
        answer="""# Answer

Citation auditing reduces hallucinated references by 91% in agentic workflows
[1].

[1] Nguyen, A. "MetricGuard: Deterministic Citation Gates for AI Research."
Nature Machine Intelligence, 2025. DOI: 10.1038/s42256-025-99999-9
URL: https://example.invalid/metricguard-citation-gates
""",
    ),
    BenchmarkCase(
        case_id="metadata_mismatch",
        description="Resolvable local DOI with wrong title, journal, author, and year.",
        expected_verdict="rejected",
        answer="""# Answer

MetricGuard audits generated answers by extracting citations [1].

[1] Wrong Author. "A Different Citation Audit Paper." Imaginary Journal, 2025.
DOI: 10.0000/metricguard.local.2026
URL: metricguard://sources/local-citation-audit
""",
    ),
    BenchmarkCase(
        case_id="fake_quote",
        description="Resolvable source, but the quoted sentence is not present.",
        expected_verdict="rejected",
        answer=f"""# Answer

The source says "MetricGuard guarantees perfect citation accuracy" [1].

{VALID_CITATION}""",
    ),
    BenchmarkCase(
        case_id="overclaimed_support",
        description="Resolvable source, but the claim overstates what the source supports.",
        expected_verdict="rejected",
        answer=f"""# Answer

MetricGuard eliminates fabricated evidence in every agentic workflow [1].

{VALID_CITATION}""",
    ),
    BenchmarkCase(
        case_id="missing_citation",
        description="Claim has no citation block at all.",
        expected_verdict="rejected",
        answer="""# Answer

MetricGuard audits generated answers by extracting citations and checking
whether sources support claims.
""",
    ),
]


def run_citation_benchmark(
    artifacts_dir: Path,
    live_config: LiveCitationConfig | None = None,
) -> tuple[list[BenchmarkResult], dict[str, object]]:
    benchmark_dir = artifacts_dir / "citation_benchmark"
    if benchmark_dir.exists():
        shutil.rmtree(benchmark_dir)
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    (benchmark_dir / "source_registry.json").write_text(
        json.dumps(SOURCE_REGISTRY, indent=2) + "\n",
        encoding="utf-8",
    )

    results: list[BenchmarkResult] = []
    for case in BENCHMARK_CASES:
        answer_path = benchmark_dir / f"{case.case_id}.md"
        answer_path.write_text(case.answer, encoding="utf-8")
        outcome = audit_citation_answer(
            answer_path=answer_path,
            run_id=f"audit_{case.case_id}",
            citation_dir=benchmark_dir,
            live_config=live_config,
        )
        results.append(
            BenchmarkResult(
                case=case,
                verdict=outcome.verdict,
                reason=outcome.reason,
                answer_path=answer_path,
                artifacts=outcome.artifacts,
            )
        )

    metrics = _benchmark_metrics(results)
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    (benchmark_dir / "benchmark_report.md").write_text(
        _format_benchmark_report(results, metrics),
        encoding="utf-8",
    )
    return results, metrics


def _benchmark_metrics(results: list[BenchmarkResult]) -> dict[str, object]:
    rows = []
    true_positive = false_positive = true_negative = false_negative = 0
    for result in results:
        expected_reject = result.case.expected_verdict == "rejected"
        actual_reject = result.verdict == "rejected"
        correct = result.case.expected_verdict == result.verdict
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
                "case_id": result.case.case_id,
                "expected_verdict": result.case.expected_verdict,
                "actual_verdict": result.verdict,
                "correct": correct,
                "reason": result.reason,
            }
        )

    total = len(results)
    rejected_total = true_positive + false_negative
    accepted_total = true_negative + false_positive
    return {
        "total_cases": total,
        "correct_cases": sum(1 for row in rows if row["correct"]),
        "accuracy": _ratio(sum(1 for row in rows if row["correct"]), total),
        "cheat_detection_rate": _ratio(true_positive, rejected_total),
        "false_reject_rate": _ratio(false_positive, accepted_total),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "true_negative": true_negative,
        "false_negative": false_negative,
        "cases": rows,
    }


def _format_benchmark_report(results: list[BenchmarkResult], metrics: dict[str, object]) -> str:
    lines = [
        "# Citation Integrity Benchmark",
        "",
        "This benchmark tests whether MetricGuard rejects common citation failures while accepting a supported citation.",
        "",
        "## Summary",
        "",
        f"- Total cases: {metrics['total_cases']}",
        f"- Correct cases: {metrics['correct_cases']}",
        f"- Accuracy: {float(metrics['accuracy']):.1%}",
        f"- Cheat detection rate: {float(metrics['cheat_detection_rate']):.1%}",
        f"- False reject rate: {float(metrics['false_reject_rate']):.1%}",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        status = "PASS" if result.case.expected_verdict == result.verdict else "FAIL"
        lines.extend(
            [
                f"### {result.case.case_id}",
                "",
                f"- Result: {status}",
                f"- Description: {result.case.description}",
                f"- Expected: `{result.case.expected_verdict}`",
                f"- Actual: `{result.verdict}`",
                f"- Reason: {result.reason}",
                "",
            ]
        )
    return "\n".join(lines)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
