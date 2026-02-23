# PIRML Walkthroughs: 002-004 (Expert/Terse)

## W002: Proof-First Runtime (L0)
**Stance**: `trace.ndjson` = truth; `final.json` = projection. Replay or it didn't happen.

### Drill: The Parity Loop
1. **Reset**: `rm -rf out/w02 && mkdir -p out/w02`
2. **Live**: `python -m pirml --prog tests/prog_ok.py --out-dir out/w02/live > out/w02/live.stdout`
3. **Replay**: `PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay out/w02/live/trace.ndjson --out-dir out/w02/replay > out/w02/replay.stdout`
4. **Audit**: `sha256sum out/w02/live/final.json out/w02/replay/final.json` (MUST MATCH)
5. **Verify**: `tail -n1 out/w02/replay/trace.ndjson | grep '"replay_match":true'`

### Triage
- **RC1**: Biz/Tool fail. Check `final.ok=false`.
- **RC2**: Protocol/Integrity/Timeout. Check `stderr` for `config|internal`.
- **Mismatch**: Check `final.meta.replay_match`. Usually nondeterministic IDs or side-effects.

### Snippet: Redaction Proof
```bash
# Verify no secrets in trace
python -m pirml --prog tests/prog_leak.py --out-dir out/leak
rg "secret|token" out/leak/trace.ndjson && exit 1 || echo "SAFE"
```

### Snippet: Truncation Audit
```bash
# Verify only 'result' frames truncate
python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir out/trunc
rg '"truncated":true' out/trunc/trace.ndjson | grep -v '"op":"result"' && exit 1 || echo "OK"
```

---

## W003: ToolSearch (L1)
**Stance**: Pareto-optimal hydration. Runtime is frozen; L1 is metadata selection.

### Drill: Context Compression
1. **Lint**: `python -m scripts.tool_manifest_lint --tools-dir tools`
2. **Bench**: `python -m scripts.tool_search_bench` -> Check `out/toolsearch_tokens.json` for `reduction_pct > 95%`.
3. **Selection**: `python -c "from pirml.toolsearch.loader import load_catalog; from pirml.toolsearch.search import search_tools; cat=load_catalog('tools'); print(search_tools(cat, 'list files', k=3))"`

### Triage
- **Ranking Drift**: Check tie-break keys (name/desc/hot). Run `tests/test_toolsearch_golden.py`.
- **Manifest Red**: `ManifestError` in `stderr`. Usually missing `hot_count` or invalid examples.
- **Hydration Fail**: `missing_ref`. selected refs must exist in the loaded catalog.

### Snippet: Determinism x3
```bash
# Identity check on ranking
for i in {1..3}; do python -m scripts.tool_search_bench | sha256sum; done
```

### Snippet: Manual Hydration/Render
```python
# Pure L1 transform (Client-Side)
from pirml.toolsearch.loader import load_catalog, load_selected
from pirml.toolsearch.search import search_tools
from pirml.toolsearch.render import render_selected_tools

cat = load_catalog("tools", strict=True)
refs = search_tools(cat, "query", k=5)
sel = load_selected(refs, "tools")
prompt_block = render_selected_tools(sel)
```

---

## W004: Compiler (L1)
**Stance**: Fail-closed branch: `{prog.py, contract.json}` XOR `{compile_error.json}`. No prose.

### Drill: Compile -> Smoke -> Replay
1. **Compile**: `PIRML_MODEL_RAW="$(cat model.txt)" python -m scripts.compile --task t1 --tools-dir tools --out-dir out/w04 --smoke`
2. **Validate Branch**: `test -f out/w04/prog.py && test -f out/w04/contract.json`
3. **Smoke Check**: `cat out/w04/smoke_trace.ndjson` -> verify `op=final` exists.
4. **Replay Parity**: `python -m pirml --prog out/w04/prog.py --out-dir out/w04/live` -> Replay as W002.

### Triage
- **Extract Fail**: Check `raw.txt`. Sentinels `<<<PROG>>>` and `<<<CONTRACT>>>` mandatory.
- **Verify Fail**: AST check. No `os|sys`, no unawaited `TOOL_*`, mandatory `asyncio.gather` for parallel.
- **Smoke Fail**: RC1 + `compile_error.json`. Check `smoke_trace.ndjson` for budget/logic errors.

### Snippet: Raw Model Input (Sentinels)
```text
<<<PROG>>>
import asyncio
from pirml.runtime.rpc import send_final
async def main():
    await TOOL_pirml_echo({"text": "hi"})
    send_final(True, {"ok": True, "results": []})
if __name__ == "__main__":
    asyncio.run(main())
<<<CONTRACT>>>
{"tool_deps": ["pirml.echo"], "budgets": {"max_calls": 5}}
```

### Snippet: Strict Schema Gate
```bash
# Reject argless scans
python -m scripts.schema_lint --final out/live/final.json --contract out/w04/contract.json
```

---

## Cross-Cycle Integrity (Master Control)
**Stance**: Every behavior delta must ship an invariant delta + proof.

### The Immutable Gate Ladder
1. `fmt > lint > types`: Syntax & Contract Surface.
2. `unit`: Component Logic.
3. `proto > trace`: Protocol Adherence (L0).
4. `schemas`: Artifact/Contract Validity.
5. `replay`: Forensic Determinism.

### Global Triage Playbook
- **Gate Fail**: `mise run fast` (reject <3s). If green, run `mise run ci`.
- **System Drift**: `python -m scripts.artifact_rebuild --check`.
- **Replay Mismatch**: `python -m scripts.replay_check`.

## Master Command
`mise run ci && python -m scripts.replay_check`
*Green = Releasable. Red = Artifact Only.*
