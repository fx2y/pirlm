from __future__ import annotations

import argparse
import json
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.types import ArtifactMeta
from scripts.tools.common import emit_error, resolve_art_root


def _src_url(meta: ArtifactMeta) -> str:
    raw = meta["src"].get("url")
    if isinstance(raw, str):
        return raw
    return ""


def _matches(meta: ArtifactMeta, *, url: str | None) -> bool:
    if url is None:
        return True
    return url.lower() in _src_url(meta).lower()


def _contains_text(store: ArtifactStore, aid: str, needle: str) -> bool:
    path = store.index.get_path(aid)
    if path is None:
        return False
    data = store.get_bytes(aid)
    return needle.lower() in data.decode("utf-8", errors="ignore").lower()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pirml-search",
        description="Search artifacts by metadata/content in deterministic order.",
    )
    parser.add_argument("--kind", help="Filter artifact kind")
    parser.add_argument("--url", help="Filter by source URL substring")
    parser.add_argument("--contains", help="Filter by UTF-8 content substring")
    parser.add_argument("--limit", type=int, default=20, help="Max rows to output (default: 20)")
    parser.add_argument("--json", action="store_true", help="Emit JSON rows")
    parser.add_argument(
        "--art-root", type=Path, default=Path("art"), help="Artifact root directory (default: art)"
    )
    args = parser.parse_args()

    if args.limit < 1:
        emit_error("validation", "--limit must be >= 1", 1)

    art_root = resolve_art_root(args.art_root)
    if not art_root.exists():
        emit_error("artifact", f"Artifact root not found: {art_root}", 1)

    try:
        store = ArtifactStore(layout=default_layout(root=art_root))
        rows = store.list_meta(kind=args.kind)
        out: list[dict[str, object]] = []
        for meta in rows:
            if not _matches(meta, url=args.url):
                continue
            if args.contains and not _contains_text(store, str(meta["id"]), args.contains):
                continue
            out.append(
                {
                    "id": meta["id"],
                    "kind": meta["kind"],
                    "bytes": meta["bytes"],
                    "ts": meta["ts"],
                    "url": _src_url(meta),
                    "path": store.index.get_path(str(meta["id"])) or "",
                }
            )
            if len(out) >= args.limit:
                break

        if args.json:
            print(json.dumps(out, sort_keys=True, separators=(",", ":")))
        else:
            for row in out:
                print(
                    f"{row['id']} kind={row['kind']} bytes={row['bytes']} ts={row['ts']} "
                    f"url={row['url']} path={row['path']}"
                )
    except Exception as exc:
        emit_error("integrity", str(exc), 2)


if __name__ == "__main__":
    main()
