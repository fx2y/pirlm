---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
  - "tests/fixtures/**/*.jsonl"
  - "tests/golden/**/*"
---
# Test + Determinism Rules

- `T0` Determinism mandatory: no live network/oracle, no wall-clock assertions, no unseeded randomness, no locale/TZ dependence.
- `T1` Tests rerun-stable and order-independent; isolate artifacts in temp roots, never shared mutable `out/**`.
- `T2` Contract-first proof: prefer CLI/artifact black-box checks; use internals only if boundary cannot encode invariant.
- `T3` Dual-lane invariant proof required: one pass lane + one typed fail lane; empty-success fail lanes are invalid.
- `T4` "Done" means executable proof artifacts + invariant coverage; narrative-only or green-only claims are invalid.
- `T5` Bugfix protocol fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay/schema proof if boundary touched.
- `T6` Goldens are contractual bytes; missing/drift fails; no self-heal/auto-regenerate in test runs.
- `T7` Compile branch proof required: success lane asserts `prog.py+contract.json` and no `compile_error.json`; fail lane asserts inverse.
- `T8` Boundary byte edits (`trace/final/hash/order/clock/cache`) require deterministic x3 proof and hashseed variation where relevant.
- `T9` Replay edits must extend replay-parity coverage; omission is merge-blocking.
- `T10` Eval anti-fraud tests required: all declared plans execute or emit typed unsupported rows; silent skips/default winners are invalid.
- `T11` Fail-closed config tests required: unknown provider/cache/variant/plan/path must typed-fail (never implicit fallback).
- `T12` Ordering claims require explicit permutation+tiebreak tests; incidental order coverage is non-evidence.
- `T13` Governor/recursion claims require explicit cap/cohesion tests (`warn`, `hard-fail`, deterministic parallel merge).
- `T14` Pointer/custom-op claims require default-off + opt-in + no-context-contamination tests.
- `T15` Merge blockers: algebra/order/id drift, replay drift, schema strictness drift, timeout/cap bypass, artifact/pointer loss, redaction/truncation drift.
- `T16` Flake triage is fail-closed: pin env, rerun x3, run replay-check; unresolved flakes remain red.
- `T17` Test names/docstrings encode invariant IDs/semantics, not implementation trivia.
