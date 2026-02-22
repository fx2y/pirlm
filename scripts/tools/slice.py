from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_materialize import ViewMaterializer


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
    art_root = args.art_root
    if art_root == Path("art") and not art_root.exists() and Path(".pirml/artifacts").exists():
        art_root = Path(".pirml/artifacts")

    if not art_root.exists():
        print(f"Error: Artifact root not found: {art_root}", file=sys.stderr)
        sys.exit(1)

    try:
        # Load spec
        if Path(args.spec).exists():
            try:
                spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"Error: Failed to parse spec file: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            try:
                spec = json.loads(args.spec)
            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON spec string: {e}", file=sys.stderr)
                sys.exit(1)

        store = ArtifactStore(layout=default_layout(root=art_root))
        mat = ViewMaterializer(store)

        # C2.T01: same artifact+spec => identical view_id x3
        vid = mat.materialize(args.aid, spec)
        print(vid)

    except Exception as e:
        # T07: Typed fail lanes
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
