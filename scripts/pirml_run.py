from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TypedDict

from pirml.ux.layout import derive_summary
from pirml.ux.runtime_bridge import run_once
from pirml.ux.types import PointerPayload, RunResult


class SummaryPayload(TypedDict, total=False):
    runId: str
    ok: bool
    summary: str | None
    pointer: PointerPayload | None
    error: Any | None


def _summary_payload(out_dir: Path, result: RunResult) -> SummaryPayload:
    summary: SummaryPayload = {
        "runId": result["runId"],
        "ok": result["ok"],
        "summary": derive_summary(out_dir),
        "pointer": result["pointer"],
    }
    if not result["ok"]:
        summary["error"] = result["error"]
    return summary


def _human_lines(summary: SummaryPayload) -> list[str]:
    pointer = summary.get("pointer")
    trace = ""
    final = ""
    if pointer is not None:
        trace = pointer.get("trace", "")
        final = pointer.get("final", "")
    lines = [
        f"runId: {summary.get('runId', '')}",
        f"ok: {summary.get('ok', False)}",
        f"summary: {summary.get('summary', '') or ''}",
        f"trace: {trace}",
        f"final: {final}",
    ]
    error = summary.get("error")
    if isinstance(error, dict):
        lines.append(f"error: {json.dumps(error, sort_keys=True)}")
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pirml_run")
    parser.add_argument("--prog", required=True, help="Path to Python program")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--replay", help="Replay from trace NDJSON")
    parser.add_argument("--timeout", type=float, default=60.0, help="Run timeout")
    parser.add_argument("--project-root", default=".", help="Project root for .pirml facade")
    parser.add_argument(
        "--human",
        action="store_true",
        help="Print concise operator summary instead of JSON envelope",
    )

    args = parser.parse_args(argv)

    try:
        res = run_once(
            prog_path=Path(args.prog),
            out_dir=Path(args.out_dir),
            replay_path=Path(args.replay) if args.replay else None,
            timeout=args.timeout,
            project_root=Path(args.project_root),
        )

        summary = _summary_payload(Path(args.out_dir), res)
        if args.human:
            print("\n".join(_human_lines(summary)))
        else:
            # S30: Headless summary row
            print(json.dumps(summary, indent=2))
        sys.exit(0 if res["ok"] else 1)

    except Exception as e:
        err_data = {
            "ok": False,
            "error": {"type": "integrity", "msg": str(e), "retryable": False},
        }
        print(json.dumps(err_data, indent=2), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
