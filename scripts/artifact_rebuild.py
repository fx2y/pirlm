#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore


def check_parity(root: Path) -> int:
    """I14: Filesystem->sqlite rebuild parity exact"""
    layout = default_layout(root)
    store = ArtifactStore(layout)

    # Get current index metadata
    # Better find all IDs from sqlite
    import sqlite3

    conn = sqlite3.connect(str(layout.index_path))
    ids: list[str] = [r[0] for r in conn.execute("SELECT id FROM artifacts").fetchall()]

    from pirml.artifacts.types import ArtifactMeta

    orig_metas: dict[str, ArtifactMeta | None] = {}
    for aid in ids:
        orig_metas[aid] = store.get_meta(aid)

    # Rebuild
    print(f"Rebuilding index for {root}...")
    store.rebuild_index()

    # Compare
    mismatches = 0
    for aid, orig_meta in orig_metas.items():
        new_meta = store.get_meta(aid)
        if orig_meta != new_meta:
            print(f"Mismatch for ID {aid}:")
            print(f"  Orig: {orig_meta}")
            print(f"  New:  {new_meta}")
            mismatches += 1

    if mismatches:
        print(f"FAILED: {mismatches} mismatches found")
        return 2

    print("SUCCESS: Parity confirmed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("out"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--export", type=Path, help="Export index to NDJSON")
    args = parser.parse_args()

    if args.export:
        layout = default_layout(args.root)
        import json
        import sqlite3

        conn = sqlite3.connect(str(layout.index_path))
        conn.row_factory = sqlite3.Row
        with args.export.open("w", encoding="utf-8") as f:
            for row in conn.execute("SELECT * FROM artifacts").fetchall():
                d = dict(row)
                aid = d["id"]
                # handle src_json
                if d.get("src_json"):
                    d["src"] = json.loads(d.pop("src_json"))
                else:
                    d["src"] = {}
                # parents
                parents = [
                    r[0]
                    for r in conn.execute(
                        "SELECT parent FROM parents WHERE child = ? ORDER BY pos", (aid,)
                    ).fetchall()
                ]
                d["parents"] = parents
                f.write(json.dumps(d) + "\n")
        print(f"Index exported to {args.export}")
        return 0

    if args.check:
        return check_parity(args.root)

    # Default: just rebuild
    layout = default_layout(args.root)
    store = ArtifactStore(layout)
    store.rebuild_index()
    print("Index rebuilt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
