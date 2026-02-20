# Replay Mechanism (V2-Substrate)

## Input: {trace.ndjson}
## Output: {final.json} byte-parity with LIVE.

## Process:
1. **Load Trace:** `trace_lint` validates envelope + protocol strictness.
2. **Build Cassette:** `dict[call_id, result_payload]`. Fail on duplicate result IDs.
3. **Set Invariants:** `PIRML_BLOCK_TOOLS=1`, `PIRML_BLOCK_CLOCK=1`, `PIRML_BLOCK_SEED=1`.
4. **Execute (No-Tool):**
    - `call(tool, args)` => lookup `id` in Cassette.
    - Return `result_payload` directly.
    - `ToolRegistry.execute` bypassed.
5. **Finalize:**
    - `send_final(result)` => project `final.json`.
    - Compare `live_final_sha` vs `replay_final_sha`.
    - Attach `replay_match: bool` to trace-final meta.
6. **Exit Code:** `rc0` (match), `rc1` (final.ok false), `rc2` (mismatch/protocol fatal).

## Error Taxonomy (ErrorType):
- **NOT_FOUND**: Tool not in registry.
- **TIMEOUT**: Execution exceeded budget.
- **BAD_ARGS**: Argument validation failed.
- **INTERNAL**: Unexpected tool exception.
- **PROTOCOL**: Malformed frame/id.
- **ABORTED**: External signal/kill.
- **SYSTEM**: Environment/FS error.

## Failure Invariants:
- **Unexpected Call:** `call.id` not in cassette.
- **Missing Call:** Program finished without exhausting cassette.
- **ID Mismatch:** Program sent `c00001` when cassette expected `c00002`.
- **Early End:** Program sent `final` before all cassette calls were consumed (if applicable).
