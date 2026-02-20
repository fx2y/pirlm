---
paths:
  - ".mise.toml"
  - "pyproject.toml"
  - "pyrightconfig.json"
  - "requirements-dev.txt"
  - "scripts/*.py"
  - "scripts/**/*.py"
---
# Tooling + Task Rules

- `G0` `mise` is the only task contract; authoritative CI entrypoint is `mise run ci`.
- `G1` Gate order is fixed fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `G2` `fast` is <3s-class signal, not mini-CI; keep high-reject/low-cost checks only.
- `G3` Scripts run as modules (`python -m scripts.*`) only.
- `G4` Backend/tool pins are policy (determinism/supply-chain control), not convenience.
- `G5` New dependency bar: measurable correctness/determinism/perf win > ongoing maintenance+risk.
- `G6` Task-graph edits must prove value in same change via `mise run fast`, `mise run ci`, and replay check when boundary semantics changed.
- `G7` Artifact law: emitted artifacts are source of truth (`out/<run>/...`); linters/checkers consume artifacts, never hidden process state.
- `G8` Bench law: keep raw telemetry and canonical verdict bytes separate; CI gates on canonical artifact.
- `G9` Exit codes are standardized in scripts/runners: `0` pass, `1` business failure, `2` integrity failure.
- `G10` Extension admission (new gate/tool) requires explicit placement rationale: earliest stage with max reject power and minimal deterministic cost.
