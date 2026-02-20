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

- `G0` `mise` is the only task contract; authoritative CI entrypoint is `mise run ci`.
- `G1` Gate order is fixed fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `G2` `fast` is <3s reject-signal, not mini-CI; keep only high-reject/low-cost deterministic checks.
- `G3` Scripts run as modules (`python -m scripts.*`) only.
- `G4` Backend/tool pins are policy (determinism + supply-chain), not convenience.
- `G5` Dependency admission bar: measurable correctness/determinism/perf gain must exceed maintenance+risk.
- `G6` Task-graph edits must prove value in same change via `mise run fast`, `mise run ci`, plus replay check when boundary semantics changed.
- `G7` Artifact-first law: checks consume explicit artifacts (`out/<run>/...`), never hidden process state.
- `G8` Schema-stage law: `scripts.schema_lint` validates explicit artifact args only; missing requested artifacts are hard-fail; no recursive `out/**` discovery.
- `G9` Compile CLI contract: deterministic stage toggles only; branch tuple + RC mapping (`0/1/2`) is fixed and tested.
- `G10` Bench law: raw telemetry and canonical verdict bytes stay separate; CI gates canonical artifacts only.
- `G11` Exit-code law across scripts/runners: `0` pass/success, `1` business/validation failure, `2` integrity/internal failure.
- `G12` Extension admission (new gate/tool/op) needs explicit placement rationale: earliest stage with max reject power and minimum deterministic cost.
- `G13` Handoff sync law: behavior-affecting change must update `spec-0/*tasks.jsonl` + `spec-0/00-learnings.jsonl` status/decision records in same merge.
