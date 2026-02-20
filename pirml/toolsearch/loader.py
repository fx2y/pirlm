from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from pirml.contracts.schemas import ToolManifest
from pirml.runtime.rpc import canonical_json


def load_catalog(tools_dir: str | Path, strict: bool = False) -> dict[str, ToolManifest]:
    """C1.T2: Canonical tool loader.
    Same input files -> byte-identical catalog object.
    G.P1.1: Added strict mode for linting/CI.
    """
    catalog: dict[str, ToolManifest] = {}
    name_to_path: dict[str, Path] = {}

    # glob is not guaranteed to be sorted on all OS
    paths = sorted(Path(tools_dir).glob("*.json"))
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name")
            if not isinstance(name, str):
                if strict:
                    raise HydrationError(
                        "missing_name", f"Manifest at {path} missing 'name' string"
                    )
                continue

            if name in name_to_path:
                if strict:
                    raise HydrationError(
                        "duplicate_name",
                        f"Duplicate tool name '{name}' found in {path} and {name_to_path[name]}",
                    )
                # In non-strict mode, we skip duplicates to stay permissive
                continue

            catalog[name] = data
            name_to_path[name] = path
        except (json.JSONDecodeError, OSError) as e:
            if strict:
                raise HydrationError("load_failed", f"Failed to load {path}: {e}") from e
            # Loader is permissive; Linter is strict
            continue

    # Return dict sorted by key for iteration determinism
    return {k: catalog[k] for k in sorted(catalog.keys())}


class HydrationError(Exception):
    def __init__(self, type: str, msg: str):
        self.type = type
        self.msg = msg
        super().__init__(f"{type}: {msg}")


def hydrate_tools(names: list[str], catalog: Mapping[str, ToolManifest]) -> list[ToolManifest]:
    """C3.T1: Strict name->manifest expansion preserving input order."""
    hydrated: list[ToolManifest] = []
    for name in names:
        if name not in catalog:
            raise HydrationError("missing_ref", f"Tool '{name}' not found in catalog")
        hydrated.append(catalog[name])
    return hydrated


def load_selected(names: list[str], tools_dir: str | Path) -> list[ToolManifest]:
    """C3.T2: Enforce selected-only expansion (never full catalog) in public APIs.
    Loads only the specified tools from disk.
    """
    tools: list[ToolManifest] = []
    for name in names:
        path = Path(tools_dir) / f"{name}.json"
        if not path.exists():
            raise HydrationError("missing_ref", f"Tool '{name}' file not found: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("name") != name:
                raise HydrationError(
                    "inconsistent_name",
                    f"File {path} contains tool '{data.get('name')}', expected '{name}'",
                )
            tools.append(data)
        except (json.JSONDecodeError, OSError) as e:
            raise HydrationError("load_failed", str(e)) from e
    return tools


def catalog_hash(catalog: Mapping[str, ToolManifest]) -> str:
    """C1.T2: Deterministic catalog hash."""
    # canonical_json sorts keys recursively
    return hashlib.sha256(canonical_json(catalog).encode("utf-8")).hexdigest()
