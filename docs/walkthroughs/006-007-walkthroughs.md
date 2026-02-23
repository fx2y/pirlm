# PIRML Mastery: 006 (ArtifactFS/RLM) + 007 (UX/Extension) Walkthroughs

Expert-tier operator guide. Terse language. Hard proofs only.

## 0. Hard Invariants (The "Stop" List)
- **L0 Freeze**: Tools = `{echo,readfile,bash}` only. No convenience bloat.
- **Protocol**: `{call,result,final,custom}`. One `final`, strictly last.
- **Authority**: `mise run fast` (reject) -> `mise run ci` (ship).
- **Parity**: Replay parity > live intuition. Drift = stop ship.
- **Storage**: `out/*` + `art/*` are truth. `.pirml/*` is projection-only facade.
- **Exit Codes**: `0` (ok), `1` (biz/tool fail), `2` (integrity/config fail).

## 1. Track: The Authority Ladder (Core Flow)
Execute this sequence for every behavioral delta.

1. **Preflight**: `mise run fast` (Reject noise <3s).
2. **Execution**: `python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/run_1 --project-root .`
3. **Projection**: `ls -l .pirml` (Verify symlinks to `out/run_1`).
4. **Replay**: `python -m scripts.tools.replay tests/prog_ok.py out/run_1/trace.ndjson --out-dir out/replay_1`
5. **Parity**: `python -m scripts.replay_check` (Full suite parity).
6. **Ship**: `mise run ci` (Final gate).

## 2. Track: Artifact & Lineage Forensics (Spec-06)
Verify CAS integrity, RLM history, and trace pointer resolvability.

1. **Ingest**: `python -m unittest -q tests.test_artifact_c1` (Generates `out/test_artifact_c1`).
2. **Extract AID**: 
   ```python
   # Get first raw artifact ID from trace
   import json; from pathlib import Path
   trace = Path('out/test_artifact_c1/trace.ndjson').read_text().splitlines()
   aid = next(json.loads(l)['aid'] for l in trace if json.loads(l).get('kind')=='raw')
   print(aid)
   ```
3. **Rebuild**: `python -m scripts.artifact_rebuild --root out/test_artifact_c1 --check` (SUCCESS: Parity confirmed).
4. **Lint**: `python -m scripts.artifact_rebuild --root out/test_artifact_c1 --export /tmp/meta.ndjson`
   - `python -m scripts.schema_lint --artifact /tmp/meta.ndjson` (Schema strictness).
5. **View DSL**: `VID=$(python -m scripts.tools.slice "$AID" '{"op":"lines","a":0,"b":1}' --art-root out/test_artifact_c1)`
   - `python -m scripts.tools.open "$VID" --art-root out/test_artifact_c1 --mode text`

## 3. Track: UX & Extension Integration (Spec-07)
Verify shim delegation, toolpack contracts, and feature gates.

1. **Shim**: `python -m pirml.ux.runtime_bridge tests/prog_ok.py` (Verify summary row).
2. **Headless Event**:
   ```json
   // STDIN to python -m pirml.ux.headless (PIRML_ENABLE_JSON_HEADLESS=1)
   {
     "type": "tool_execution_start",
     "tool": "pirml_run",
     "args": { "prog": "tests/prog_ok.py", "out-dir": "out/headless_demo" }
   }
   ```
3. **Toolpack**: `python -m unittest -q tests.test_spec07_c3_toolpack` (Open/Slice/Replay contracts).
4. **Extension (TSX)**: `npx tsx tests/test_spec07_c2_extension_contract.ts` (Event flow validation).

## 4. Live Pipeline (Lane B - Real Network)
Example `WebPipeline` + `ArtifactStore` integration:
```python
import asyncio, json
from pathlib import Path
from pirml.artifacts import ArtifactStore, default_layout
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import provider_factory

async def main():
    out = Path("out/live_web")
    pipe = WebPipeline(
        provider=provider_factory("searx_json", {}),
        artifact_store=ArtifactStore(default_layout(out / "art")),
        # ... fetcher, clock, tracer
    )
    final = await pipe.run("OpenAI rate limits", WebPlan(serp_k=2))
    print(f"Artifacts: {len(pipe.artifact_store.find_by_kind('raw'))}")

asyncio.run(main())
```

## 5. Track: Triage & Fail-Lanes
Reproduce failures without narrative filler.

- **Integrity Fail (rc=2)**: Delete a chunk in `art/obj/*` -> `python -m scripts.artifact_rebuild --check`.
- **Validation Fail (rc=1)**: `python -m scripts.tools.open missing --art-root out/art`.
- **Schema Fail**: `python -m scripts.schema_lint --artifact tests/fixtures/web/corpus.jsonl` (Wrong type).
- **Timeout**: `python -m unittest -q tests.test_spec07_c1_runtime_shim.TestSpec07C1RuntimeShim.test_run_once_timeout`.

## 5. Summary Scenarios (Dense Drills)
- **S-CAS**: `tests/test_artifact_paths.py` (CAS path canonicality).
- **S-RLM**: `tests/test_rlm_kernel.py` (No state bleed, budget enforcement).
- **S-PROJ**: `tests/test_spec07_c1_runtime_shim.TestSpec07C1RuntimeShim.test_projection_refuses_non_projection_directory`.
- **S-REPLAY**: `tests/test_replay_cli_docs.py` (Snippet/Doc drift).
- **S-FREEZE**: `tests/test_tool_surface_freeze.py` (L0 integrity).

## 6. Exit Policy
`done` = `mise run ci` green + `replay_check` green + `artifact_rebuild --check` green.
Prose/logs are non-evidence. Use `spec-0/00-learnings.jsonl` for rationale persistence.
