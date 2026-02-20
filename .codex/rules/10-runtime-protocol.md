---
paths:
  - "pirml/*.py"
  - "pirml/**/*.py"
  - "pirml/toolsearch/*.py"
  - "pirml/toolsearch/**/*.py"
  - "scripts/proto_lint.py"
  - "scripts/trace_lint.py"
---
# Runtime + Protocol Rules (Normative)

- `R0` Channels are disjoint: stdout=NDJSON protocol only, stderr=diagnostics only.
- `R1` Protocol algebra is closed: `op in {call,result,final}`; unknown op/order/cardinality violation => integrity fail.
- `R2` `final` is exactly one and terminal; `result.id` must map an earlier `call.id`.
- `R3` IDs are `^c[0-9]{5}$`, monotonic by appearance; envelope is `seq:+1 from 1`, `dir in {in,out}`, `ts:int`, `ms>=0`.
- `R4` Hashes are boundary truth: `call.sha256_args`; `result|final.sha256_output` over emitted bytes only.
- `R5` Redaction applies to traced call args only; sensitive keys (`token|password|secret|api[_]?key|authorization|auth*`) become `{redacted_sha256}`.
- `R6` Size cap is writer-boundary (`8192` default). Only `result` may truncate; must set `truncated:true` + `truncated_bytes>=0`; hash recomputed after truncation.
- `R7` Replay contract: source trace must validate; replay runs with `PIRML_BLOCK_TOOLS=1`; extra/missing/reordered call IDs hard-fail; replay/source `final` hash parity required and stamped in replay `final.meta`.
- `R8` Fatal paths still emit `trace.ndjson` + compact `final.json` (`ok:false` fallback allowed); artifact loss is merge-blocking.
- `R9` `final.json` is boundary state only: `{ok,results,output?,meta?}`; never raw trace/tool transcript.
- `R10` Selection plane is metadata-only: search/hydrate/render cannot mutate runtime tool adapter surface.
- `R11` Selection determinism: same `(query,catalog,mode,k)` => same ordered refs; tie-break must be total order and tested.
- `R12` Selection bounds: `k<=5`; all-deferred/empty-usable catalog is typed hard-fail.
- `R13` Manifest contract at boundary: strict keys, strict schema/examples, deterministic loader behavior (duplicates/invalids fail in strict mode).
- `R14` Any op/tool/replay/selection semantic change requires invariant delta + schema/lint/test/gate/docs updates in same merge.
