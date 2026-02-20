---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
  - "tests/fixtures/**/*.jsonl"
  - "tests/golden/**/*"
---
# Test + Determinism Rules

- `T0` Determinism is mandatory: no network, no wall-clock assertions, no unseeded randomness, no locale/TZ dependence.
- `T1` Tests are rerun-stable/order-independent; artifacts isolate in temp dirs, never shared `out/**`.
- `T2` Contract-first proofs: prefer CLI/artifact black-box assertions; internals only when boundary cannot encode invariant.
- `T3` Each invariant needs dual evidence: at least one pass path and one typed fail path.
- `T4` Bugfix protocol is fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay/schema proof if boundary touched.
- `T5` Golden discipline is strict: goldens are contractual bytes; tests must fail on missing/drift; no auto-generate/self-heal in test execution.
- `T6` Compile branch proof is required: success path asserts `prog.py+contract.json` and absence of `compile_error.json`; fail path asserts inverse.
- `T7` Verifier/smoke edits must include deterministic x3 proof for trace/artifact bytes where order/clock/hash can drift.
- `T8` Trace/final/replay edits must update replay-parity coverage; omission is merge-blocking.
- `T9` Merge-blocking severities: protocol algebra/order/id, replay parity, schema strictness drift, timeout integrity, artifact loss, redaction/truncation drift.
- `T10` Flake triage: enforce env pins, rerun x3, run replay; unresolved flakes remain failing (no silent waive).
- `T11` Test names encode invariant semantics, not implementation detail.
- `T12` Any ordering claim requires explicit permutation/tie-break tests; incidental coverage is invalid.
