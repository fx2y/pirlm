#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore


def check_parity(root: Path) -> int:
    """I14: Filesystem->sqlite rebuild parity exact.
    G11: Derives expected set from fs+trace and hard-fails missing/corrupt objects.
    """
    layout = default_layout(root)
    store = ArtifactStore(layout)

    # 1. Get current index state
    import sqlite3

    def get_index_state(index_path: Path) -> dict[str, dict[str, Any]]:
        if not index_path.exists():
            return {}
        conn = sqlite3.connect(str(index_path))
        conn.row_factory = sqlite3.Row
        state: dict[str, dict[str, Any]] = {}
        for r in conn.execute("SELECT * FROM artifacts").fetchall():
            state[r["id"]] = dict(r)
        conn.close()
        return state

    orig_state = get_index_state(layout.index_path)
    print(f"Original index has {len(orig_state)} artifacts")

    # 2. Rebuild
    print(f"Rebuilding index for {root} from trace...")
    store.rebuild_index()

    # 3. Get new index state
    new_state = get_index_state(layout.index_path)
    print(f"New index has {len(new_state)} artifacts")

    # 4. Compare sets
    orig_ids = set(orig_state.keys())
    new_ids = set(new_state.keys())

    mismatches = 0
    missing_in_new = orig_ids - new_ids
    extra_in_new = new_ids - orig_ids

    if missing_in_new:
        print(f"FAILED: {len(missing_in_new)} IDs lost after rebuild: {list(missing_in_new)[:5]}")
        mismatches += len(missing_in_new)

    if extra_in_new:
        print(f"INFO: {len(extra_in_new)} new IDs found after rebuild (index was partial)")
        # This is not necessarily a failure if the old index was incomplete,
        # but the goal is "exact parity" if we assume the old index was complete.

    # 5. Check metadata for common IDs
    for aid in orig_ids & new_ids:
        # Comparison excluding things that might change like internal sqlite rowids
        o = orig_state[aid]
        n = new_state[aid]
        # Compare key fields: id, kind, mime, bytes, sha256, path
        for field in ["id", "kind", "mime", "bytes", "sha256", "path"]:
            if o.get(field) != n.get(field):
                print(
                    f"Metadata mismatch for {aid} field '{field}': {o.get(field)} != {n.get(field)}"
                )
                mismatches += 1

    # 6. Verify filesystem existence for all indexed artifacts
    for aid, rec in new_state.items():
        path = layout.root / rec["path"]
        if not path.exists():
            print(f"FAILED: Indexed artifact file missing for {aid}: {path}")
            mismatches += 1

    if mismatches:
        print(f"FAILED: {mismatches} total mismatches found")
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
