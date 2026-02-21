---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
  - "tests/fixtures/**/*.jsonl"
  - "tests/golden/**/*"
---
# Test + Determinism Rules

- `T0` Determinism mandatory: no live network, wall-clock assertions, unseeded randomness, locale/TZ dependence.
- `T1` Tests rerun-stable/order-independent; artifacts isolate in temp dirs, never shared mutable `out/**`.
- `T2` Contract-first proofs: favor CLI/artifact black-box checks; internals only when boundary cannot encode invariant.
- `T3` Invariant proof is dual-lane: at least one pass path and one typed fail path; empty-success labeled fail is invalid.
- `T4` Bugfix protocol fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay/schema proof if boundary touched.
- `T5` Goldens are contractual bytes; missing/drift must fail; no auto-generate/self-heal during test run.
- `T6` Compile branch proof required: success asserts `prog.py+contract.json` and no `compile_error.json`; fail path asserts inverse.
- `T7` Boundary byte edits (trace/final/hash/order/clock/cache) require deterministic x3 proof, including hash-seed variation when relevant.
- `T8` Replay edits must update replay-parity coverage; omission is merge-blocking.
- `T9` Matrix/eval anti-fraud tests required: every declared plan executes or typed-fails; no silent skips/default winners.
- `T10` Fail-closed config tests required: unknown provider/cache/variant/plan must typed-fail (no implicit fallback).
- `T11` Ordering claims require explicit permutation+tiebreak tests; incidental ordering coverage is invalid.
- `T12` Merge blockers: algebra/order/id drift, replay parity drift, schema strictness drift, timeout integrity drift, artifact/pointer loss, redaction/truncation drift.
- `T13` Flake triage: enforce env pins, rerun x3, replay-check; unresolved flakes stay red (no silent waive).
- `T14` Test names/docstrings should encode invariant IDs/semantics, not implementation trivia.
