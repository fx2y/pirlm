from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec
from pirml.artifacts.view_materialize import ViewMaterializer
from scripts.tools.common import emit_error, resolve_art_root


def _load_spec(raw_spec: str) -> SliceSpec:
    spec_path = Path(raw_spec)
    if spec_path.exists():
        try:
            return cast(SliceSpec, json.loads(spec_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            emit_error("validation", f"Failed to parse spec file: {e}", 1)
    try:
        return cast(SliceSpec, json.loads(raw_spec))
    except json.JSONDecodeError as e:
        emit_error("validation", f"Invalid JSON spec string: {e}", 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pirml-slice", description="Create artifact slices for RLM recursion."
    )
    parser.add_argument("aid", help="Artifact ID (AID)")
    parser.add_argument("spec", help="Slice specification (JSON string or path to JSON file)")
    parser.add_argument(
        "--art-root", type=Path, default=Path("art"), help="Artifact root directory (default: art)"
    )

    args = parser.parse_args()

    # C1.T04: Support .pirml projection if default art/ missing
    art_root = resolve_art_root(args.art_root)

    if not art_root.exists():
        emit_error("artifact", f"Artifact root not found: {art_root}", 1)

    try:
        spec = _load_spec(args.spec)
        store = ArtifactStore(layout=default_layout(root=art_root))
        mat = ViewMaterializer(store)

        # C2.T01: same artifact+spec => identical view_id x3
        vid = mat.materialize(args.aid, spec)
        print(vid)

    except Exception as e:
        emit_error("integrity", str(e), 2)


if __name__ == "__main__":
    main()
