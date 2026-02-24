from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .cli_common import CliFailure, emit_failure, strict_parse_args
from .clock import SequenceClock
from .engine import run_live, run_replay
from .product.cmd_doctor import run_doctor_command
from .product.cmd_incident import run_incident_command
from .product.cmd_surface import run_surface_command
from .product.cmd_tool import run_tool_command
from .product.install_ext import run_install_command, run_uninstall_command
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

_PRODUCT_COMMANDS = frozenset(
    {"doctor", "install-pi-ext", "uninstall-pi-ext", "replay", "tool", "surface", "incident", "run"}
)


def build_legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pirml",
        description="PIRML Product Shell",
        epilog=(
            "Product commands: doctor, run, replay, tool, surface, incident, "
            "install-pi-ext, uninstall-pi-ext"
        ),
    )
    # Legacy flags (top-level)
    parser.add_argument("--prog", help="Path to Python program file defining PROGRAM list")
    parser.add_argument("--replay", help="Replay from existing trace.ndjson")
    parser.add_argument(
        "--out-dir", default="out", help="Output directory for trace.ndjson/final.json"
    )
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES_DEFAULT)
    parser.add_argument("--timeout", type=float, default=30.0, help="Global run timeout in seconds")

    # Subcommands
    sub = parser.add_subparsers(dest="product_cmd")
    sub.add_parser("doctor", help="Environment check")
    sub.add_parser("run", help="Unified run (delegates to scripts.pirml_run)")
    sub.add_parser("replay", help="Unified replay (delegates to scripts.tools.replay)")
    sub.add_parser("tool", help="Tool authoring (init|lint|pack)")
    sub.add_parser("surface", help="Surface resolver views (console|evidence|eval|policy)")
    sub.add_parser("incident", help="One-command incident triage")
    sub.add_parser("install-pi-ext", help="Install extension")
    sub.add_parser("uninstall-pi-ext", help="Uninstall extension")

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
    args = strict_parse_args(parser, argv)
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


def _cmd_run(argv: list[str]) -> int:
    # Delegate to scripts.pirml_run.main
    from scripts.pirml_run import main as run_main

    try:
        run_main(argv)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)


def _dispatch_product(cmd: str, argv: list[str]) -> int:
    if cmd == "doctor":
        return run_doctor_command(argv)
    if cmd == "install-pi-ext":
        return run_install_command(argv)
    if cmd == "uninstall-pi-ext":
        return run_uninstall_command(argv)
    if cmd == "replay":
        return _cmd_replay(argv)
    if cmd == "tool":
        return run_tool_command(argv)
    if cmd == "surface":
        return run_surface_command(argv)
    if cmd == "incident":
        return run_incident_command(argv)
    if cmd == "run":
        return _cmd_run(argv)
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

    # Handle legacy flags or help
    parser = build_legacy_parser()
    try:
        args = strict_parse_args(parser, raw_argv)
        if args.product_cmd:
            return _dispatch_product(args.product_cmd, raw_argv[1:])
        return _run_legacy(args)
    except CliFailure as err:
        return emit_failure(err)
    except ValueError as exc:
        return emit_failure(CliFailure("config", str(exc), 2, retryable=False))
    except (OSError, ProtocolError) as exc:
        return emit_failure(CliFailure("integrity", str(exc), 2, retryable=False))


if __name__ == "__main__":
    raise SystemExit(main())
