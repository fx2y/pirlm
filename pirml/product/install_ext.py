from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from pirml.cli_common import CliFailure

_TARGETS = frozenset({"global", "project"})


def _resolve_source_dir(source_dir: str) -> Path:
    path = Path(source_dir).expanduser().resolve()
    if not path.is_dir():
        raise CliFailure("unsupported", f"extension source not found: {path}", 1, retryable=False)
    return path


def _resolve_target_path(*, target: str, home: Path, project_root: Path) -> Path:
    if target == "global":
        return (home / ".pi/agent/extensions/pirml").resolve()
    if target == "project":
        return (project_root / ".pi/extensions/pirml").resolve()
    raise CliFailure("config", f"unknown target: {target}", 2, retryable=False)


def _safe_replace_tree(destination: Path, source: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    shutil.copytree(source, destination)


def _safe_remove_tree(destination: Path) -> bool:
    if not destination.exists() and not destination.is_symlink():
        return False
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    else:
        destination.unlink()
    return True


def _build_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--target", default="project", help="Install target: global|project")
    parser.add_argument(
        "--source-dir",
        default=".pi/extensions/pirml",
        help="Extension source directory (default: .pi/extensions/pirml)",
    )
    parser.add_argument("--project-root", default=".", help="Project root")
    parser.add_argument("--home", default=None, help="Override home for deterministic testing")
    return parser


def run_install_command(argv: list[str]) -> int:
    parser = _build_parser("pirml install-pi-ext")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        raise CliFailure("config", f"unknown args: {' '.join(unknown)}", 2, retryable=False)
    if args.target not in _TARGETS:
        raise CliFailure("config", f"unknown target: {args.target}", 2, retryable=False)

    home = Path(args.home).expanduser() if args.home else Path.home()
    project_root = Path(args.project_root).resolve()
    source = _resolve_source_dir(args.source_dir)
    destination = _resolve_target_path(target=args.target, home=home, project_root=project_root)
    _safe_replace_tree(destination, source)
    print(
        json.dumps(
            {
                "ok": True,
                "op": "install",
                "target": args.target,
                "path": str(destination),
                "source": str(source),
            },
            sort_keys=True,
        ),
        file=sys.stdout,
    )
    return 0


def run_uninstall_command(argv: list[str]) -> int:
    parser = _build_parser("pirml uninstall-pi-ext")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        raise CliFailure("config", f"unknown args: {' '.join(unknown)}", 2, retryable=False)
    if args.target not in _TARGETS:
        raise CliFailure("config", f"unknown target: {args.target}", 2, retryable=False)

    home = Path(args.home).expanduser() if args.home else Path.home()
    project_root = Path(args.project_root).resolve()
    destination = _resolve_target_path(target=args.target, home=home, project_root=project_root)
    removed = _safe_remove_tree(destination)
    print(
        json.dumps(
            {
                "ok": True,
                "op": "uninstall",
                "target": args.target,
                "path": str(destination),
                "removed": removed,
            },
            sort_keys=True,
        ),
        file=sys.stdout,
    )
    return 0
