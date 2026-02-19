#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.check_call(cmd, env=env)


def main() -> int:
    base = Path("out/replay-check")
    live_dir = base / "live"
    replay_dir = base / "replay"

    if base.exists():
        shutil.rmtree(base)
    live_dir.mkdir(parents=True, exist_ok=True)
    replay_dir.mkdir(parents=True, exist_ok=True)

    live_cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        "tests/prog_ok.py",
        "--out-dir",
        str(live_dir),
    ]
    _run(live_cmd)
    live_hash = _sha256(live_dir / "final.json")

    replay_env = dict(os.environ)
    replay_env["PIRML_BLOCK_TOOLS"] = "1"
    replay_cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        "tests/prog_ok.py",
        "--replay",
        str(live_dir / "trace.ndjson"),
        "--out-dir",
        str(replay_dir),
    ]
    _run(replay_cmd, env=replay_env)
    replay_hash = _sha256(replay_dir / "final.json")

    if live_hash != replay_hash:
        print(f"hash mismatch: live={live_hash} replay={replay_hash}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
