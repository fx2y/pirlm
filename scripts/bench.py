#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if shutil.which("hyperfine") is None:
        print("hyperfine is not installed", file=sys.stderr)
        return 1

    out_dir = Path("out")
    out_dir.mkdir(parents=True, exist_ok=True)

    command = f"{sys.executable} -m pirml --prog tests/prog_ok.py --out-dir out/bench-run"
    subprocess.check_call(
        [
            "hyperfine",
            "--warmup",
            "3",
            "--export-json",
            str(out_dir / "bench.json"),
            command,
        ]
    )
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
