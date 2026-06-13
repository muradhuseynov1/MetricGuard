from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metricguard.blue import Proposal
from metricguard.llm_judge import LLMJudgeConfig, write_llm_judge_explanation


class LLMJudgeTests(unittest.TestCase):
    def _proposal(self, root: Path) -> Proposal:
        patch_path = root / "patch.diff"
        proposal_path = root / "proposal.json"
        patch_path.write_text("diff --git a/model.py b/model.py\n", encoding="utf-8")
        proposal_path.write_text("{}", encoding="utf-8")
        return Proposal(
            scenario="repair",
            reported_metric=0.80,
            candidate_dir=root / "candidate",
            artifact_dir=root,
            changed_files=["model.py"],
            patch_path=patch_path,
            proposal_path=proposal_path,
        )

    def test_writes_skipped_artifact_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp)
            paths = write_llm_judge_explanation(
                audit_dir=audit_dir,
                proposal=self._proposal(audit_dir),
                checks=[],
                trusted_metrics={"trusted_metric": 0.80},
                verdict="accepted",
                reason="trusted rerun confirmed improvement",
                config=LLMJudgeConfig(api_key=None),
            )

            payload = json.loads((audit_dir / "llm_judge.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "skipped")
            self.assertEqual(len(paths), 2)
            self.assertIn("not configured", (audit_dir / "llm_judge.md").read_text(encoding="utf-8"))

    def test_writes_model_explanation_from_injected_client(self) -> None:
        def fake_client(prompt: str, config: LLMJudgeConfig) -> dict[str, object]:
            self.assertIn("deterministic verdict is authoritative", prompt)
            return {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": "The repair is credible because all deterministic checks passed.",
                            }
                        ]
                    }
                ]
            }

        with tempfile.TemporaryDirectory() as tmp:
            audit_dir = Path(tmp)
            paths = write_llm_judge_explanation(
                audit_dir=audit_dir,
                proposal=self._proposal(audit_dir),
                checks=[{"name": "metric_comparison", "passed": True, "details": "delta=0.000"}],
                trusted_metrics={"trusted_metric": 0.80, "delta_reported_vs_trusted": 0.0},
                verdict="accepted",
                reason="trusted rerun confirmed improvement",
                config=LLMJudgeConfig(api_key="test-key", model="test-model"),
                client=fake_client,
            )

            payload = json.loads((audit_dir / "llm_judge.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["model"], "test-model")
            self.assertIn("repair is credible", payload["explanation"])
            self.assertEqual(paths, [audit_dir / "llm_judge.json", audit_dir / "llm_judge.md"])


if __name__ == "__main__":
    unittest.main()
