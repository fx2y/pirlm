from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from .artifacts import ArtifactStore, default_layout
from .artifacts.types import ArtifactSource
from .cli_common import CliFailure, ThresholdConfig, emit_failure, strict_parse_args
from .reporting import aggregate_report, read_eval_rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml.report")
    parser.add_argument("inputs", nargs="+", help="Input eval NDJSON paths")
    parser.add_argument("--out", required=True, help="Output report JSON path")
    parser.add_argument(
        "--pareto-out", help="Output pareto JSON path (default: <out_dir>/pareto.json)"
    )
    parser.add_argument(
        "--art-root", default="art", help="Artifact root for CAS linkage (default: art)"
    )
    parser.add_argument(
        "--compare", nargs=2, metavar=("PREV", "NOW"), help="Compare two report json files"
    )
    parser.add_argument("--acc-min-delta", type=float, default=0.0)
    parser.add_argument("--cost-max-delta", type=float, default=0.0)
    parser.add_argument("--latency-max-delta", type=float, default=0.0)
    return parser


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
        report, pareto = aggregate_report(
            read_eval_rows(list(args.inputs)), inputs=list(args.inputs)
        )
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pareto_path = (
            Path(args.pareto_out) if args.pareto_out else out_path.with_name("pareto.json")
        )
        pareto_path.parent.mkdir(parents=True, exist_ok=True)
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
        store = ArtifactStore(default_layout(Path(args.art_root)))
        try:
            shared_inputs = sorted(list(args.inputs))
            report_src: ArtifactSource = {
                "tool": "pirml.report",
                "params": {"inputs": shared_inputs, "kind": "report"},
            }
            pareto_src: ArtifactSource = {
                "tool": "pirml.report",
                "params": {"inputs": shared_inputs, "kind": "pareto"},
            }
            report_aid = store.put_raw(
                json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                kind="report",
                mime="application/json",
                src=report_src,
            )
            pareto_aid = store.put_raw(
                json.dumps(pareto, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                kind="report",
                mime="application/json",
                src=pareto_src,
            )
        finally:
            store.close()
        report["artifacts"] = {
            "report_aid": report_aid,
            "pareto_aid": pareto_aid,
            "art_root": str(Path(args.art_root)),
        }
        out_path.write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        pareto_path.write_text(
            json.dumps(pareto, sort_keys=True, separators=(",", ":")), encoding="utf-8"
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
