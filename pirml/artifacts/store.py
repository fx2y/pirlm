from __future__ import annotations

import json
from typing import Any

from .errors import ArtifactErrorType, ArtifactPathError, artifact_error
from .index_sqlite import ArtifactsIndex
from .io import atomic_write, cas_path, sha256_bytes
from .paths import ArtifactLayout, default_layout
from .trace import ArtifactTraceWriter
from .types import ArtifactKind, ArtifactMeta, ArtifactRecord, ArtifactSource


class ArtifactStore:
    def __init__(self, layout: ArtifactLayout | None = None) -> None:
        self._layout = layout or default_layout()
        self._index = ArtifactsIndex(self._layout.index_path)
        self._trace = ArtifactTraceWriter(self._layout.trace_path)

    @property
    def layout(self) -> ArtifactLayout:
        return self._layout

    @property
    def index(self) -> ArtifactsIndex:
        return self._index

    @property
    def trace(self) -> ArtifactTraceWriter:
        return self._trace

    def close(self) -> None:
        """Close index connection."""
        self._index.close()

    def put_raw(
        self,
        data: bytes,
        *,
        kind: str | ArtifactKind,
        mime: str,
        parents: list[str] | None = None,
        src: ArtifactSource | None = None,
        notes: str | None = None,
    ) -> str:
        """C1.T06: Public store API for raw bytes"""
        sha = sha256_bytes(data)
        path = cas_path(self._layout.obj_dir, sha)

        # 1. CAS write
        atomic_write(path, data)

        # 2. Index write
        ts = self._trace.clock.now()
        rel_path = str(path.relative_to(self._layout.root))
        rec: ArtifactRecord = {
            "id": sha,
            "kind": str(kind),
            "mime": mime,
            "bytes": len(data),
            "sha256": sha,
            "path": rel_path,
            "parents": parents or [],
            "src": src or {},
            "ts": ts,
            "notes": notes,
        }
        self._index.put(rec)

        # 3. Trace write
        self._trace.append(
            ev="put",
            aid=sha,
            kind=str(kind),
            mime=mime,
            bytes=len(data),
            sha256=sha,
            path=rel_path,
            parents=parents or [],
            src=src or {},
            notes=notes,
            ts=ts,
        )

        return sha

    def put_json(
        self,
        value: Any,
        *,
        kind: str | ArtifactKind,
        parents: list[str] | None = None,
        src: ArtifactSource | None = None,
        notes: str | None = None,
    ) -> str:
        """C1.T06: Public store API for JSON objects"""
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.put_raw(
            data,
            kind=kind,
            mime="application/json",
            parents=parents,
            src=src,
            notes=notes,
        )

    def put_view(
        self,
        vid: str,
        aid: str,
        spec: Any,  # SliceSpec
        data: bytes,
        stats: dict[str, Any],
    ) -> str:
        """C2.T06: Link each view materialization into ArtifactFS index + trace events"""
        path = self._layout.views_dir / f"{vid}.ndjson"
        atomic_write(path, data)

        ts = self._trace.clock.now()
        rel_path = str(path.relative_to(self._layout.root))
        view_sha = sha256_bytes(data)

        rec: ArtifactRecord = {
            "id": vid,
            "kind": "slice",
            "mime": "application/x-ndjson",
            "bytes": len(data),
            "sha256": view_sha,
            "path": rel_path,
            "parents": [aid],
            "src": {"vid": vid, "aid": aid, "spec": spec, "stats": stats},
            "ts": ts,
            "notes": f"View {vid} for {aid}",
        }
        self._index.put(rec)

        self._trace.append(
            ev="view",
            aid=aid,
            vid=vid,
            spec=spec,
            stats=stats,
            sha256=view_sha,
            path=rel_path,
            ts=ts,
        )
        return vid

    def get_bytes(self, aid: str) -> bytes:
        """C1.T06: Retrieve artifact bytes by id"""
        path_str = self._index.get_path(aid)
        if not path_str:
            err = artifact_error(ArtifactErrorType.NOT_FOUND, f"Artifact not found: {aid}")
            raise ArtifactPathError(error_type=ArtifactErrorType.NOT_FOUND, msg=err["msg"])

        path = self._layout.root / path_str
        if not path.exists():
            err = artifact_error(ArtifactErrorType.INTEGRITY, f"Artifact file missing: {path}")
            raise ArtifactPathError(error_type=ArtifactErrorType.INTEGRITY, msg=err["msg"])

        return path.read_bytes()

    def get_meta(self, aid: str) -> ArtifactMeta | None:
        """C1.T06: Retrieve artifact metadata by id"""
        return self._index.get_meta(aid)

    def resolve_parents(self, aid: str) -> list[str]:
        """C1.T06: Retrieve parent ids for an artifact"""
        return self._index.resolve_parents(aid)

    def find_by_kind(self, kind: str) -> list[str]:
        """Retrieve artifact ids by kind."""
        return self._index.find_by_kind(kind)

    def get_view_text(self, vid: str) -> str:
        """Helper to read and concatenate text from an ndjson view."""
        path_str = self._index.get_path(vid)
        if not path_str:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.NOT_FOUND, msg=f"View missing: {vid}"
            )
        abs_path = self._layout.root / path_str
        texts: list[str] = []
        with abs_path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        row = json.loads(line)
                        texts.append(row.get("text", ""))
                    except json.JSONDecodeError:
                        continue
        return "\n".join(texts)

    def rebuild_index(self) -> None:
        """C1.T07: Rebuild sqlite index from trace.ndjson"""
        if self._layout.index_path.exists():
            self._index.close()
            # Clean up main file and sidecars (WAL/SHM)
            for p in [
                self._layout.index_path,
                self._layout.index_path.with_name(self._layout.index_path.name + "-shm"),
                self._layout.index_path.with_name(self._layout.index_path.name + "-wal"),
            ]:
                if p.exists():
                    p.unlink()

        self._index = ArtifactsIndex(self._layout.index_path)

        if not self._layout.trace_path.exists():
            return

        with self._layout.trace_path.open("r", encoding="utf-8") as f:
            for line in f:
                frame = json.loads(line)
                if frame.get("ev") == "put":
                    rec: ArtifactRecord = {
                        "id": frame["aid"],
                        "kind": frame["kind"],
                        "mime": frame["mime"],
                        "bytes": frame["bytes"],
                        "sha256": frame["sha256"],
                        "path": frame["path"],
                        "parents": frame["parents"],
                        "src": frame["src"],
                        "ts": frame["ts"],
                        "notes": frame.get("notes"),
                    }
                    self._index.put(rec)
                elif frame.get("ev") == "view":
                    rec: ArtifactRecord = {
                        "id": frame["vid"],
                        "kind": "slice",
                        "mime": "application/x-ndjson",
                        "bytes": len(
                            frame.get("sha256", "")
                        ),  # bytes not in view frame, but path exists
                        "sha256": frame["sha256"],
                        "path": frame["path"],
                        "parents": [frame["aid"]],
                        "src": {
                            "vid": frame["vid"],
                            "aid": frame["aid"],
                            "spec": frame["spec"],
                            "stats": frame["stats"],
                        },
                        "ts": frame["ts"],
                        "notes": f"View {frame['vid']} for {frame['aid']}",
                    }
                    # We need to get the actual byte length if we want perfection
                    p = self._layout.root / frame["path"]
                    if p.exists():
                        rec["bytes"] = p.stat().st_size
                    self._index.put(rec)
