from __future__ import annotations

import argparse

from metricguard.benchmark import PROJECT_ROOT, trusted_baseline
from metricguard.blue import build_proposal
from metricguard.citation_benchmark import run_citation_benchmark
from metricguard.citations import LiveCitationConfig, run_fake_citation_audit
from metricguard.external_scifact import run_external_scifact_subset
from metricguard.flywheel_graph import FlywheelGraph, create_graph
from metricguard.red_auditor import audit_proposal


def run_cheating_then_repair(graph_backend: str, flywheel_parent_node_id: str | None = None) -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    graph = create_graph(artifacts_dir, graph_backend, parent_node_id=flywheel_parent_node_id)
    baseline = trusted_baseline()
    graph.add_node(
        kind="baseline",
        title="Baseline trusted benchmark",
        status="accepted",
        summary=f"Trusted baseline accuracy: {baseline['accuracy']:.2%}",
        artifacts=["baseline_metrics.json", "baseline_summary.md"],
    )

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
    print(f"Baseline trusted accuracy: {baseline['accuracy']:.2%}")
    print(f"Cheating claim verdict: {rejected.verdict.upper()} - {rejected.reason}")
    print(f"Repair claim verdict: {accepted.verdict.upper()} - {accepted.reason}")
    print(f"Local graph: {artifacts_dir / 'local_graph.md'}")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")
    return 0 if rejected.verdict == "rejected" and accepted.verdict == "accepted" else 1


def run_fake_citations(
    graph_backend: str,
    live_citation_config: LiveCitationConfig | None = None,
    flywheel_parent_node_id: str | None = None,
) -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    graph = create_graph(artifacts_dir, graph_backend, parent_node_id=flywheel_parent_node_id)
    graph.add_node(
        kind="baseline",
        title="Baseline citation audit task",
        status="accepted",
        summary="Generated answers must be backed by resolvable citations and source-supported claims.",
        artifacts=["citations/sources/source_registry.json"],
    )

    rejected, accepted = run_fake_citation_audit(artifacts_dir, live_config=live_citation_config)

    graph.add_node(
        kind="proposal",
        title="Blue answer: fabricated citations",
        status="claimed",
        summary="Seeded answer claims a 91% reduction and cites a nonexistent DOI and URL.",
        artifacts=["citations/bad_answer.md"],
        parent_id="baseline",
    )
    graph.add_node(
        kind="audit",
        title="Red citation audit: rejected",
        status=rejected.verdict,
        summary=rejected.reason,
        artifacts=[str(path.relative_to(artifacts_dir)) for path in rejected.artifacts],
        parent_id="proposal-citation-fake",
    )

    graph.add_node(
        kind="proposal",
        title="Blue repair: verified citation answer",
        status="claimed",
        summary="Repaired answer only makes claims supported by the local source fixture.",
        artifacts=["citations/repaired_answer.md"],
        parent_id="baseline",
    )
    graph.add_node(
        kind="audit",
        title="Red citation audit: accepted",
        status=accepted.verdict,
        summary=accepted.reason,
        artifacts=[str(path.relative_to(artifacts_dir)) for path in accepted.artifacts],
        parent_id="proposal-citation-repair",
    )

    graph.write()

    print("MetricGuard citation demo complete")
    print(f"Fake citation verdict: {rejected.verdict.upper()} - {rejected.reason}")
    print(f"Repaired citation verdict: {accepted.verdict.upper()} - {accepted.reason}")
    print(f"Citation artifacts: {artifacts_dir / 'citations'}")
    print(f"Local graph: {artifacts_dir / 'local_graph.md'}")
    if live_citation_config and live_citation_config.enabled:
        mode = "enforced" if live_citation_config.enforce else "evidence-only"
        print(f"Live DOI/URL checks: enabled ({mode})")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")
    return 0 if rejected.verdict == "rejected" and accepted.verdict == "accepted" else 1


def run_citation_benchmark_demo(
    graph_backend: str,
    live_citation_config: LiveCitationConfig | None = None,
    flywheel_parent_node_id: str | None = None,
) -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    results, metrics = run_citation_benchmark(artifacts_dir, live_config=live_citation_config)

    graph = create_graph(artifacts_dir, graph_backend, parent_node_id=flywheel_parent_node_id)
    graph.add_node(
        kind="baseline",
        title="CitationGuardBench - seeded citation integrity suite",
        status="accepted",
        summary=(
            f"{metrics['correct_cases']}/{metrics['total_cases']} cases correct; "
            f"detection rate {float(metrics['cheat_detection_rate']):.1%}; "
            f"false reject rate {float(metrics['false_reject_rate']):.1%}"
        ),
        artifacts=[
            "citation_benchmark/source_registry.json",
            "citation_benchmark/benchmark_summary.json",
            "citation_benchmark/benchmark_report.md",
        ],
    )
    for result in results:
        case_id = result.case.case_id
        graph.add_node(
            kind="proposal",
            title=f"Benchmark case: {case_id}",
            status=f"expected-{result.case.expected_verdict}",
            summary=result.case.description,
            artifacts=[str(result.answer_path.relative_to(artifacts_dir))],
            parent_id="baseline",
        )
        graph.add_node(
            kind="audit",
            title=f"Benchmark audit: {case_id} {result.verdict}",
            status=result.verdict,
            summary=f"Expected {result.case.expected_verdict}; got {result.verdict}. {result.reason}",
            artifacts=[str(path.relative_to(artifacts_dir)) for path in result.artifacts],
            parent_id=f"proposal-benchmark-{case_id}",
        )

    graph.write()

    print("MetricGuard citation benchmark complete")
    print(f"Cases correct: {metrics['correct_cases']}/{metrics['total_cases']}")
    print(f"Accuracy: {float(metrics['accuracy']):.1%}")
    print(f"Cheat detection rate: {float(metrics['cheat_detection_rate']):.1%}")
    print(f"False reject rate: {float(metrics['false_reject_rate']):.1%}")
    print(f"Benchmark report: {artifacts_dir / 'citation_benchmark' / 'benchmark_report.md'}")
    if live_citation_config and live_citation_config.enabled:
        mode = "enforced" if live_citation_config.enforce else "evidence-only"
        print(f"Live DOI/URL checks: enabled ({mode})")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")
    return 0 if metrics["correct_cases"] == metrics["total_cases"] else 1


def run_external_scifact_demo(graph_backend: str, flywheel_parent_node_id: str | None = None) -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    results, metrics = run_external_scifact_subset(PROJECT_ROOT, artifacts_dir)

    graph = create_graph(artifacts_dir, graph_backend, parent_node_id=flywheel_parent_node_id)
    graph.add_node(
        kind="baseline",
        title="External SciFact subset - scientific claim verification",
        status="accepted",
        summary=(
            f"{metrics['correct_cases']}/{metrics['total_cases']} cases correct; "
            f"unsupported detection {float(metrics['unsupported_detection_rate']):.1%}; "
            f"false reject rate {float(metrics['false_reject_rate']):.1%}"
        ),
        artifacts=[
            "external_scifact_subset/external_scifact_subset.jsonl",
            "external_scifact_subset/benchmark_summary.json",
            "external_scifact_subset/benchmark_report.md",
        ],
    )
    for result in results:
        graph.add_node(
            kind="proposal",
            title=f"SciFact case: {result.case_id}",
            status=f"expected-{result.expected_verdict}",
            summary=f"External SciFact case expected {result.expected_verdict}.",
            artifacts=[str(result.artifacts[0].relative_to(artifacts_dir))],
            parent_id="baseline",
        )
        graph.add_node(
            kind="audit",
            title=f"SciFact audit: {result.case_id} {result.verdict}",
            status=result.verdict,
            summary=f"Expected {result.expected_verdict}; got {result.verdict}. {result.reason}",
            artifacts=[str(path.relative_to(artifacts_dir)) for path in result.artifacts],
            parent_id=f"proposal-scifact-{result.case_id}",
        )

    graph.write()

    print("MetricGuard external SciFact subset complete")
    print(f"Cases correct: {metrics['correct_cases']}/{metrics['total_cases']}")
    print(f"Accuracy: {float(metrics['accuracy']):.1%}")
    print(f"Unsupported detection rate: {float(metrics['unsupported_detection_rate']):.1%}")
    print(f"False reject rate: {float(metrics['false_reject_rate']):.1%}")
    print(f"Benchmark report: {artifacts_dir / 'external_scifact_subset' / 'benchmark_report.md'}")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")
    return 0 if metrics["correct_cases"] == metrics["total_cases"] else 1


def run_citation_validation_pipeline(
    graph_backend: str,
    live_citation_config: LiveCitationConfig | None = None,
    flywheel_parent_node_id: str | None = None,
) -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    citation_rejected, citation_accepted = run_fake_citation_audit(
        artifacts_dir,
        live_config=live_citation_config,
    )
    benchmark_results, benchmark_metrics = run_citation_benchmark(
        artifacts_dir,
        live_config=live_citation_config,
    )
    scifact_results, scifact_metrics = run_external_scifact_subset(PROJECT_ROOT, artifacts_dir)

    graph = create_graph(artifacts_dir, graph_backend, parent_node_id=flywheel_parent_node_id)

    graph.add_node(
        kind="baseline",
        title="Citation repair demo - fake then verified",
        status="accepted",
        summary="A fabricated citation is rejected, then a repaired citation is accepted.",
        artifacts=["citations/sources/source_registry.json"],
        node_id="pipeline-citation-demo",
    )
    graph.add_node(
        kind="proposal",
        title="Blue answer: fabricated citations",
        status="claimed",
        summary="Seeded answer claims a 91% reduction and cites a nonexistent DOI and URL.",
        artifacts=["citations/bad_answer.md"],
        parent_id="pipeline-citation-demo",
        node_id="pipeline-proposal-citation-fake",
    )
    graph.add_node(
        kind="audit",
        title="Red citation audit: rejected",
        status=citation_rejected.verdict,
        summary=citation_rejected.reason,
        artifacts=[str(path.relative_to(artifacts_dir)) for path in citation_rejected.artifacts],
        parent_id="pipeline-proposal-citation-fake",
        node_id="pipeline-audit-citation-rejected",
    )
    graph.add_node(
        kind="proposal",
        title="Blue repair: verified citation answer",
        status="claimed",
        summary="Repaired answer only makes claims supported by the local source fixture.",
        artifacts=["citations/repaired_answer.md"],
        parent_id="pipeline-citation-demo",
        node_id="pipeline-proposal-citation-repair",
    )
    graph.add_node(
        kind="audit",
        title="Red citation audit: accepted",
        status=citation_accepted.verdict,
        summary=citation_accepted.reason,
        artifacts=[str(path.relative_to(artifacts_dir)) for path in citation_accepted.artifacts],
        parent_id="pipeline-proposal-citation-repair",
        node_id="pipeline-audit-citation-accepted",
    )

    graph.add_node(
        kind="baseline",
        title="CitationGuardBench - seeded citation integrity suite",
        status="accepted",
        summary=(
            f"{benchmark_metrics['correct_cases']}/{benchmark_metrics['total_cases']} cases correct; "
            f"detection rate {float(benchmark_metrics['cheat_detection_rate']):.1%}; "
            f"false reject rate {float(benchmark_metrics['false_reject_rate']):.1%}"
        ),
        artifacts=[
            "citation_benchmark/source_registry.json",
            "citation_benchmark/benchmark_summary.json",
            "citation_benchmark/benchmark_report.md",
        ],
        parent_id="pipeline-audit-citation-accepted",
        node_id="pipeline-citation-benchmark",
    )
    for result in benchmark_results:
        case_id = result.case.case_id
        proposal_id = f"pipeline-proposal-benchmark-{case_id}"
        graph.add_node(
            kind="proposal",
            title=f"Benchmark case: {case_id}",
            status=f"expected-{result.case.expected_verdict}",
            summary=result.case.description,
            artifacts=[str(result.answer_path.relative_to(artifacts_dir))],
            parent_id="pipeline-citation-benchmark",
            node_id=proposal_id,
        )
        graph.add_node(
            kind="audit",
            title=f"Benchmark audit: {case_id} {result.verdict}",
            status=result.verdict,
            summary=f"Expected {result.case.expected_verdict}; got {result.verdict}. {result.reason}",
            artifacts=[str(path.relative_to(artifacts_dir)) for path in result.artifacts],
            parent_id=proposal_id,
            node_id=f"pipeline-audit-benchmark-{case_id}",
        )

    graph.add_node(
        kind="baseline",
        title="External SciFact subset - scientific claim verification",
        status="accepted",
        summary=(
            f"{scifact_metrics['correct_cases']}/{scifact_metrics['total_cases']} cases correct; "
            f"unsupported detection {float(scifact_metrics['unsupported_detection_rate']):.1%}; "
            f"false reject rate {float(scifact_metrics['false_reject_rate']):.1%}"
        ),
        artifacts=[
            "external_scifact_subset/external_scifact_subset.jsonl",
            "external_scifact_subset/benchmark_summary.json",
            "external_scifact_subset/benchmark_report.md",
        ],
        parent_id="pipeline-citation-benchmark",
        node_id="pipeline-external-scifact",
    )
    for result in scifact_results:
        proposal_id = f"pipeline-proposal-scifact-{result.case_id}"
        graph.add_node(
            kind="proposal",
            title=f"SciFact case: {result.case_id}",
            status=f"expected-{result.expected_verdict}",
            summary=f"External SciFact case expected {result.expected_verdict}.",
            artifacts=[str(result.artifacts[0].relative_to(artifacts_dir))],
            parent_id="pipeline-external-scifact",
            node_id=proposal_id,
        )
        graph.add_node(
            kind="audit",
            title=f"SciFact audit: {result.case_id} {result.verdict}",
            status=result.verdict,
            summary=f"Expected {result.expected_verdict}; got {result.verdict}. {result.reason}",
            artifacts=[str(path.relative_to(artifacts_dir)) for path in result.artifacts],
            parent_id=proposal_id,
            node_id=f"pipeline-audit-scifact-{result.case_id}",
        )

    graph.write()

    print("MetricGuard citation validation pipeline complete")
    print(f"Citation repair: {citation_rejected.verdict.upper()} then {citation_accepted.verdict.upper()}")
    print(
        "Synthetic benchmark: "
        f"{benchmark_metrics['correct_cases']}/{benchmark_metrics['total_cases']} "
        f"({float(benchmark_metrics['accuracy']):.1%})"
    )
    print(
        "External SciFact subset: "
        f"{scifact_metrics['correct_cases']}/{scifact_metrics['total_cases']} "
        f"({float(scifact_metrics['accuracy']):.1%})"
    )
    print(f"Local graph: {artifacts_dir / 'local_graph.md'}")
    if live_citation_config and live_citation_config.enabled:
        mode = "enforced" if live_citation_config.enforce else "evidence-only"
        print(f"Live DOI/URL checks: enabled ({mode})")
    if isinstance(graph, FlywheelGraph):
        ok = all(event["ok"] for event in graph.sync_events)
        status = "synced" if ok else "sync attempted with errors"
        print(f"Flywheel graph: {status} ({artifacts_dir / 'flywheel_sync.json'})")

    all_good = (
        citation_rejected.verdict == "rejected"
        and citation_accepted.verdict == "accepted"
        and benchmark_metrics["correct_cases"] == benchmark_metrics["total_cases"]
        and scifact_metrics["correct_cases"] == scifact_metrics["total_cases"]
    )
    return 0 if all_good else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the MetricGuard MVP demo.")
    parser.add_argument(
        "--scenario",
        choices=[
            "cheating_then_repair",
            "fake_citations",
            "citation_benchmark",
            "external_scifact_subset",
            "citation_validation_pipeline",
        ],
        default="cheating_then_repair",
    )
    parser.add_argument(
        "--graph-backend",
        choices=["auto", "local", "flywheel", "flywheel-cli"],
        default="auto",
        help="Use local artifacts only, sync through Flywheel API, sync through Flywheel CLI, or auto-detect API env vars.",
    )
    parser.add_argument(
        "--live-citation-checks",
        action="store_true",
        help="Resolve public DOI and URL citation targets and write live_citation_resolution.json.",
    )
    parser.add_argument(
        "--enforce-live-citation-checks",
        action="store_true",
        help="Make failed live DOI/URL checks affect citation verdicts.",
    )
    parser.add_argument(
        "--citation-timeout-seconds",
        type=int,
        default=8,
        help="Timeout for each live DOI/URL probe.",
    )
    parser.add_argument(
        "--flywheel-parent-node-id",
        default=None,
        help="Attach top-level nodes in this run under this Flywheel node instead of FLYWHEEL_ROOT_NODE_ID.",
    )
    args = parser.parse_args()
    if args.scenario == "cheating_then_repair":
        try:
            return run_cheating_then_repair(args.graph_backend, flywheel_parent_node_id=args.flywheel_parent_node_id)
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    if args.scenario == "fake_citations":
        try:
            live_config = LiveCitationConfig(
                enabled=args.live_citation_checks or args.enforce_live_citation_checks,
                enforce=args.enforce_live_citation_checks,
                timeout_seconds=args.citation_timeout_seconds,
            )
            return run_fake_citations(
                args.graph_backend,
                live_citation_config=live_config,
                flywheel_parent_node_id=args.flywheel_parent_node_id,
            )
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    if args.scenario == "citation_benchmark":
        try:
            live_config = LiveCitationConfig(
                enabled=args.live_citation_checks or args.enforce_live_citation_checks,
                enforce=args.enforce_live_citation_checks,
                timeout_seconds=args.citation_timeout_seconds,
            )
            return run_citation_benchmark_demo(
                args.graph_backend,
                live_citation_config=live_config,
                flywheel_parent_node_id=args.flywheel_parent_node_id,
            )
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    if args.scenario == "external_scifact_subset":
        try:
            return run_external_scifact_demo(args.graph_backend, flywheel_parent_node_id=args.flywheel_parent_node_id)
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    if args.scenario == "citation_validation_pipeline":
        try:
            live_config = LiveCitationConfig(
                enabled=args.live_citation_checks or args.enforce_live_citation_checks,
                enforce=args.enforce_live_citation_checks,
                timeout_seconds=args.citation_timeout_seconds,
            )
            return run_citation_validation_pipeline(
                args.graph_backend,
                live_citation_config=live_config,
                flywheel_parent_node_id=args.flywheel_parent_node_id,
            )
        except RuntimeError as exc:
            parser.exit(2, f"error: {exc}\n")
    raise ValueError(args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
