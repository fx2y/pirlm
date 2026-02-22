from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pirml.artifacts.errors import ArtifactPathError
from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from scripts.tools.common import emit_error, resolve_art_root


def main() -> None:
    parser = argparse.ArgumentParser(prog="pirml-open", description="Open artifacts/views by ID.")
    parser.add_argument("id", help="Artifact ID (AID) or View ID (VID)")
    parser.add_argument(
        "--mode",
        choices=["meta", "bytes", "text"],
        default="bytes",
        help="Display mode (default: bytes)",
    )
    parser.add_argument(
        "--art-root", type=Path, default=Path("art"), help="Artifact root directory (default: art)"
    )

    args = parser.parse_args()

    # C3.T02: Path decode policy: support path inputs by extracting ID
    target_id = args.id
    if "/" in target_id or "\\" in target_id or target_id.endswith(".ndjson"):
        from contextlib import suppress

        from pirml.artifacts.paths import parse_view_artifact_path

        with suppress(ArtifactPathError):
            target_id = parse_view_artifact_path(target_id)

    # C1.T04: Support .pirml projection if default art/ missing
    art_root = resolve_art_root(args.art_root)

    if not art_root.exists():
        emit_error("artifact", f"Artifact root not found: {art_root}", 1)

    try:
        store = ArtifactStore(layout=default_layout(root=art_root))

        if args.mode == "meta":
            meta = store.get_meta(target_id)
            if not meta:
                emit_error("artifact", f"artifact {target_id} not found", 1)
            print(json.dumps(meta, indent=2, sort_keys=True))
        elif args.mode == "text":
            try:
                # Try view text first
                text = store.get_view_text(target_id)
                print(text)
            except ArtifactPathError:
                # If not a view, try reading as raw bytes (best effort)
                try:
                    data = store.get_bytes(target_id)
                    try:
                        print(data.decode("utf-8"))
                    except UnicodeDecodeError:
                        emit_error("artifact", f"artifact {target_id} is binary", 1)
                except ArtifactPathError as e:
                    emit_error("artifact", str(e), 1)
        else:  # bytes
            try:
                data = store.get_bytes(target_id)
                sys.stdout.buffer.write(data)
            except ArtifactPathError as e:
                emit_error("artifact", str(e), 1)

    except Exception as e:
        emit_error("integrity", str(e), 2)


if __name__ == "__main__":
    main()
