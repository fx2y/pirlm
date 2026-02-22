from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from pirml.cli_common import CliFailure


def _check_path(home: Path) -> dict[str, object]:
    expected = str(home / ".local/bin")
    path = os.environ.get("PATH", "")
    if expected in path.split(":"):
        return {"check": "path_local_bin", "ok": True, "path": expected}
    return {
        "check": "path_local_bin",
        "ok": False,
        "path": expected,
        "fix": 'export PATH="$HOME/.local/bin:$PATH"',
        "error": {
            "type": "config",
            "msg": f"PATH missing {expected}",
            "retryable": False,
        },
    }


def _check_pipx() -> dict[str, object]:
    binary = shutil.which("pipx")
    if binary:
        return {"check": "pipx", "ok": True, "path": binary}
    return {
        "check": "pipx",
        "ok": False,
        "fix": "python -m pip install --user pipx && python -m pipx ensurepath",
        "error": {"type": "unsupported", "msg": "pipx not found in PATH", "retryable": False},
    }


def _check_path_exists(check: str, path: Path, fix: str) -> dict[str, object]:
    if path.exists():
        return {"check": check, "ok": True, "path": str(path)}
    return {
        "check": check,
        "ok": False,
        "path": str(path),
        "fix": fix,
        "error": {"type": "unsupported", "msg": f"path not found: {path}", "retryable": False},
    }


def run_doctor_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pirml doctor")
    parser.add_argument("--project-root", default=".", help="Project root")
    parser.add_argument("--home", default=None, help="Override home for deterministic checks")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        raise CliFailure("config", f"unknown args: {' '.join(unknown)}", 2, retryable=False)

    home = Path(args.home).expanduser() if args.home else Path.home()
    project_root = Path(args.project_root).resolve()
    global_ext_dir = home / ".pi/agent/extensions"
    project_ext_dir = project_root / ".pi/extensions"
    global_ext = global_ext_dir / "pirml"
    project_ext = project_ext_dir / "pirml"

    rows = [
        _check_path(home),
        _check_pipx(),
        _check_path_exists(
            "global_extensions_dir",
            global_ext_dir,
            "mkdir -p ~/.pi/agent/extensions",
        ),
        _check_path_exists(
            "project_extensions_dir",
            project_ext_dir,
            "mkdir -p .pi/extensions",
        ),
    ]
    if global_ext.exists() or project_ext.exists():
        rows.append(
            {
                "check": "extension_presence",
                "ok": True,
                "paths": [str(project_ext), str(global_ext)],
            }
        )
    else:
        rows.append(
            {
                "check": "extension_presence",
                "ok": False,
                "paths": [str(project_ext), str(global_ext)],
                "fix": "pirml install-pi-ext --target project",
                "error": {
                    "type": "unsupported",
                    "msg": "pirml extension not installed (project/global)",
                    "retryable": False,
                },
            }
        )

    for row in rows:
        print(json.dumps(row, sort_keys=True), file=sys.stdout)
    return 0 if all(bool(row.get("ok")) for row in rows) else 1
