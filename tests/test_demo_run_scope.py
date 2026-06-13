from __future__ import annotations

import json
import unittest

from demo import run_cheating_then_repair
from metricguard.benchmark import PROJECT_ROOT


class DemoRunScopeTests(unittest.TestCase):
    def _run_and_read_titles(self, run_scope: str) -> list[str]:
        exit_code = run_cheating_then_repair("local", run_scope)
        self.assertEqual(exit_code, 0)
        graph = json.loads((PROJECT_ROOT / "artifacts" / "local_graph.json").read_text())
        return [node["title"] for node in graph["nodes"]]

    def test_rejected_scope_writes_only_rejected_branch(self) -> None:
        titles = self._run_and_read_titles("rejected")

        self.assertIn("Baseline trusted benchmark", titles)
        self.assertIn("Blue claim: dramatic improvement", titles)
        self.assertIn("Red audit: rejected", titles)
        self.assertNotIn("Blue repair: legitimate threshold change", titles)
        self.assertNotIn("Red audit: accepted", titles)

    def test_accepted_scope_writes_only_accepted_branch(self) -> None:
        titles = self._run_and_read_titles("accepted")

        self.assertIn("Baseline trusted benchmark", titles)
        self.assertNotIn("Blue claim: dramatic improvement", titles)
        self.assertNotIn("Red audit: rejected", titles)
        self.assertIn("Blue repair: legitimate threshold change", titles)
        self.assertIn("Red audit: accepted", titles)

    def test_both_scope_writes_both_branches(self) -> None:
        titles = self._run_and_read_titles("both")

        self.assertIn("Blue claim: dramatic improvement", titles)
        self.assertIn("Red audit: rejected", titles)
        self.assertIn("Blue repair: legitimate threshold change", titles)
        self.assertIn("Red audit: accepted", titles)


if __name__ == "__main__":
    unittest.main()
