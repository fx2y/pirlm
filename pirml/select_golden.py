from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, cast

from .cli_common import CliFailure, emit_failure, strict_parse_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml.select_golden")
    parser.add_argument("--in", dest="input_path", required=True, help="Input corpus jsonl")
    parser.add_argument("--n", type=int, required=True, help="Manifest size")
    parser.add_argument("--seed", type=int, default=0, help="Selection seed")
    parser.add_argument("--out", required=True, help="Output manifest jsonl")
    return parser


def _norm_row(row: dict[str, Any]) -> dict[str, Any]:
    task_id = str(row.get("task_id") or row.get("qid") or "")
    if not task_id:
        raise CliFailure("validation", "task row missing task_id/qid", 1, retryable=False)
    return {
        "task_id": task_id,
        "category": str(row.get("category", "unknown")),
        "failure_mode": str(row.get("failure_mode", "unknown")),
        "expected_answer": str(row.get("expected_answer", row.get("answer", ""))),
        "citation_required": bool(row.get("citation_required", True)),
    }


def _score(seed: int, task_id: str) -> str:
    return hashlib.sha256(f"{seed}:{task_id}".encode()).hexdigest()


def _select(rows: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for row in rows:
        grouped[(row["category"], row["failure_mode"])].append(row)
    for key in sorted(grouped.keys()):
        sorted_rows = sorted(grouped[key], key=lambda r: (_score(seed, r["task_id"]), r["task_id"]))
        grouped[key] = deque(sorted_rows)
    selected: list[dict[str, Any]] = []
    keys = sorted(grouped.keys())
    while len(selected) < n and any(grouped[k] for k in keys):
        for key in keys:
            if len(selected) >= n:
                break
            if grouped[key]:
                selected.append(grouped[key].popleft())
    return sorted(selected, key=lambda r: r["task_id"])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = strict_parse_args(parser, argv)
        if args.n <= 0:
            raise CliFailure("validation", "--n must be > 0", 1, retryable=False)
        in_path = Path(args.input_path)
        if not in_path.is_file():
            raise CliFailure("unsupported", f"input path not found: {in_path}", 1, retryable=False)
        raw_rows: list[dict[str, Any]] = []
        for line in in_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if not isinstance(row, dict):
                raise CliFailure("validation", "input rows must be objects", 1, retryable=False)
            raw_rows.append(_norm_row(cast(dict[str, Any], row)))
        if len(raw_rows) < args.n:
            raise CliFailure(
                "validation", "insufficient rows for requested --n", 1, retryable=False
            )
        selected = _select(raw_rows, n=int(args.n), seed=int(args.seed))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in selected]
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 0
    except CliFailure as err:
        return emit_failure(err)
    except Exception as exc:
        print(
            json.dumps({"type": "integrity", "msg": str(exc), "retryable": False}), file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
