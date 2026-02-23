from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pirml.contracts.schemas import ManifestError, ToolManifest
from pirml.toolsearch.lint import lint_catalog, lint_manifest
from pirml.toolsearch.loader import load_catalog


@dataclass(frozen=True)
class LintFailure(Exception):
    err_type: str
    msg: str
    code: int
    retryable: bool = False


def lint_tools_dir(
    tools_dir: Path, *, enforce_hot_count: bool = True
) -> tuple[dict[str, ToolManifest], list[ManifestError]]:
    if not tools_dir.exists():
        raise LintFailure("config", f"tools directory not found: {tools_dir}", 2, False)

    try:
        catalog = load_catalog(tools_dir, strict=True)
    except Exception as exc:  # strict loader already maps deterministic error types
        raise LintFailure("integrity", str(exc), 2, False) from exc

    if not catalog:
        raise LintFailure("validation", f"no manifests found in {tools_dir}", 1, False)

    return catalog, lint_catalog(catalog, enforce_hot_count=enforce_hot_count)


__all__ = ["lint_manifest", "lint_catalog", "lint_tools_dir", "LintFailure"]
