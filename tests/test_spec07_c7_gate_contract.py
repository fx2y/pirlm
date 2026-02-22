from __future__ import annotations

import unittest
from pathlib import Path


class TestSpec07C7GateContract(unittest.TestCase):
    def setUp(self):
        self.mise_path = Path(".mise.toml")

    def test_ci_order_is_immutable(self):
        # H2: Gate order is immutable fail-fast: fmt > lint > types > unit > proto > trace > schemas > replay
        # AGENTS.md:10, .codex/rules/30-tooling-tasks.md:14-19
        import tomllib

        data = tomllib.loads(self.mise_path.read_text(encoding="utf-8"))
        ci_run = data.get("tasks", {}).get("ci", {}).get("run", "")
        expected = "mise run fmt && mise run lint && mise run types && mise run unit && mise run proto && mise run trace && mise run schemas && mise run replay"
        self.assertEqual(ci_run, expected)

    def test_fast_has_no_proto_trace_schema_replay(self):
        # G2: `fast` must stay <3s and high-yield; reject signal only, never mini-CI
        # .codex/rules/30-tooling-tasks.md:16
        import tomllib

        data = tomllib.loads(self.mise_path.read_text(encoding="utf-8"))
        fast_run = data.get("tasks", {}).get("fast", {}).get("run", "")
        for heavy in ["proto", "trace", "schemas", "replay"]:
            self.assertNotIn(f"run {heavy}", fast_run)
            self.assertNotIn(f"scripts.{heavy}", fast_run)


if __name__ == "__main__":
    unittest.main()
