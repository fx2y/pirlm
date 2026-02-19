---
paths:
  - "pirml/*.py"
  - "pirml/**/*.py"
  - "scripts/proto_lint.py"
  - "scripts/trace_lint.py"
---
# Runtime + Protocol Rules

- Keep protocol algebra minimal: `op in {call,result,final}` only.
- Enforce `final` cardinality/order in shared validator, not ad-hoc call sites.
- `result.id` must reference a prior `call.id`; unknown/duplicate ids hard-fail.
- Generate call ids deterministically (`c0001...` monotonic, width-stable).
- Canonicalize all serialized JSON (`ensure_ascii`, compact separators, sorted keys).
- Enforce line-byte cap at writer boundary; non-`result` overflow is fatal.
- Truncation is explicit schema: set `truncated=true` and exact `truncated_bytes`.
- Keep `final.json` compact; detailed payloads live in trace `result` frames only.
- Replay path must not execute tools; if replay needs tools, design is wrong.
- Extend tool surface only with spec bump: validator changes + tests + AGENTS/rule update in same PR.
- Error messages should be stable and specific; avoid nondeterministic wording/content.
