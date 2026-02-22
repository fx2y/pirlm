---
paths:
  - ".mise.toml"
  - "pyproject.toml"
  - "pyrightconfig.json"
  - "requirements-dev.txt"
  - "scripts/*.py"
  - "scripts/**/*.py"
  - "spec-0/**/*.jsonl"
---
# Tooling + Task Rules

- `G0` `mise` is the execution contract; release authority is `mise run ci`.
- `G1` Gate order immutable fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `G2` `fast` must stay `<3s` and high-yield; reject signal only, never mini-CI.
- `G3` Scripts run via modules only: `python -m scripts.*`.
- `G4` Tool/runtime/version pins are policy (determinism+supply chain), not convenience.
- `G5` Dependency admission bar: measurable correctness/determinism/perf lift must exceed maintenance+risk cost.
- `G6` Task/gate changes must prove value in the same merge via `mise run fast` + `mise run ci`; add replay proof when boundary semantics change.
- `G7` Artifact-first gating: consume explicit artifacts (`out/<run>/...`), never hidden process state.
- `G8` Schema law: `scripts.schema_lint` validates explicit args only; missing requested artifacts hard-fail; recursive `out/**` scan forbidden.
- `G9` Pointer parity law: any emitted pointer (`trace_ptr`, view/artifact refs, etc.) must resolve and pass frame/schema parity checks.
- `G10` Eval harness law: every declared matrix row executes or emits typed unsupported row; no silent skip/fallback.
- `G11` Canonical-byte law: CI decisions use canonical compact bytes only; human reports are non-authoritative.
- `G12` Exit-code law across scripts/runners: `0` success/pass, `1` business/validation failure, `2` integrity/config/internal failure.
- `G13` Extension admission (`gate/tool/op/schema`) goes at earliest stage with max reject power and minimum deterministic cost.
- `G14` Status truth law: current-cycle `spec-0/*-tasks.jsonl` is authoritative state ledger; other docs are supportive, not status authority.
- `G15` Handoff sync law: behavior deltas co-update `spec-0/00-learnings.jsonl`, `spec-0/*-tasks.jsonl`, and `spec-0/*-tutorial.jsonl` in same merge.
- `G16` Done law: status flips to `done` only with reproducible proof commands + artifacts.
- `G17` Release-ready minimum proof set: `mise run fast`, `mise run ci`, replay check, required schema checks, and relevant domain parity/smoke scripts.
