#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_materialize import ViewMaterializer


def bench_view_lookup() -> None:
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        layout = default_layout(tmp_dir)
        store = ArtifactStore(layout)
        vm = ViewMaterializer(store)

        # 1. Put a large-ish artifact
        data = b"line\n" * 1000
        aid = store.put_raw(data, kind="raw", mime="text/plain")

        # 2. Materialize many views
        vids: list[str] = []
        for i in range(100):
            vid = vm.materialize(aid, {"op": "lines", "a": i, "b": i + 10})
            vids.append(vid)

        # 3. Benchmark lookup
        start = time.perf_counter()
        count = 1000
        for _ in range(count):
            for vid in vids[:10]:
                store.get_view_text(vid)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        per_lookup_ms = elapsed_ms / (count * 10)
        print(
            f"View lookup: {per_lookup_ms:.3f}ms per call (total {elapsed_ms:.1f}ms per {count * 10} calls)"
        )

    finally:
        shutil.rmtree(tmp_dir)


def bench_trace_append() -> None:
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        layout = default_layout(tmp_dir)
        store = ArtifactStore(layout)

        start = time.perf_counter()
        count = 1000
        for i in range(count):
            store.put_raw(f"data{i}".encode(), kind="raw", mime="text/plain")
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        per_append_ms = elapsed_ms / count
        print(
            f"Artifact put (incl trace): {per_append_ms:.3f}ms per call (total {elapsed_ms:.1f}ms per {count} calls)"
        )

    finally:
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    bench_view_lookup()
    bench_trace_append()
