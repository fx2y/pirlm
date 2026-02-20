---
paths:
  - "pirml/*.py"
  - "pirml/**/*.py"
  - "scripts/proto_lint.py"
  - "scripts/trace_lint.py"
---
# Runtime + Protocol Rules (Normative)

- `R0` stdout is protocol channel only (NDJSON); stderr is diagnostics only.
- `R1` Frame algebra is closed: `op in {call,result,final}`; unknown op is hard-fail.
- `R2` Trace cardinality: one `final` exactly, terminal position exactly.
- `R3` ID contract: `^c[0-9]{5}$`, monotonic by appearance, `result.id` must map prior `call.id`.
- `R4` Envelope contract (all frames): `seq` strictly increments from 1, `dir in {in,out}`, `ts:int`, `ms=ts-start_ts>=0`.
- `R5` Hash contract:
  - `call`: include `sha256_args`; trace args are redacted by key policy.
  - `result|final`: include `sha256_output` over emitted payload bytes.
- `R6` Redaction contract (call args in trace only): redact keys matching `token|password|secret|api_key|apikey|authorization|auth*` using `{redacted_sha256}`.
- `R7` Size contract: enforce line-byte cap at writer boundary (`8192` default).
- `R8` Truncation contract: only `result` may truncate; if truncated set root fields `truncated:true` and `truncated_bytes:int>=0`; recompute hashes post-truncate.
- `R9` Replay contract:
  - build replay cassette from validated source trace;
  - execute with `PIRML_BLOCK_TOOLS=1`;
  - fail on extra/missing/out-of-order call ids;
  - compare replay `final` payload hash vs source hash and stamp parity in replay final-frame `meta`.
- `R10` Fatal-path contract: supervisor must still emit `trace.ndjson` + compact `final.json` (`ok:false` fallback if needed).
- `R11` Final boundary contract: `final.json` keeps deterministic summary (`ok`,`results`; optional `output/meta`), never raw trace/tool transcripts.
- `R12` Extension gate (future): new op/tool/replay semantics require explicit invariants, schema/test/lint updates, and deterministic replay proof before merge.
