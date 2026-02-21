#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# C7.T07: Release proof bundle with absolute command set


async def run_signoff() -> int:
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        art_dir = tmp_dir / "art"
        print(f"--- Hardening Signoff Start (Root: {tmp_dir}) ---")

        # 1. Hostile flow E2E (10MB + recursive map-reduce)
        print("Step 1: Running Hostile-Flow E2E test...")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests/test_spec06_c4_stress.py",
                "tests/test_spec06_c7_hard_end2end.py",
            ]
        )

        # 2. Run RLM kernel to generate real artifacts
        print("\nStep 2: Generating artifacts via RLM kernel run...")
        from pirml.artifacts.paths import default_layout
        from pirml.artifacts.store import ArtifactStore
        from pirml.artifacts.view_materialize import ViewMaterializer
        from pirml.compiler.model import ModelAdapter
        from pirml.rlm import run_rlm

        class SimpleModel(ModelAdapter):
            def compile_once(self, prompt: str) -> str:
                return 'Final = "Done"'

        layout = default_layout(art_dir)
        store = ArtifactStore(layout)
        vm = ViewMaterializer(store)

        # Put some artifacts
        aid = store.put_raw(b"hello world", kind="test", mime="text/plain")
        store.put_json({"a": 1}, kind="config")

        # View
        vm.materialize(aid, {"op": "bytes", "offset": 0, "limit": 5})

        # RLM run (this will generate trace.ndjson implicitly? No, RlmKernel doesn't have a global trace yet, wait.)
        # RlmKernel uses store.trace.
        await run_rlm("Signoff goal", store, SimpleModel())

        # We also need ndx.sqlite to be flushed
        # store._index._conn is in WAL mode, should be fine.

        # 3. Export and Schema Lint
        print("\nStep 3: Exporting index and Running Schema Linter...")
        meta_ndjson = art_dir / "meta.ndjson"
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "scripts.artifact_rebuild",
                "--root",
                str(art_dir),
                "--export",
                str(meta_ndjson),
            ]
        )

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "scripts.schema_lint",
                "--artifact",
                str(meta_ndjson),
                "--artifact-trace",
                str(art_dir / "trace.ndjson"),
            ]
        )

        # 4. Rebuild Parity
        print("\nStep 4: Running Rebuild Parity check...")
        subprocess.check_call(
            [sys.executable, "-m", "scripts.artifact_rebuild", "--root", str(art_dir), "--check"]
        )

        # 5. Benchmarks
        print("\nStep 5: Running Artifact Benchmarks...")
        subprocess.check_call([sys.executable, "-m", "scripts.artifact_bench"])

        print("\n--- HARDENING SIGNOFF SUCCESS ---")
        return 0
    except Exception as exc:
        print(f"\n--- SIGNOFF FAILED: {exc} ---")
        return 1
    finally:
        shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    sys.exit(asyncio.run(run_signoff()))
