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

- `G0` `mise` is task contract; authoritative release gate is `mise run ci`.
- `G1` Gate order immutable fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `G2` `fast` is `<3s` reject-signal, not mini-CI; keep only highest-reject/lowest-cost deterministic checks.
- `G3` Scripts run as modules (`python -m scripts.*`) only.
- `G4` Tool/runtime pins are policy (determinism+supply-chain), not convenience.
- `G5` Dependency admission bar: measurable correctness/determinism/perf gain must exceed maintenance+risk.
- `G6` Task/gate edits prove value in same change via `mise run fast` + `mise run ci`; add replay proof if boundary semantics changed.
- `G7` Artifact-first: checks consume explicit artifacts (`out/<run>/...`), never hidden process state.
- `G8` Schema-stage strictness: `scripts.schema_lint` validates explicit args only (`--final/--contract/--compile-error/--web-*`); missing requested artifacts hard-fail; no recursive `out/**` scan.
- `G9` Pointer parity: if payload emits artifact pointer (`trace_ptr` etc.), gate must validate target exists + schema/frame parity.
- `G10` Eval harness law: declared matrix plans must all execute; unsupported variants become typed rows, not skips.
- `G11` Canonical artifact law: human-readable reports may vary, but CI gates canonical compact bytes only.
- `G12` Exit-code law across scripts/runners: `0` success/pass, `1` business/validation fail, `2` integrity/internal fail.
- `G13` Extension admission (new gate/tool/op/schema): place at earliest stage maximizing reject power at minimum deterministic cost.
- `G14` Handoff sync law: behavior change updates `spec-0/*tasks.jsonl`, `spec-0/*tutorial.jsonl` (if operator flow changes), and `spec-0/00-learnings.jsonl` in same merge.
- `G15` Done law: status flips to `done` only with reproducible executable proof artifacts; narrative-only closure invalid.
