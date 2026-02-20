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

- `G0` `mise` is the only task contract. CI entrypoint is `mise run ci` only.
- `G1` Gate order is fixed and fail-fast: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `G2` `fast` is inner-loop (<3s class); keep it tiny and representative. Heavy checks belong in `ci`.
- `G3` Scripts execute as modules (`python -m scripts.*`), never path-hacked direct imports.
- `G4` Tool backend pins are policy, not convenience:
  - pyright via `npm:pyright`;
  - perf/watch tools via cargo backends.
- `G5` Dependency admission bar: must improve correctness/determinism/speed enough to offset maintenance + supply-chain risk.
- `G6` Task-graph edits require proof in same change: `mise run fast`, `mise run ci`, and replay parity (`python -m scripts.replay_check` when relevant).
- `G7` Artifact contract:
  - run outputs live under `out/<run>/`;
  - perf smoke writes `out/bench.json`;
  - protocol/trace/schema scripts must consume emitted artifacts, not hidden state.
- `G8` Performance policy: regressions need quantified delta + rationale + mitigation plan, else rollback.
- `G9` Future extension rule: adding a new gate/tool must define placement by cost-first reject power and deterministic value, then codify in docs/tests/tasks together.
