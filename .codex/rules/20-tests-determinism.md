---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
---
# Test + Determinism Rules

- `T0` Determinism is non-negotiable: no network, no wall-clock assertions, no unseeded randomness, no locale/timezone assumptions.
- `T1` Tests must be rerun-stable and order-independent; use temp dirs and isolated artifacts.
- `T2` Prefer black-box contract tests via CLI traces/artifacts; avoid private-internal coupling unless invariant cannot be expressed externally.
- `T3` Each runtime invariant must have:
  - one passing-path test;
  - one failing-path test with explicit error class/message contract.
- `T4` Bugfix flow is fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay parity proof.
- `T5` Golden artifacts are contracts; update only with explicit behavioral rationale in the same change.
- `T6` Any change touching trace/final/replay semantics must add or update replay-parity coverage.
- `T7` Severity policy:
  - protocol algebra/id/final-order/replay-order/timeout/artifact-loss = merge-blocking;
  - redaction/truncation/schema drift = merge-blocking unless explicitly waived in writing.
- `T8` Flake playbook: freeze env pins, rerun x3, then replay; if non-reproducible, treat as unresolved defect.
- `T9` Naming rule: test names encode invariant (`what must hold`), not implementation detail (`how currently done`).
