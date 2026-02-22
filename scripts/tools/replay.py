from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _typed_error(err_type: str, msg: str, retryable: bool = False) -> dict[str, object]:
    return {"type": err_type, "msg": msg, "retryable": retryable}


def _emit_error(err_type: str, msg: str, code: int) -> None:
    print(json.dumps(_typed_error(err_type, msg)), file=sys.stderr)
    sys.exit(code)


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

    cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        str(args.prog),
        "--replay",
        str(args.trace),
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
        _emit_error("integrity", str(e), 2)


if __name__ == "__main__":
    main()
