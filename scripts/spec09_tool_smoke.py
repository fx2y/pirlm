from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pirml", *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="spec09 C3 smoke: tool init -> lint -> run")
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

        init_proc = _run(
            "tool", "init", "demo.spec09_smoke", "--tools-dir", str(tools_dir), cwd=project_root
        )
        if init_proc.returncode != 0:
            print(init_proc.stderr, end="", file=sys.stderr)
            return int(init_proc.returncode)

        lint_proc = _run("tool", "lint", "--tools-dir", str(tools_dir), cwd=project_root)
        if lint_proc.returncode != 0:
            print(lint_proc.stderr, end="", file=sys.stderr)
            return int(lint_proc.returncode)

        out_dir = root / "run"
        run_proc = _run("--prog", "tests/prog_ok.py", "--out-dir", str(out_dir), cwd=project_root)
        if run_proc.returncode != 0:
            print(run_proc.stderr, end="", file=sys.stderr)
            return int(run_proc.returncode)
        if not (out_dir / "trace.ndjson").is_file() or not (out_dir / "final.json").is_file():
            print(
                json.dumps(
                    {"type": "integrity", "msg": "missing run artifacts", "retryable": False}
                ),
                file=sys.stderr,
            )
            return 2
        print(
            json.dumps(
                {
                    "ok": True,
                    "tool_init": "demo.spec09_smoke",
                    "tools_dir": str(tools_dir),
                    "out_dir": str(out_dir),
                },
                sort_keys=True,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
