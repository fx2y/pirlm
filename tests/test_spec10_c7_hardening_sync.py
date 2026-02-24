from __future__ import annotations

import importlib.util
import json
import re
import shlex
import subprocess
import unittest
from pathlib import Path


class Spec10C7HardeningSyncTests(unittest.TestCase):
    def test_matrix_proofs_all_green(self) -> None:
        """I24/C7.T00: matrix proof rows must resolve to executable, bounded proof commands."""
        matrix_path = Path("spec-0/10/81-verification-matrix.jsonl")
        self.assertTrue(matrix_path.exists())

        proof_cmds: list[str] = []
        for line in matrix_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("k") != "inv":
                continue
            proof = str(row.get("proof", "")).strip()
            if not proof:
                continue
            if not proof.startswith("python -m unittest -q "):
                # Heavy multi-gate proofs are exercised in integration/gate lanes, not this unit suite.
                continue
            if "tests.test_spec10_c7_hardening_sync" in proof:
                continue
            proof_cmds.append(proof)

        deduped = sorted(set(proof_cmds))
        self.assertGreater(len(deduped), 0)
        for proof in deduped:
            argv = shlex.split(proof)
            result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=120)
            self.assertEqual(result.returncode, 0, f"proof failed: {proof}\n{result.stderr}")

    def test_bet_winner_tuple_deterministic(self) -> None:
        """I23: orthogonal bet winner selection is deterministic tuple-driven."""
        bets_path = Path("spec-0/10/90-orthogonal-bets.jsonl")
        self.assertTrue(bets_path.exists())

        for line in bets_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("k") != "bet":
                continue
            winner_rule = str(row.get("winner", ""))
            self.assertTrue(
                "min" in winner_rule or "max" in winner_rule,
                f"bet {row.get('id')} lacks deterministic winner rule",
            )
            variants = [str(item) for item in row.get("variants", [])]
            self.assertTrue(any("(default)" in item for item in variants))

    def test_loser_surfaces_deleted_or_flagged(self) -> None:
        """C7.T01: loser surfaces (`tui`,`dashboard`) are absent from product scripts/docs."""
        for loser in ("tui", "dashboard"):
            scripts = list(Path("scripts").glob(f"*{loser}*"))
            self.assertEqual(len(scripts), 0, f"loser script found: {scripts}")

            docs = list(Path("docs").glob(f"**/*{loser}*"))
            docs = [doc for doc in docs if "docs/showcase" in str(doc)]
            self.assertEqual(len(docs), 0, f"loser showcase doc found: {docs}")

    def test_ledgers_synced_same_merge(self) -> None:
        """C7.T02: cycle-10 ledgers remain cross-referenced and status-aligned."""
        tasks = Path("spec-0/10-tasks.jsonl").read_text(encoding="utf-8")
        htn = Path("spec-0/10-htn.jsonl").read_text(encoding="utf-8")
        tutorial = Path("spec-0/10-tutorial.jsonl").read_text(encoding="utf-8")
        self.assertIn('"k":"state","c":"C7"', tasks)
        self.assertIn('"k":"cycle","id":"C7"', htn)
        self.assertIn('"state":{"C0"', tutorial)

    def test_snippets_match_live_commands(self) -> None:
        """C7.T03: snippet python module references must resolve."""
        snippets_path = Path("spec-0/10/95-snippets.jsonl")
        self.assertTrue(snippets_path.exists())

        for line in snippets_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("k") != "snip" or row.get("lang") != "sh":
                continue
            cmd = str(row.get("snip", ""))
            for module in re.findall(r"python -m ([\w\.]+)", cmd):
                mod_parts = module.split(".")
                mod_path = Path(*mod_parts)
                is_local = Path(f"{mod_path}.py").exists() or (mod_path / "__init__.py").exists()
                is_importable = importlib.util.find_spec(module) is not None
                self.assertTrue(is_local or is_importable, f"missing module in snippet: {module}")

    def test_done_guard_enforced(self) -> None:
        """C7.T04: done guard requires proof commands in C7 shard and helper contracts."""
        c7_path = Path("spec-0/10/80-cycle-c7-winner-lock-sync.jsonl")
        c7_text = c7_path.read_text(encoding="utf-8")
        self.assertIn("scripts.replay_check", c7_text)
        self.assertIn("scripts.artifact_rebuild --check", c7_text)

        mise_text = Path(".mise.toml").read_text(encoding="utf-8")
        self.assertIn('tasks."spec10-proof"', mise_text)
        self.assertIn('tasks."spec10-sales"', mise_text)


if __name__ == "__main__":
    unittest.main()
