---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
---
# Test + Determinism Rules

- `T0` Determinism is mandatory: no network, no wall-clock assertions, no unseeded randomness, no locale/TZ dependence.
- `T1` Tests are rerun-stable and order-independent; isolate artifacts via temp dirs.
- `T2` Contract-first testing: prefer CLI/artifact black-box assertions; use internals only when boundary cannot express invariant.
- `T3` Every invariant needs both proof modes: at least one pass-path and one typed fail-path test.
- `T4` Bugfix protocol is fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay parity proof (if boundary touched).
- `T5` Golden files are contractual bytes; updates require explicit behavior rationale in same change.
- `T6` Trace/final/replay edits must update replay-parity coverage; omission is merge-blocking.
- `T7` Merge-blocking severities: protocol algebra/order/id, replay ordering/parity, timeout integrity, artifact loss, redaction/truncation/schema drift.
- `T8` Flake triage: enforce env pins, rerun x3, run replay; if still non-reproducible, keep failing state open (no silent waive).
- `T9` Test names encode invariant (`must hold`), not implementation detail.
- `T10` Deterministic ordering claims require explicit permutation/tie-break tests (not incidental coverage).
