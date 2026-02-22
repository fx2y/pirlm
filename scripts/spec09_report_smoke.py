from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

from scripts.tools.common import emit_error


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def main() -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="spec09_c6_report_") as tmp:
            root = Path(tmp)
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "task_id": "R1",
                                "query": "alpha",
                                "expected_answer": "alpha",
                            },
                            sort_keys=True,
                        ),
                        json.dumps(
                            {
                                "task_id": "R2",
                                "query": "__timeout__ lane",
                                "expected_answer": "x",
                            },
                            sort_keys=True,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            eval_out = root / "out"
            eval_proc = _run(
                "-m",
                "pirml.eval",
                "--suite",
                "golden50",
                "--dataset",
                str(dataset),
                "--jobs",
                "1",
                "--shards",
                "1",
                "--shard",
                "0",
                "--timeout-s",
                "10",
                "--out-dir",
                str(eval_out),
                cwd=Path("."),
            )
            if eval_proc.returncode != 0:
                print(eval_proc.stderr, end="", file=sys.stderr)
                raise SystemExit(eval_proc.returncode)

            shard = eval_out / "runs" / "golden50" / "shard-00000.ndjson"
            if not shard.is_file():
                emit_error("integrity", f"missing eval shard: {shard}", 2)

            report_out = eval_out / "report.json"
            pareto_out = eval_out / "pareto.json"
            report_cmp_out = eval_out / "report.compare.json"
            pareto_cmp_out = eval_out / "pareto.compare.json"
            delta_out = eval_out / "delta.json"
            art_root = root / "art"
            report_proc = _run(
                "-m",
                "pirml.report",
                str(shard),
                "--out",
                str(report_out),
                "--pareto-out",
                str(pareto_out),
                "--art-root",
                str(art_root),
                cwd=Path("."),
            )
            if report_proc.returncode != 0:
                print(report_proc.stderr, end="", file=sys.stderr)
                raise SystemExit(report_proc.returncode)
            report_cmp_proc = _run(
                "-m",
                "pirml.report",
                str(shard),
                "--out",
                str(report_cmp_out),
                "--pareto-out",
                str(pareto_cmp_out),
                "--art-root",
                str(art_root),
                "--compare",
                str(report_out),
                str(report_out),
                "--delta-out",
                str(delta_out),
                cwd=Path("."),
            )
            if report_cmp_proc.returncode != 0:
                print(report_cmp_proc.stderr, end="", file=sys.stderr)
                raise SystemExit(report_cmp_proc.returncode)

            pointers = eval_out / "report.pointers.json"
            for required in (
                report_out,
                pareto_out,
                report_cmp_out,
                pareto_cmp_out,
                delta_out,
                pointers,
            ):
                if not required.is_file():
                    emit_error("integrity", f"missing report artifact: {required}", 2)

            report = cast(dict[str, Any], json.loads(report_cmp_out.read_text(encoding="utf-8")))
            compare = cast(dict[str, Any] | None, report.get("compare"))
            if not isinstance(compare, dict) or not bool(compare.get("ok")):
                emit_error("integrity", "report compare lane drift", 2)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "acc": report.get("acc"),
                        "inputs": 1,
                        "pointer_index": len(json.loads(pointers.read_text(encoding="utf-8"))),
                    },
                    sort_keys=True,
                )
            )
    except SystemExit:
        raise
    except Exception as exc:
        emit_error("integrity", str(exc), 2)


if __name__ == "__main__":
    main()
