from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from pirml.protocol import JSONObject


def run_cli(
    *,
    program: str,
    out_dir: Path,
    replay: Path | None = None,
    max_line_bytes: int | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        program,
        "--out-dir",
        str(out_dir),
    ]
    if replay is not None:
        cmd.extend(["--replay", str(replay)])
    if max_line_bytes is not None:
        cmd.extend(["--max-line-bytes", str(max_line_bytes)])

    return subprocess.run(
        cmd,
        capture_output=True,
        check=False,
        env=dict(env) if env is not None else None,
        text=True,
    )


def parse_stdout_frames(stdout: str) -> list[JSONObject]:
    lines = [line for line in stdout.splitlines() if line]
    return [json.loads(line) for line in lines]
