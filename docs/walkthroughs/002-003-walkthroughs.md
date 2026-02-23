# Mastery Walkthrough: L0 Protocol (002) + L1 ToolSearch (003)

## 0. The Hard Line
- **L0 (Runtime):** Frozen. Ops: `{call, result, final}`. IDs: `c%05d` mono. `stdout` = NDJSON protocol ONLY.
- **L1 (Search):** Metadata-only. Context compression > 99%. Never expands L0 tool registry.
- **Parity Law:** `PIRML_BLOCK_TOOLS=1` replay must match `live` hash. Drift = `rc=2` integrity fail.
- **Exit Triad:** `0`: OK | `1`: Biz/Tool Fail | `2`: Infra/Protocol/Timeout.

## 1. L0 Protocol Rigor (002 Drill)
**Goal:** Prove deterministic forensic truth.

1. **Preflight:** `mise run fast` (reject dirty gates <3s).
2. **Execute Live:** `python -m pirml --prog tests/prog_ok.py --out-dir out/002/live > out/002/live.stdout`.
   - *Check:* `stderr` for logs, `stdout` for NDJSON frames.
3. **Forensic Replay:** `PIRML_BLOCK_TOOLS=1 python -m pirml --prog tests/prog_ok.py --replay out/002/live/trace.ndjson --out-dir out/002/rep > out/002/rep.stdout`.
4. **Parity Proof:** `sha256sum out/002/{live,rep}/final.json`.
   - *Verify:* `tail -n 1 out/002/rep/trace.ndjson` contains `meta.replay_match=true`.
5. **RC Drill:**
   - `prog_fail.py` -> `rc=1`.
   - `--timeout 0.001` -> `rc=2`.
6. **Integrity Lint:**
   - `python -m scripts.proto_lint --trace out/002/live/trace.ndjson`.
   - `python -m scripts.trace_lint --trace out/002/live/trace.ndjson`.
   - `python -m scripts.schema_lint --final out/002/live/final.json`.
7. **Secret Redaction Proof:**
   ```bash
   # Trace must NOT contain 'secret123' or 'Bearer abc'
   rg -n 'secret123|Bearer abc' out/002/live/trace.ndjson || echo "CLEAN"
   # Trace MUST contain redaction markers
   rg -n 'redacted_sha256' out/002/live/trace.ndjson
   ```
8. **Evidence Verification:**
   ```bash
   # Verify metrics columns: calls,retries,failures,wall_ms,final_ok,trace_sha,final_sha
   tail -n 1 out/002/live/metrics.csv
   ```

## 2. L1 ToolSearch Mastery (003 Drill)
**Goal:** Context-compressed deterministic selection.

1. **Manifest Guard:** `python -m scripts.tool_manifest_lint --tools-dir tools`. Fail on schema/desc drift.
2. **Value Proof:** `python -m scripts.tool_search_bench`.
   - *Inspect:* `out/toolsearch_tokens.json`. Expect `reduction_pct` > 99%.
3. **Selection Path (Expert Script):**
   ```python
   import json
   from pirml.toolsearch.loader import load_catalog, load_selected
   from pirml.toolsearch.search import search_tools
   from pirml.toolsearch.render import render_selected_tools

   cat = load_catalog('tests/fixtures/toolsearch/catalog', strict=True)
   refs = search_tools(cat, 'list files', k=3)
   sel = load_selected(refs[:2], 'tests/fixtures/toolsearch/catalog')
   print(render_selected_tools(sel)) # Deterministic XML prompt
   ```
4. **Deterministic Ranking:** Execute search x3 on same query; assert identical order.
5. **Policy Enforce:** Trigger `invalid_policy_combo` by mixing `server_search` + `examples`.
6. **Golden Stability:** `python -m unittest tests.test_toolsearch_golden`. Zero tolerance for ranking drift.
7. **Leak-Strip Proof:**
   ```bash
   python -m pirml --prog tests/prog_leak.py --out-dir out/002/leak
   # Verify 'results' in final.json contain only {id, ok, tool}; no extra junk.
   cat out/002/leak/final.json | jq '.results[0]'
   ```
8. **Truncation Proof:**
   ```bash
   python -m pirml --prog tests/prog_large.py --max-line-bytes 1024 --out-dir out/002/trunc
   # Must find truncated=true markers only on 'result' frames
   rg '"truncated":true' out/002/trunc/trace.ndjson
   ```

## 3. Triage Playbook (Expert Path)
- **Replay Mismatch:** Compare `final.json` hashes -> diff `trace.ndjson` IDs -> check tool-registry side-effects.
- **Proto Fail:** `rc=2`. Check `trace_lint` for `final` order or ID gaps.
- **Context Bloat:** Run `tool_search_bench`. Verify L1 selection isn't leaking full catalog.
- **Secret Leak:** `rg 'redacted_sha256' trace.ndjson`. If missing, check `redaction_map` in `protocol.py`.
- **Flake:** `mise run ci` is the only release authority. `fast` is for dev loop only.
