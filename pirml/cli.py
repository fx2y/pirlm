from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .clock import SequenceClock
from .engine import run_live, run_replay
from .protocol import (
    MAX_LINE_BYTES_DEFAULT,
    ProtocolError,
    emit_stdout,
    load_jsonl,
    write_final,
    write_metrics,
    write_trace,
)
from .tools import default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml")
    parser.add_argument("--prog", help="Path to Python program file defining PROGRAM list")
    parser.add_argument("--replay", help="Replay from existing trace.ndjson")
    parser.add_argument(
        "--out-dir", default="out", help="Output directory for trace.ndjson/final.json"
    )
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES_DEFAULT)
    return parser


def _run(args: argparse.Namespace) -> int:
    max_line_bytes = int(args.max_line_bytes)
    if max_line_bytes <= 0:
        raise ValueError("--max-line-bytes must be > 0")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.ndjson"
    final_path = out_dir / "final.json"
    metrics_path = out_dir / "metrics.csv"

    if args.replay:
        if not args.prog:
            raise ValueError("--prog is required for --replay to verify call sequence")
        replay_frames = load_jsonl(Path(args.replay))
        output = run_replay(
            program_path=Path(args.prog),
            replay_frames=replay_frames,
            clock=SequenceClock.from_env(),
            max_line_bytes=max_line_bytes,
        )
    else:
        if not args.prog:
            raise ValueError("--prog is required unless --replay is provided")
        output = run_live(
            program_path=Path(args.prog),
            registry=default_registry(),
            clock=SequenceClock.from_env(),
            max_line_bytes=max_line_bytes,
        )

    normalized = write_trace(trace_path, output.frames, max_line_bytes=max_line_bytes)
    write_final(final_path, output.final_result)
    write_metrics(
        metrics_path,
        normalized,
        output.final_result,
        trace_path=trace_path,
        final_path=final_path,
    )
    emit_stdout(normalized, max_line_bytes=max_line_bytes)

    ok = output.final_result.get("ok")
    return 0 if ok is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
