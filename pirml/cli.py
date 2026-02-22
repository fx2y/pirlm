from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .cli_common import CliFailure, emit_failure
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

_PRODUCT_COMMANDS = frozenset({"doctor", "install-pi-ext", "uninstall-pi-ext", "replay", "tool"})


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pirml",
        epilog=(
            "Product commands: doctor, install-pi-ext, uninstall-pi-ext, replay, "
            "tool <init|lint|pack>"
        ),
    )
    parser.add_argument("--prog", help="Path to Python program file defining PROGRAM list")
    parser.add_argument("--replay", help="Replay from existing trace.ndjson")
    parser.add_argument(
        "--out-dir", default="out", help="Output directory for trace.ndjson/final.json"
    )
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES_DEFAULT)
    parser.add_argument("--timeout", type=float, default=30.0, help="Global run timeout in seconds")
    return parser


def _run_legacy(args: argparse.Namespace) -> int:
    max_line_bytes = int(args.max_line_bytes)
    if max_line_bytes <= 0:
        raise ValueError("--max-line-bytes must be > 0")

    timeout = float(args.timeout)
    if timeout <= 0:
        raise ValueError("--timeout must be > 0")

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
            timeout=timeout,
        )
    else:
        if not args.prog:
            raise ValueError("--prog is required unless --replay is provided")
        output = run_live(
            program_path=Path(args.prog),
            registry=default_registry(),
            clock=SequenceClock.from_env(),
            max_line_bytes=max_line_bytes,
            timeout=timeout,
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

    if output.protocol_error:
        return 2

    ok = output.final_result.get("ok")
    return 0 if ok is True else 1


def _main_legacy(argv: list[str] | None) -> int:
    parser = build_legacy_parser()
    args = parser.parse_args(argv)
    try:
        return _run_legacy(args)
    except (OSError, ProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _cmd_doctor(argv: list[str]) -> int:
    from .product.cmd_doctor import run_doctor_command

    return run_doctor_command(argv)


def _cmd_install(argv: list[str]) -> int:
    from .product.install_ext import run_install_command

    return run_install_command(argv)


def _cmd_uninstall(argv: list[str]) -> int:
    from .product.install_ext import run_uninstall_command

    return run_uninstall_command(argv)


def _cmd_replay(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pirml replay")
    parser.add_argument("prog", help="Path to Python program file defining PROGRAM list")
    parser.add_argument("trace", help="Path to existing trace.ndjson")
    parser.add_argument(
        "--out-dir",
        default="out/replay",
        help="Output directory (default: out/replay)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Process timeout seconds (default: 30.0)",
    )
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        raise CliFailure("config", f"unknown args: {' '.join(unknown)}", 2, retryable=False)
    cmd = [
        sys.executable,
        "-m",
        "scripts.tools.replay",
        str(args.prog),
        str(args.trace),
        "--out-dir",
        str(args.out_dir),
        "--timeout",
        str(args.timeout),
    ]
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


def _cmd_tool(argv: list[str]) -> int:
    from .product.cmd_tool import run_tool_command

    return run_tool_command(argv)


def _dispatch_product(cmd: str, argv: list[str]) -> int:
    if cmd == "doctor":
        return _cmd_doctor(argv)
    if cmd == "install-pi-ext":
        return _cmd_install(argv)
    if cmd == "uninstall-pi-ext":
        return _cmd_uninstall(argv)
    if cmd == "replay":
        return _cmd_replay(argv)
    if cmd == "tool":
        return _cmd_tool(argv)
    raise CliFailure("config", f"unknown command: {cmd}", 2, retryable=False)


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and not raw_argv[0].startswith("-"):
        cmd = raw_argv[0]
        if cmd in _PRODUCT_COMMANDS:
            try:
                return _dispatch_product(cmd, raw_argv[1:])
            except CliFailure as err:
                return emit_failure(err)
            except Exception as exc:
                print(
                    json.dumps({"type": "integrity", "msg": str(exc), "retryable": False}),
                    file=sys.stderr,
                )
                return 2
        return emit_failure(CliFailure("config", f"unknown command: {cmd}", 2, retryable=False))
    return _main_legacy(raw_argv)


if __name__ == "__main__":
    raise SystemExit(main())
