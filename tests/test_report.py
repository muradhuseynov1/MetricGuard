from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from metricguard.blue import Proposal
from metricguard.report import write_audit_report


class AuditReportTests(unittest.TestCase):
    def test_includes_llm_judge_explanation_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal = Proposal(
                scenario="repair",
                reported_metric=0.80,
                candidate_dir=root / "candidate",
                artifact_dir=root,
                changed_files=["model.py"],
                patch_path=root / "patch.diff",
                proposal_path=root / "proposal.json",
            )
            path = write_audit_report(
                audit_dir=root,
                proposal=proposal,
                checks=[{"name": "hidden_test_run", "passed": True, "details": "hidden accuracy 0.800"}],
                trusted_metrics={
                    "trusted_metric": 0.80,
                    "delta_reported_vs_trusted": 0.0,
                    "evaluator_hash": "abc123",
                },
                verdict="accepted",
                reason="trusted rerun confirmed improvement",
                llm_judge={
                    "status": "completed",
                    "explanation": "The patch is credible because the hidden test passed.",
                },
            )

            text = path.read_text(encoding="utf-8")
            self.assertIn("## LLM Judge Explanation", text)
            self.assertIn("patch is credible", text)


if __name__ == "__main__":
    unittest.main()
