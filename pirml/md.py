from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from .cli_common import CliFailure, emit_failure, strict_parse_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml.md")
    parser.add_argument("report_json", help="Path to report.json")
    return parser


def _load_report(path: str) -> dict[str, Any]:
    report_path = Path(path)
    if not report_path.is_file():
        raise CliFailure("unsupported", f"report path not found: {report_path}", 1, retryable=False)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CliFailure("validation", "report must be an object", 1, retryable=False)
    return cast(dict[str, Any], payload)


def _render(report: dict[str, Any]) -> str:
    lines = [
        "# PIRML Eval Report",
        "",
        "## Summary",
        f"- ok: {bool(report.get('ok', False))}",
        f"- total_tasks: {int(report.get('total_tasks', 0) or 0)}",
        f"- acc: {float(report.get('acc', 0.0) or 0.0):.6f}",
        f"- median_latency: {float(report.get('median_latency', 0.0) or 0.0):.6f}",
        f"- median_cost: {float(report.get('median_cost', 0.0) or 0.0):.6f}",
        "",
        "## Pareto",
    ]
    for row in report.get("fail_pareto", []):
        if not isinstance(row, dict):
            continue
        row_map = cast(dict[str, Any], row)
        lines.append(f"- {row_map.get('fail_tag', 'UNKNOWN')}: {int(row_map.get('count', 0) or 0)}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = strict_parse_args(parser, argv)
        sys.stdout.write(_render(_load_report(args.report_json)))
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
