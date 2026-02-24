from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from pirml.cli_common import CliFailure
from scripts import spec10_sales_pack


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


class TestSpec10C5PackagingSync(unittest.TestCase):
    def _fixture_matrix_rows(self) -> list[dict[str, object]]:
        lanes = [f"W{i}" for i in range(11)]
        rows: list[dict[str, object]] = [{"k": "meta", "id": "spec10-matrix"}]
        for lane in lanes:
            rows.append(
                {
                    "k": "row",
                    "lane": lane,
                    "cmd": f"python -m scripts.pirml_run --lane {lane}",
                    "authority": True,
                }
            )
        return rows

    def _fixture_pack_rows(self, *, root: Path) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = [{"k": "meta", "id": "spec10-proof-pack"}]
        for lane in [f"W{i}" for i in range(11)]:
            ptr = (root / "out" / "spec10_pack" / lane.lower() / "final.json").resolve()
            ptr.parent.mkdir(parents=True, exist_ok=True)
            ptr.write_text("{}", encoding="utf-8")
            rows.append({"k": "row", "lane": lane, "rc": 0, "final_ptr": str(ptr)})
        return rows

    def _fixture_verification_rows(self) -> list[dict[str, object]]:
        ids = ["I05", "I10", "I12", "I15", "I16", "I17", "I18", "I19", "I20", "I21", "I22", "I24"]
        return [{"k": "inv", "id": inv} for inv in ids]

    def test_every_claim_maps_to_proof_row(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_claims_") as tmp:
            root = Path(tmp)
            matrix_path = root / "matrix.jsonl"
            pack_path = root / "pack.jsonl"
            verify_path = root / "verify.jsonl"
            out_dir = root / "sales"

            _write_jsonl(matrix_path, self._fixture_matrix_rows())
            _write_jsonl(pack_path, self._fixture_pack_rows(root=root))
            _write_jsonl(verify_path, self._fixture_verification_rows())

            cmd = [
                "python3",
                "-m",
                "scripts.spec10_sales_pack",
                "--out",
                str(out_dir),
                "--matrix",
                str(matrix_path),
                "--pack-index",
                str(pack_path),
                "--verification-matrix",
                str(verify_path),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, 0, res.stderr)
            payload = json.loads(res.stdout)
            self.assertTrue(payload["ok"])

            persona_rows: list[dict[str, object]] = []
            for line in (out_dir / "persona_pack.jsonl").read_text(encoding="utf-8").splitlines():
                row = cast(dict[str, object], json.loads(line))
                if row.get("k") == "persona":
                    persona_rows.append(row)
                    self.assertTrue(str(row.get("proof_cmd", "")).strip())
                    artifact_ptr = Path(str(row.get("artifact_ptr", "")))
                    self.assertTrue(artifact_ptr.is_file(), f"dead artifact ptr: {artifact_ptr}")
            self.assertGreaterEqual(len(persona_rows), 10)

    def test_claim_without_pointer_fails(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_pointer_fail_") as tmp:
            root = Path(tmp)
            matrix_rows = self._fixture_matrix_rows()
            pack_rows = self._fixture_pack_rows(root=root)
            pack_rows = [
                row for row in pack_rows if not (row.get("k") == "row" and row.get("lane") == "W0")
            ]
            verify_rows = self._fixture_verification_rows()

            with self.assertRaises(CliFailure) as ctx:
                spec10_sales_pack.build_persona_pack(
                    matrix_rows=matrix_rows,
                    pack_rows=pack_rows,
                    verification_rows=verify_rows,
                    pack_index_path=root / "pack.jsonl",
                )
            self.assertEqual(ctx.exception.err_type, "validation")

    def test_priority_lane_order(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_order_") as tmp:
            root = Path(tmp)
            rows = spec10_sales_pack.build_persona_pack(
                matrix_rows=self._fixture_matrix_rows(),
                pack_rows=self._fixture_pack_rows(root=root),
                verification_rows=self._fixture_verification_rows(),
                pack_index_path=root / "pack.jsonl",
            )
            persona_refs = [row["proof_ref"] for row in rows if row.get("k") == "persona"]
            first_pos = {lane: persona_refs.index(lane) for lane in ("W0", "W1", "W8", "W9", "W10")}
            self.assertLess(first_pos["W0"], first_pos["W1"])
            self.assertLess(first_pos["W1"], first_pos["W8"])
            self.assertLess(first_pos["W8"], first_pos["W9"])
            self.assertLess(first_pos["W9"], first_pos["W10"])

    def test_objection_rows_reference_invariants(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_objection_") as tmp:
            root = Path(tmp)
            rows = spec10_sales_pack.build_persona_pack(
                matrix_rows=self._fixture_matrix_rows(),
                pack_rows=self._fixture_pack_rows(root=root),
                verification_rows=self._fixture_verification_rows(),
                pack_index_path=root / "pack.jsonl",
            )
            objections = [row for row in rows if row.get("k") == "objection"]
            self.assertEqual(len(objections), 6)
            for row in objections:
                inv = row.get("invariants")
                self.assertIsInstance(inv, list)
                inv_list = cast(list[object], inv)
                self.assertGreaterEqual(len(inv_list), 1)
                for item in inv_list:
                    self.assertRegex(str(item), r"^I[0-9]{2}$")

    def test_optional_lanes_labeled_unsupported(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_optional_") as tmp:
            root = Path(tmp)
            rows = spec10_sales_pack.build_persona_pack(
                matrix_rows=self._fixture_matrix_rows(),
                pack_rows=self._fixture_pack_rows(root=root),
                verification_rows=self._fixture_verification_rows(),
                pack_index_path=root / "pack.jsonl",
            )
            lane_rows = [row for row in rows if row.get("k") == "lane_truth"]
            self.assertEqual(len(lane_rows), 1)
            self.assertEqual(lane_rows[0]["lane"], "W4b")
            self.assertEqual(lane_rows[0]["truth"], "informational")
            self.assertEqual(lane_rows[0]["status"], "unsupported")

    def test_disqualifier_row_missing_fails(self) -> None:
        with TemporaryDirectory(prefix="spec10_c5_disqualifier_") as tmp:
            root = Path(tmp)
            rows = spec10_sales_pack.build_persona_pack(
                matrix_rows=self._fixture_matrix_rows(),
                pack_rows=self._fixture_pack_rows(root=root),
                verification_rows=self._fixture_verification_rows(),
                pack_index_path=root / "pack.jsonl",
            )
            disqualifiers = [row for row in rows if row.get("k") == "disqualifier"]
            self.assertEqual(len(disqualifiers), 4)

    def test_doc_rows_reference_matrix_ids(self) -> None:
        matrix_path = Path("spec-0/10/21-command-matrix.jsonl")
        doc_path = Path("docs/showcase/010-spec10-proof-gating-course.md")
        self.assertTrue(matrix_path.is_file(), f"missing matrix: {matrix_path}")
        self.assertTrue(doc_path.is_file(), f"missing doc: {doc_path}")

        matrix_lanes: set[str] = set()
        for line in matrix_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("k") == "row":
                matrix_lanes.add(str(row["lane"]))

        doc_text = doc_path.read_text(encoding="utf-8")
        doc_lanes = sorted(
            set(part for part in doc_text.replace("`", " ").split() if part.startswith("W"))
        )
        lanes = [lane.strip(".,:;()[]") for lane in doc_lanes]
        lanes = [lane for lane in lanes if lane.startswith("W") and lane[1:].isdigit()]
        self.assertGreaterEqual(len(lanes), 4)
        for lane in lanes:
            self.assertIn(lane, matrix_lanes)


if __name__ == "__main__":
    unittest.main()
