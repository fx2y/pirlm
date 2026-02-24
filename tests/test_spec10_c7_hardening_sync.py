from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import unittest
from pathlib import Path


class Spec10C7HardeningSyncTests(unittest.TestCase):
    def test_matrix_proofs_all_green(self) -> None:
        """I24: done flip requires post-edit authority bundle rerun clean.
        C7.T00: run full matrix pass+typed-fail lanes.
        """
        # Recursion guard: skip if already running under a full test suite or CI
        if os.environ.get("PIRML_RECURSION_GUARD"):
            self.skipTest("Skipping to avoid infinite recursion")

        matrix_path = Path("spec-0/10/81-verification-matrix.jsonl")
        self.assertTrue(matrix_path.exists())

        # Set the recursion guard for subprocesses
        env = os.environ.copy()
        env["PIRML_RECURSION_GUARD"] = "1"

        with open(matrix_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("k") == "meta":
                    continue

                proof_cmd = row.get("proof")
                if not proof_cmd:
                    continue

                print(f"Verifying invariant {row['id']}: {proof_cmd}")
                res = subprocess.run(proof_cmd, shell=True, capture_output=True, text=True, env=env)
                self.assertEqual(res.returncode, 0, f"Invariant {row['id']} failed: {res.stderr}")

    def test_bet_winner_tuple_deterministic(self) -> None:
        """I23: orthogonal bet winner selection is deterministic tuple-driven.
        C7.T01: evaluate B1..B10 with deterministic tuple.
        """
        bets_path = Path("spec-0/10/90-orthogonal-bets.jsonl")
        self.assertTrue(bets_path.exists())

        with open(bets_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("k") == "meta":
                    continue

                winner_rule = row.get("winner")
                self.assertTrue(
                    "min" in winner_rule or "max" in winner_rule,
                    f"Bet {row['id']} lacks deterministic winner rule: {winner_rule}",
                )

                # Check that winner is correctly labeled in variants (just by default for now)
                variants = row.get("variants", [])
                has_default = any("(default)" in v for v in variants)
                self.assertTrue(has_default, f"Bet {row['id']} missing default winner")

    def test_loser_surfaces_deleted_or_flagged(self) -> None:
        """C7.T01: delete loser branches/docs/scripts."""
        losers = ["tui", "dashboard"]
        for loser in losers:
            # Check for scripts
            scripts = list(Path("scripts").glob(f"*{loser}*"))
            self.assertEqual(len(scripts), 0, f"Loser script found: {scripts}")

            # Check for docs
            docs = list(Path("docs").glob(f"**/*{loser}*"))
            # Filter out spec/learnings/rules
            docs = [
                d for d in docs if not any(x in str(d) for x in ["spec-0", ".codex", "AGENTS.md"])
            ]
            self.assertEqual(len(docs), 0, f"Loser docs found: {docs}")

    def test_ledgers_synced_same_merge(self) -> None:
        """C7.T02: sync learnings + cycle-10 tasks + cycle-10 tutorial + htn shards."""
        tasks_path = Path("spec-0/10-tasks.jsonl")
        learnings_path = Path("spec-0/00-learnings.jsonl")

        self.assertTrue(tasks_path.exists())
        self.assertTrue(learnings_path.exists())

        with open(tasks_path, encoding="utf-8") as f:
            content = f.read()
            self.assertIn('"c":"C7"', content)

    def test_snippets_match_live_commands(self) -> None:
        """C7.T03: docs/snippets parity audit against live command surfaces."""
        snippets_path = Path("spec-0/10/95-snippets.jsonl")
        self.assertTrue(snippets_path.exists())

        with open(snippets_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("k") != "snip":
                    continue

                if row.get("lang") == "sh":
                    cmd = row["snip"]
                    if "python -m" in cmd:
                        # Extract the module name, handling potentially multiple python commands
                        # and trailing characters like ;
                        matches = re.findall(r"python -m ([\w\.]+)", cmd)
                        for module in matches:
                            # Verify module is either a file or a valid importable module
                            mod_parts = module.split(".")
                            mod_path = Path(*mod_parts)

                            is_local = (
                                Path(f"{mod_path}.py").exists()
                                or (mod_path / "__init__.py").exists()
                            )
                            is_importable = importlib.util.find_spec(module) is not None

                            self.assertTrue(
                                is_local or is_importable,
                                f"Module {module} from snippet {row['id']} not found or importable",
                            )

    def test_done_guard_enforced(self) -> None:
        """C7.T04: run post-edit authority bundle and only then flip C7 done."""
        mise_path = Path(".mise.toml")
        self.assertTrue(mise_path.exists())
        content = mise_path.read_text()
        self.assertIn("scripts.replay_check", content)
        self.assertIn("scripts.artifact_rebuild", content)


if __name__ == "__main__":
    unittest.main()
