---
paths:
  - "pirml/**/*.py"
  - "scripts/compile.py"
  - "scripts/proto_lint.py"
  - "scripts/trace_lint.py"
  - "scripts/schema_lint.py"
  - "scripts/web_eval.py"
  - "scripts/web_fixture_smoke.py"
  - "scripts/pirml_run.py"
  - "scripts/tools/*.py"
  - ".pi/extensions/pirml/*.ts"
---
# Runtime + Protocol Rules (Normative)

## R0-R9 Protocol Boundary
- `R0` `L0` freeze strict: runtime/replay/tool/channel/boundary immutable; `L1` wrappers only.
- `R1` stdout protocol-only; diagnostics/errors to stderr/artifacts.
- `R2` `op in {call,result,final,custom}` only.
- `R3` exactly one `final`, strictly last; each `result.id` maps to prior `call.id`.
- `R4` `id=^c[0-9]{5}$` uniq+mono/run; `seq=1,+1`; key order deterministic.
- `R5` hash persisted post-transform bytes only.
- `R6` only `result` truncates; boundary owns cap; truncation metadata mandatory.
- `R7` sensitive keys redact deterministically to `{redacted_sha256}`.
- `R8` every run (incl fatal) emits `trace.ndjson` + `final.json`; all pointers resolve.
- `R9` `final.json` root fixed `{ok,results,output?,meta?}`; bulky payload in artifacts/custom.

## R10-R19 Replay + Eval Integrity
- `R10` replay validates `op|order|id|hash|envelope`; forces `PIRML_BLOCK_TOOLS=1`; parity drift hard-fails.
- `R11` replay guard runs real deterministic snapshots; mismatch/error => typed replay-mismatch lane.
- `R12` runtime tool registry exact `{echo,readfile,bash}`; helper APIs are non-authoritative seams.
- `R13` compile XOR/run: `{prog.py+contract.json}` xor `{compile_error.json}`.
- `R14` every declared eval row executes or typed-returns unsupported; no silent skip/fallback.
- `R15` winner selection uses deterministic tuple ranking only; `hash()` forbidden in eval paths.
- `R16` unknown provider/cache/variant/plan/path/flag/arg => typed fail-closed envelope.
- `R17` dataset path explicit; scored prompt key never falls back to answer keys; duplicate `task_id` => integrity fail.
- `R18` shard NDJSON append-only; existing rows must keep seq integrity + one terminal/task.
- `R19` report ingestion reuses runner-equivalent parse/merge policy; corrupt/dup terminal evidence => integrity/code2.

## R20-R31 Determinism + Operator Projections
- `R20` metrics/taxonomy fixed by schema: required keys, single-label `fail_tag`, explicit `NO_CITE`, exact persisted `acc`.
- `R21` no wall-clock semantics in scored fields; contract-relevant timing fields deterministic.
- `R22` hard budgets (`iters|subcalls|timeout`) enforce deterministically; warn/fail lanes typed.
- `R23` lineage spillover stays in `custom`; same hash/redaction laws; custom rows never enter context packing.
- `R24` rich pointer payload in `custom.data/details`; human hint optional one-line `<=120` chars.
- `R25` wrappers delegate only via `scripts.pirml_run -> pirml.ux.runtime_bridge -> python -m pirml`.
- `R26` `.pirml/*` is projection-only facade; never rewrite/delete non-projection user dirs.
- `R27` optional capabilities default-off; disabled/unimplemented lanes typed-return unsupported.
- `R28` independent work uses bounded deterministic fanout/merge; serial needs explicit reason.
- `R29` incident report root fixed `{class,rc,replay_match,artifact_parity,trace_ptr,notes,details_ptr}`; `notes<=120`.
- `R30` resolver views are read-only projections over declared artifacts; unresolved inputs typed-fail.
- `R31` machine JSON is default boundary; human summaries require explicit opt-in flag.

## R32-R34 Change Admission
- `R32` command aliases are non-authoritative; only validated owner-path rows are authority.
- `R33` command-matrix/proof/report consumers must use shared strict parsers; no permissive duplicate loaders.
- `R34` edits touching `op|tool|replay|compile|eval|schema|gates|cli-parse` require invariant delta + failing test + ledger/doc sync.
