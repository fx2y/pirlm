from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.tools.common import emit_error


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pirml-replay", description="Deterministic rerun from trace (debug)."
    )
    parser.add_argument("prog", help="Path to Python program file defining PROGRAM list")
    parser.add_argument("trace", help="Path to existing trace.ndjson")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("out/replay"),
        help="Output directory (default: out/replay)",
    )
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="Process timeout (default: 30.0)"
    )

    args = parser.parse_args()
    trace_path = Path(args.trace)
    if not trace_path.exists():
        emit_error("artifact", f"Trace not found: {trace_path}", 1)

    cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        str(args.prog),
        "--replay",
        str(trace_path),
        "--out-dir",
        str(args.out_dir),
        "--timeout",
        str(args.timeout),
    ]

    # C3.T05: wrapper output equals direct CLI; tool execution blocked
    try:
        # Replay lane MUST block tools (INV.1, R10)
        env = os.environ.copy()
        env["PIRML_BLOCK_TOOLS"] = "1"

        proc = subprocess.run(cmd, env=env)
        sys.exit(proc.returncode)
    except Exception as e:
        emit_error("integrity", str(e), 2)


if __name__ == "__main__":
    main()
