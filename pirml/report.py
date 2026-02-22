from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, cast

from .cli_common import CliFailure, ThresholdConfig, emit_failure, strict_parse_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml.report")
    parser.add_argument("inputs", nargs="+", help="Input eval NDJSON paths")
    parser.add_argument("--out", required=True, help="Output report JSON path")
    parser.add_argument(
        "--compare", nargs=2, metavar=("PREV", "NOW"), help="Compare two report json files"
    )
    parser.add_argument("--acc-min-delta", type=float, default=0.0)
    parser.add_argument("--cost-max-delta", type=float, default=0.0)
    parser.add_argument("--latency-max-delta", type=float, default=0.0)
    return parser


def _read_rows(paths: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in sorted(paths):
        path = Path(raw)
        if not path.is_file():
            raise CliFailure("unsupported", f"missing input: {path}", 1, retryable=False)
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CliFailure("validation", f"invalid NDJSON row in {path}: {exc}", 1) from exc
            if not isinstance(row, dict):
                raise CliFailure("validation", f"row must be object in {path}", 1)
            rows.append(cast(dict[str, Any], row))
    rows.sort(
        key=lambda r: (
            str(r.get("task_id", "")),
            int(r.get("attempt", 0) or 0),
            int(r.get("shard", 0) or 0),
            int(r.get("seq", 0) or 0),
        )
    )
    return rows


def _build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise CliFailure("unsupported", "no rows to aggregate", 1, retryable=False)
    ok_rows = [r for r in rows if bool(r.get("ok"))]
    total = len(rows)
    acc = (len(ok_rows) / total) if total else 0.0
    latencies = [float(r.get("latency_ms", 0.0) or 0.0) for r in rows]
    costs = [float(r.get("cost_usd", 0.0) or 0.0) for r in rows]
    fail_tags = Counter(str(r.get("fail_tag", "")) for r in rows if not bool(r.get("ok")))
    return {
        "ok": True,
        "total_tasks": total,
        "acc": round(acc, 6),
        "median_latency": round(statistics.median(latencies), 6),
        "median_cost": round(statistics.median(costs), 6),
        "fail_pareto": [{"fail_tag": k, "count": v} for k, v in sorted(fail_tags.items())],
    }


def _compare(prev_path: str, now_path: str, th: ThresholdConfig) -> dict[str, Any]:
    prev = json.loads(Path(prev_path).read_text(encoding="utf-8"))
    now = json.loads(Path(now_path).read_text(encoding="utf-8"))
    if not isinstance(prev, dict) or not isinstance(now, dict):
        raise CliFailure("validation", "compare inputs must be report objects", 1)
    prev_map = cast(dict[str, Any], prev)
    now_map = cast(dict[str, Any], now)
    acc_delta = float(now_map.get("acc", 0.0)) - float(prev_map.get("acc", 0.0))
    cost_delta = float(now_map.get("median_cost", 0.0)) - float(prev_map.get("median_cost", 0.0))
    latency_delta = float(now_map.get("median_latency", 0.0)) - float(
        prev_map.get("median_latency", 0.0)
    )
    failed = (
        acc_delta < th.acc_min_delta
        or cost_delta > th.cost_max_delta
        or latency_delta > th.latency_max_delta
    )
    return {
        "ok": not failed,
        "acc_delta": round(acc_delta, 6),
        "cost_delta": round(cost_delta, 6),
        "latency_delta": round(latency_delta, 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = strict_parse_args(parser, argv)
        report = _build_report(_read_rows(list(args.inputs)))
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.compare is not None:
            compare = _compare(
                args.compare[0],
                args.compare[1],
                ThresholdConfig(
                    acc_min_delta=float(args.acc_min_delta),
                    cost_max_delta=float(args.cost_max_delta),
                    latency_max_delta=float(args.latency_max_delta),
                ),
            )
            report["compare"] = compare
        out_path.write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        if bool(report.get("compare", {}).get("ok", True)):
            return 0
        raise CliFailure("validation", "threshold regression", 1, retryable=False)
    except CliFailure as err:
        return emit_failure(err)
    except Exception as exc:
        print(
            json.dumps({"type": "integrity", "msg": str(exc), "retryable": False}), file=sys.stderr
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
