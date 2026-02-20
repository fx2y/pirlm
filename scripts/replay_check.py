#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pirml.protocol import ProtocolError, load_jsonl


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.check_call(cmd, env=env)


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ProtocolError(f"{path} must contain a JSON object")
    return dict(cast(dict[str, Any], data))


def main() -> int:
    try:
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
        _run(replay_cmd)

        live_final = _load_json(live_dir / "final.json")
        replay_final = _load_json(replay_dir / "final.json")
        live_sha = _sha256_path(live_dir / "final.json")
        replay_sha = _sha256_path(replay_dir / "final.json")

        if live_final != replay_final:
            print("final.json mismatch", file=sys.stderr)
            return 1
        if live_sha != replay_sha:
            print("final.json hash mismatch", file=sys.stderr)
            return 1

        replay_frames = load_jsonl(replay_dir / "trace.ndjson")
        replay_final_frame = replay_frames[-1]
        meta = replay_final_frame.get("meta")
        if not isinstance(meta, dict):
            print("replay parity metadata missing in final trace frame", file=sys.stderr)
            return 1
        meta_map = cast(dict[str, Any], meta)
        if meta_map.get("replay_match") is not True:
            print("replay_match flag missing or False in replay trace metadata", file=sys.stderr)
            return 1
        if meta_map.get("replay_expected_final_sha256") != live_sha:
            print("replay_expected_final_sha256 mismatch", file=sys.stderr)
            return 1
        if meta_map.get("replay_actual_final_sha256") != replay_sha:
            print("replay_actual_final_sha256 mismatch", file=sys.stderr)
            return 1
    except (OSError, ProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
