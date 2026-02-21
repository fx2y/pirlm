#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from pirml.artifacts.paths import default_layout
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_materialize import ViewMaterializer


def bench_view_lookup(count: int = 100000) -> float:
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
        # Batch lookup
        for _ in range(count // 10):
            for vid in vids[:10]:
                store.get_view_text(vid)
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        per_lookup_ms = elapsed_ms / count
        print(
            f"View lookup: {per_lookup_ms:.3f}ms per call (total {elapsed_ms:.1f}ms per {count} calls)"
        )
        return per_lookup_ms

    finally:
        shutil.rmtree(tmp_dir)


def bench_trace_append(count: int = 10000) -> float:
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        layout = default_layout(tmp_dir)
        store = ArtifactStore(layout)

        start = time.perf_counter()
        for i in range(count):
            store.put_raw(f"data{i}".encode(), kind="raw", mime="text/plain")
        end = time.perf_counter()

        elapsed_ms = (end - start) * 1000
        per_append_ms = elapsed_ms / count
        print(
            f"Artifact put (incl trace): {per_append_ms:.3f}ms per call (total {elapsed_ms:.1f}ms per {count} calls)"
        )
        return per_append_ms

    finally:
        shutil.rmtree(tmp_dir)


def main() -> None:
    # 06.G12: Match declared SLOs: 100k lookups, 10k appends
    lookup_ms = bench_view_lookup(100000)
    append_ms = bench_trace_append(10000)

    results = {
        "view_lookup_ms": lookup_ms,
        "trace_append_ms": append_ms,
        "timestamp": int(time.time()),
    }

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    with open(out_dir / "bench.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {out_dir / 'bench.json'}")


if __name__ == "__main__":
    main()
