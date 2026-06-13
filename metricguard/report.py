from __future__ import annotations

from pathlib import Path

from metricguard.blue import Proposal


def write_audit_report(
    *,
    audit_dir: Path,
    proposal: Proposal,
    checks: list[dict[str, object]],
    trusted_metrics: dict[str, object],
    verdict: str,
    reason: str,
) -> Path:
    lines = [
        f"# MetricGuard Audit Report: {proposal.scenario}",
        "",
        f"Verdict: **{verdict.upper()}**",
        "",
        f"Reason: {reason}",
        "",
        "## Claim",
        "",
        f"- Reported metric: {proposal.reported_metric:.2%}",
        f"- Changed files: {', '.join(proposal.changed_files)}",
        "",
        "## Trusted Metrics",
        "",
        f"- Trusted metric: {trusted_metrics['trusted_metric']:.2%}",
        f"- Reported vs trusted delta: {trusted_metrics['delta_reported_vs_trusted']:.2%}",
        f"- Evaluator hash: `{trusted_metrics['evaluator_hash']}`",
        "",
        "## Checks",
        "",
    ]
    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- {status}: `{check['name']}` - {check['details']}")
    lines.append("")

    path = audit_dir / "audit_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
