from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pirml.contracts.schemas import ToolManifest
from pirml.runtime.rpc import canonical_json


def load_catalog(tools_dir: str | Path) -> dict[str, ToolManifest]:
    """C1.T2: Canonical tool loader.
    Same input files -> byte-identical catalog object.
    """
    catalog: dict[str, ToolManifest] = {}
    # glob is not guaranteed to be sorted on all OS
    paths = sorted(Path(tools_dir).glob("*.json"))
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name")
            if isinstance(name, str):
                catalog[name] = data
        except (json.JSONDecodeError, OSError):
            # Loader is permissive; Linter is strict
            continue

    # Return dict sorted by key for iteration determinism
    return {k: catalog[k] for k in sorted(catalog.keys())}


def catalog_hash(catalog: dict[str, ToolManifest]) -> str:
    """C1.T2: Deterministic catalog hash."""
    # canonical_json sorts keys recursively
    return hashlib.sha256(canonical_json(catalog).encode("utf-8")).hexdigest()
