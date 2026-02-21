from __future__ import annotations

import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

from pirml.artifacts.errors import ArtifactErrorType, ArtifactPathError
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec, ViewOpSpec, view_id_for


class HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.bad = 0
        self.out: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self.bad += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self.bad:
            self.bad -= 1

    def handle_data(self, data: str) -> None:
        if not self.bad:
            d = data.strip()
            if d:
                self.out.append(d)


class ViewMaterializer:
    def __init__(self, store: ArtifactStore) -> None:
        self._store = store
        self._layout = store.layout

    def materialize(self, aid: str, spec: SliceSpec) -> str:
        vid = view_id_for(aid, spec)

        # C2.T01: same artifact+spec => identical view_id x3
        meta = self._store.get_meta(vid)
        if meta:
            return vid

        path_str = self._store.index.get_path(aid)
        if not path_str:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.NOT_FOUND,
                msg=f"Artifact not found: {aid}",
            )
        abs_path = self._layout.root / path_str

        op = spec["op"]
        if op == "lines":
            rows = self._slice_lines(abs_path, spec.get("a", 0), spec.get("b", 0))
        elif op == "regex":
            rows = self._slice_regex(abs_path, spec.get("pat", ""), spec.get("max_hits", 200))
        elif op == "bytes":
            rows = self._slice_bytes(abs_path, spec.get("offset", 0), spec.get("limit", 0))
        elif op == "html_text":
            rows = self._slice_html_text(abs_path)
        else:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.VIEW_OP_UNSUPPORTED,
                msg=f"Unsupported view op: {op}",
            )

        # C2.T07: Integrate ETL ops (post-process)
        post_ops = spec.get("post", [])
        if post_ops:
            # Post ops currently require full list (select_top, join, etc)
            # This is the memory bottleneck for large results, but okay for typical slices.
            rows_list = list(rows)
            for pop in post_ops:
                rows_list = self._apply_post_op(rows_list, pop)
            rows = iter(rows_list)

        # G09: Streaming materialization via ArtifactStore.put_view_stream
        self._store.put_view_stream(vid, aid, spec, rows)

        return vid

    def _slice_lines(self, path: Path, a: int, b: int) -> Iterator[dict[str, Any]]:
        # C2.T02: Implement lines slice (stream)
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if a <= i <= b:
                    yield {"line": i, "text": line.rstrip("\n")}
                if i > b:
                    break

    def _slice_regex(self, path: Path, pat: str, max_hits: int) -> Iterator[dict[str, Any]]:
        # C2.T02: Implement regex slice (stream)
        rx = re.compile(pat)
        hits = 0
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if rx.search(line):
                    yield {"line": i, "text": line.rstrip("\n")}
                    hits += 1
                    if hits >= max_hits:
                        break

    def _slice_bytes(self, path: Path, offset: int, limit: int) -> Iterator[dict[str, Any]]:
        # C2.T02: Implement bytes slice (bounded)
        with path.open("rb") as f:
            f.seek(offset)
            data = f.read(limit)
            yield {
                "offset": offset,
                "bytes": len(data),
                "text": data.decode("utf-8", errors="replace"),
            }

    def _slice_html_text(self, path: Path) -> Iterator[dict[str, Any]]:
        # G09: Stream HTML text extraction
        p = HtmlToText()
        with path.open("r", encoding="utf-8", errors="replace") as f:
            while True:
                chunk = f.read(16384)
                if not chunk:
                    break
                p.feed(chunk)

        for i, line in enumerate(p.out):
            line = line.strip()
            if line:
                yield {"line": i, "text": line}

    def _apply_post_op(self, rows: list[dict[str, Any]], pop: ViewOpSpec) -> list[dict[str, Any]]:
        op = pop["op"]
        params = pop.get("params", {})

        from pirml.web.etl import select_top_chunks, stable_chunk_sort
        from pirml.web.etl_join import join_chunks
        from pirml.web.etl_score import score_bm25
        from pirml.web.types import ChunkRow

        # Adapt rows to ChunkRow for existing ETL ops
        adapted: list[ChunkRow] = []
        for i, r in enumerate(rows):
            chunk = cast(ChunkRow, r.copy())
            if "chunk_id" not in chunk:
                chunk["chunk_id"] = str(r.get("line") or r.get("offset") or i)
            if "text" not in chunk:
                chunk["text"] = ""
            if "score" not in chunk:
                chunk["score"] = 0.0
            if "url" not in chunk:
                chunk["url"] = "internal://artifact"
            if "doc_sha256" not in chunk:
                chunk["doc_sha256"] = "0" * 64
            if "source_rank" not in chunk:
                chunk["source_rank"] = 0
            if "doc_rank" not in chunk:
                chunk["doc_rank"] = 0
            if "kind" not in chunk:
                chunk["kind"] = "slice"
            if "path_hint" not in chunk:
                chunk["path_hint"] = "view"
            adapted.append(chunk)

        result: list[ChunkRow] | list[dict[str, Any]]
        if op == "score":
            query = cast(str, params.get("query", ""))
            result = score_bm25(adapted, query=query)
        elif op == "join" or op == "dedup":
            result = join_chunks(adapted)
        elif op == "limit":
            n = cast(int, params.get("n", 40))
            result = select_top_chunks(adapted, n=n)
        elif op == "sort":
            result = stable_chunk_sort(adapted)
        else:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.VIEW_OP_UNSUPPORTED,
                msg=f"Unsupported post op: {op}",
            )

        return cast(list[dict[str, Any]], result)
