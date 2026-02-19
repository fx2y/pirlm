---
paths:
  - "pirml/*.py"
  - "pirml/**/*.py"
  - "scripts/proto_lint.py"
  - "scripts/trace_lint.py"
---
# Runtime + Protocol Rules (Sprint-1 Normative Contract)

- **Op Set:** `op in {call,result,final}` only. Reject `log` or any unknown op.
- **Cardinality:** Exactly one `final` frame per trace; must be the terminal frame.
- **IDs:** `c0001...` monotonic 0-padded width=5 (e.g. `c00001`).
- **Truncation:** Only `result` frames may truncate. Must include `truncated: true` and `truncated_bytes: int`.
- **Replay:** Zero tool execution on replay path (`PIRML_BLOCK_TOOLS=1`).
- Canonicalize all serialized JSON (`ensure_ascii`, compact separators, sorted keys).
- Enforce line-byte cap (8192 default) at writer boundary; non-`result` overflow is fatal.
- Keep `final.json` compact (summary only: `id`, `tool`, `ok`, `error`); no raw outputs.
