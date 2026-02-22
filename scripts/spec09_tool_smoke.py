from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_module(module: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="spec09 smoke: tool init -> lint -> run -> replay")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve()
    source_tools_dir = project_root / "tools"
    if not source_tools_dir.is_dir():
        print(
            json.dumps(
                {
                    "type": "config",
                    "msg": f"missing tools directory: {source_tools_dir}",
                    "retryable": False,
                }
            ),
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory(prefix="spec09_c3_smoke_") as tmp:
        root = Path(tmp)
        tools_dir = root / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(source_tools_dir.glob("*.json")):
            shutil.copy2(path, tools_dir / path.name)

        init_proc = _run_module(
            "pirml",
            "tool",
            "init",
            "demo.spec09_smoke",
            "--tools-dir",
            str(tools_dir),
            cwd=project_root,
        )
        if init_proc.returncode != 0:
            print(init_proc.stderr, end="", file=sys.stderr)
            return int(init_proc.returncode)

        lint_proc = _run_module(
            "pirml", "tool", "lint", "--tools-dir", str(tools_dir), cwd=project_root
        )
        if lint_proc.returncode != 0:
            print(lint_proc.stderr, end="", file=sys.stderr)
            return int(lint_proc.returncode)

        out_dir = root / "run"
        run_proc = _run_module(
            "scripts.pirml_run",
            "--prog",
            "tests/prog_ok.py",
            "--out-dir",
            str(out_dir),
            "--project-root",
            str(project_root),
            cwd=project_root,
        )
        if run_proc.returncode != 0:
            print(run_proc.stderr, end="", file=sys.stderr)
            return int(run_proc.returncode)
        live_trace = out_dir / "trace.ndjson"
        live_final = out_dir / "final.json"
        if not live_trace.is_file() or not live_final.is_file():
            print(
                json.dumps(
                    {"type": "integrity", "msg": "missing run artifacts", "retryable": False}
                ),
                file=sys.stderr,
            )
            return 2

        replay_dir = root / "replay"
        replay_proc = _run_module(
            "scripts.tools.replay",
            "tests/prog_ok.py",
            str(live_trace),
            "--out-dir",
            str(replay_dir),
            cwd=project_root,
        )
        if replay_proc.returncode != 0:
            print(replay_proc.stderr, end="", file=sys.stderr)
            return int(replay_proc.returncode)
        replay_final = replay_dir / "final.json"
        replay_trace = replay_dir / "trace.ndjson"
        if not replay_final.is_file() or not replay_trace.is_file():
            print(
                json.dumps(
                    {"type": "integrity", "msg": "missing replay artifacts", "retryable": False}
                ),
                file=sys.stderr,
            )
            return 2
        if live_final.read_bytes() != replay_final.read_bytes():
            print(
                json.dumps(
                    {"type": "integrity", "msg": "live/replay final mismatch", "retryable": False}
                ),
                file=sys.stderr,
            )
            return 2
        print(
            json.dumps(
                {
                    "ok": True,
                    "tool_init": "demo.spec09_smoke",
                    "tool_manifest_sha256": _sha256(tools_dir / "demo.spec09_smoke.json"),
                    "live_final_sha256": _sha256(live_final),
                    "live_trace_sha256": _sha256(live_trace),
                    "replay_final_sha256": _sha256(replay_final),
                    "replay_trace_sha256": _sha256(replay_trace),
                },
                sort_keys=True,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
