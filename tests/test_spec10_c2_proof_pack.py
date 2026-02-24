from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _smoke_matrix_rows(matrix_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [{"k": "meta", "id": "spec10-matrix", "asof": "2026-02-24"}]
    for idx in range(11):
        lane = f"W{idx}"
        rows.append(
            {
                "k": "row",
                "lane": lane,
                "name": f"{lane} smoke",
                "cmd": f"python -m scripts.spec10_matrix --matrix {matrix_path} --lane W0",
                "authority": True,
                "deps": [],
                "deterministic": True,
                "optional": False,
            }
        )
    rows.append({"k": "alias", "alias": "mise ci", "ref": "W10", "authority": False, "risk": "low"})
    return rows


def _run_pack(
    *, matrix: Path, out: Path, skip_run: bool, include_live: bool = False
) -> subprocess.CompletedProcess[str]:
    cmd = [
        "python3",
        "-m",
        "scripts.spec10_proof_pack",
        "--matrix",
        str(matrix),
        "--out",
        str(out),
    ]
    if skip_run:
        cmd.append("--skip-run")
    if include_live:
        cmd.append("--include-live")
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


class TestSpec10C2ProofPack(unittest.TestCase):
    def test_pack_index_emitted(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_emit_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            _write_jsonl(matrix, _smoke_matrix_rows(matrix))

            res = _run_pack(matrix=matrix, out=out, skip_run=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out.is_file())

            rows = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(rows[0]["k"], "meta")
            self.assertEqual(rows[0]["id"], "spec10-proof-pack")

    def test_lane_spec_table_stable(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_lanes_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            _write_jsonl(matrix, _smoke_matrix_rows(matrix))

            res = _run_pack(matrix=matrix, out=out, skip_run=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            rows = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            lanes = [row["lane"] for row in rows if row.get("k") == "row"]
            self.assertEqual(lanes, [f"W{i}" for i in range(11)])

    def test_pack_pointer_resolve(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_ptr_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            _write_jsonl(matrix, _smoke_matrix_rows(matrix))

            res = _run_pack(matrix=matrix, out=out, skip_run=True)
            self.assertEqual(res.returncode, 0, res.stderr)

            rows = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            lane_rows = [row for row in rows if row.get("k") == "row"]
            self.assertEqual(len(lane_rows), 11)
            for row in lane_rows:
                self.assertIn("details_ptr", row)
                pointer = Path(str(row["details_ptr"]))
                self.assertTrue(pointer.is_file(), f"missing pointer for {row['lane']}: {pointer}")
                self.assertTrue(
                    str(row.get("sha256", "")).strip(), f"missing sha256 for {row['lane']}"
                )

    def test_live_lane_marked_non_authoritative(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_live_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            _write_jsonl(matrix, _smoke_matrix_rows(matrix))

            res = _run_pack(matrix=matrix, out=out, skip_run=True, include_live=True)
            self.assertEqual(res.returncode, 0, res.stderr)

            rows = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            w4 = next(row for row in rows if row.get("k") == "row" and row.get("lane") == "W4")
            w4b = next(row for row in rows if row.get("k") == "row" and row.get("lane") == "W4b")
            self.assertTrue(bool(w4["authority"]))
            self.assertFalse(bool(w4b["authority"]))
            self.assertTrue(bool(w4b["optional"]))

    def test_eval_rows_require_explicit_dataset(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_ingress_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            rows = _smoke_matrix_rows(matrix)
            for row in rows:
                if row.get("k") == "row" and row.get("lane") == "W7":
                    row["cmd"] = "python -m pirml.eval --suite golden50 --out-dir out/eval/bad"
            _write_jsonl(matrix, rows)

            res = _run_pack(matrix=matrix, out=out, skip_run=True)
            self.assertEqual(res.returncode, 1)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "validation")
            self.assertIn("--dataset", err["msg"])

    def test_required_lane_failures_exit_nonzero(self) -> None:
        with TemporaryDirectory(prefix="spec10_c2_failclosed_") as tmp:
            root = Path(tmp)
            matrix = root / "matrix.jsonl"
            out = root / "pack/index.jsonl"
            rows = _smoke_matrix_rows(matrix)
            for row in rows:
                if row.get("k") == "row" and row.get("lane") == "W0":
                    row["cmd"] = f"python -m scripts.spec10_matrix --matrix {matrix} --lane W99"
            _write_jsonl(matrix, rows)

            res = _run_pack(matrix=matrix, out=out, skip_run=False)
            self.assertEqual(res.returncode, 1)
            err = json.loads(res.stderr)
            self.assertEqual(err["type"], "validation")
            self.assertIn("required lanes failed", err["msg"])
            self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
