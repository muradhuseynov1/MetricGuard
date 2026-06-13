from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metricguard.flywheel_graph import FlywheelConfig, FlywheelGraph


class FlywheelGraphTests(unittest.TestCase):
    def test_cli_sync_creates_nodes_with_canonical_parent_ids(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_create(payload: dict[str, object]) -> dict[str, object]:
            calls.append(payload)
            local_id = str(payload["local_temp_node_id"]).replace("metricguard-", "")
            return {"node": {"node_id": f"fw-{local_id}", "slug_name": f"slug-{local_id}"}}

        with tempfile.TemporaryDirectory() as tmp:
            artifacts_dir = Path(tmp)
            graph = FlywheelGraph(
                artifacts_dir,
                FlywheelConfig(root_node_id="fw-root", updated_by="tester"),
                create_node=fake_create,
            )

            graph.add_node(
                kind="baseline",
                title="Baseline trusted benchmark",
                status="accepted",
                summary="Trusted baseline accuracy: 60.00%",
                artifacts=["baseline_metrics.json"],
            )
            graph.add_node(
                kind="proposal",
                title="Blue claim: dramatic improvement",
                status="claimed",
                summary="Reported accuracy: 99.00%",
                artifacts=["cheat/proposal.json"],
                parent_id="baseline",
            )

            graph.write()

            self.assertEqual(calls[0]["parent_ids"], ["fw-root"])
            self.assertEqual(calls[1]["parent_ids"], ["fw-baseline"])
            self.assertEqual(
                calls[0]["staged_payload"]["repo_context"]["updated_by"],  # type: ignore[index]
                "tester",
            )

            sync_report = json.loads((artifacts_dir / "flywheel_sync.json").read_text())
            self.assertTrue(sync_report["ok"])
            self.assertEqual(sync_report["local_to_flywheel"]["baseline"], "fw-baseline")
            self.assertEqual(sync_report["events"][1]["parent_ids"], ["fw-baseline"])

    def test_audit_node_embeds_llm_judge_explanation_in_payload_content(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_create(payload: dict[str, object]) -> dict[str, object]:
            calls.append(payload)
            local_id = str(payload["local_temp_node_id"]).replace("metricguard-", "")
            return {"node": {"node_id": f"fw-{local_id}"}}

        with tempfile.TemporaryDirectory() as tmp:
            artifacts_dir = Path(tmp)
            judge_path = artifacts_dir / "cheat" / "audit" / "llm_judge.md"
            judge_path.parent.mkdir(parents=True)
            judge_path.write_text(
                "# LLM Judge Explanation\n\nThe proposal was rejected because it modified `evaluate.py`.",
                encoding="utf-8",
            )
            graph = FlywheelGraph(
                artifacts_dir,
                FlywheelConfig(root_node_id="fw-root"),
                create_node=fake_create,
            )

            graph.add_node(
                kind="audit",
                title="Red audit: rejected",
                status="rejected",
                summary="failed checks: protected_file_diff",
                artifacts=["cheat/audit/llm_judge.md"],
            )

            graph.write()

            content = calls[0]["staged_payload"]["content"]  # type: ignore[index]
            self.assertIn("## LLM Judge Explanation", content)
            self.assertIn("modified `evaluate.py`", content)


if __name__ == "__main__":
    unittest.main()
