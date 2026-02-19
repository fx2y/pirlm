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

- `mise` task graph is the build contract; CI must call only `mise run ci`.
- Preserve fail-fast ladder ordering unless a faster equivalent is proven and documented.
- `fast` stays tiny (<3s class); push expensive checks to `ci`.
- Keep module execution style (`python -m scripts.*`) to avoid path/import drift.
- Tool backend workarounds are policy: pyright via `npm:pyright`; hyperfine/watchexec via cargo.
- New tool/dependency must justify determinism, speed, and maintenance cost.
- Any task graph change needs matching proof (`mise run fast` and `mise run ci`) in change notes.
- Benchmark output lives in `out/bench.json`; perf regressions require explanation or rollback.
