from __future__ import annotations

import argparse

from metricguard.benchmark import PROJECT_ROOT, trusted_baseline
from metricguard.blue import build_proposal
from metricguard.flywheel_graph import FlywheelGraph, create_graph
from metricguard.red_auditor import audit_proposal


def run_cheating_then_repair(graph_backend: str, run_scope: str = "both") -> int:
    if run_scope not in {"rejected", "accepted", "both"}:
        raise ValueError(f"unknown run scope: {run_scope}")
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    graph = create_graph(artifacts_dir, graph_backend)
    baseline = trusted_baseline()
    graph.add_node(
        kind="baseline",
        title="Baseline trusted benchmark",
        status="accepted",
        summary=f"Trusted baseline accuracy: {baseline['accuracy']:.2%}",
        artifacts=["baseline_metrics.json", "baseline_summary.md"],
    )

    rejected = None
    accepted = None
    if run_scope in {"rejected", "both"}:
        cheating = build_proposal("cheat", artifacts_dir)
        graph.add_node(
            kind="proposal",
            title="Blue claim: dramatic improvement",
            status="claimed",
            summary=f"Reported accuracy: {cheating.reported_metric:.2%}",
            artifacts=[str(cheating.artifact_dir.relative_to(artifacts_dir) / "proposal.json")],
            parent_id="baseline",
        )
        rejected = audit_proposal(cheating, baseline["accuracy"], artifacts_dir)
        graph.add_node(
            kind="audit",
            title="Red audit: rejected",
            status=rejected.verdict,
            summary=rejected.reason,
            artifacts=[str(path.relative_to(artifacts_dir)) for path in rejected.artifacts],
            parent_id="proposal-cheat",
        )

    if run_scope in {"accepted", "both"}:
        repair = build_proposal("repair", artifacts_dir)
        graph.add_node(
            kind="proposal",
            title="Blue repair: legitimate threshold change",
            status="claimed",
            summary=f"Reported accuracy: {repair.reported_metric:.2%}",
            artifacts=[str(repair.artifact_dir.relative_to(artifacts_dir) / "proposal.json")],
            parent_id="baseline",
        )
        accepted = audit_proposal(repair, baseline["accuracy"], artifacts_dir)
        graph.add_node(
            kind="audit",
            title="Red audit: accepted",
            status=accepted.verdict,
            summary=accepted.reason,
            artifacts=[str(path.relative_to(artifacts_dir)) for path in accepted.artifacts],
            parent_id="proposal-repair",
        )

    graph.write()

    print("MetricGuard demo complete")
    print(f"Run scope: {run_scope}")
    print(f"Baseline trusted accuracy: {baseline['accuracy']:.2%}")
    if rejected:
        print(f"Cheating claim verdict: {rejected.verdict.upper()} - {rejected.reason}")
    if accepted:
        print(f"Repair claim verdict: {accepted.verdict.upper()} - {accepted.reason}")
    print(f"Local graph: {artifacts_dir / 'local_graph.md'}")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")
    rejected_ok = rejected is None or rejected.verdict == "rejected"
    accepted_ok = accepted is None or accepted.verdict == "accepted"
    return 0 if rejected_ok and accepted_ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MetricGuard MVP demo.")
    parser.add_argument(
        "--scenario",
        choices=["cheating_then_repair"],
        default="cheating_then_repair",
    )
    parser.add_argument(
        "--graph-backend",
        choices=["auto", "local", "flywheel"],
        default="auto",
        help="Use local artifacts only, require Flywheel sync, or auto-detect from env vars.",
    )
    parser.add_argument(
        "--run-scope",
        choices=["rejected", "accepted", "both"],
        default="both",
        help="Run only the rejected branch, only the accepted branch, or both branches.",
    )
    args = parser.parse_args()
    if args.scenario == "cheating_then_repair":
        try:
            return run_cheating_then_repair(args.graph_backend, args.run_scope)
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    raise ValueError(args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
