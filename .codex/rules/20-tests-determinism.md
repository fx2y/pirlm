---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
  - "tests/fixtures/**/*.jsonl"
  - "tests/golden/**/*"
---
# Test + Determinism Rules

- `T0` Determinism mandatory: no live network/oracle, no wall-clock assertions, no unseeded randomness, no locale/TZ coupling.
- `T1` Tests must be rerun-stable/order-independent; isolate artifacts in temp roots; never share mutable `out/**`.
- `T2` Proof style is contract-first: prefer CLI/artifact black-box checks; use internals only when boundary cannot encode invariant.
- `T3` Every invariant needs dual lanes: one pass lane + one typed fail lane; silent/untested fail lanes are invalid.
- `T4` `done` evidence requires executable artifacts + invariant coverage; green logs/prose are non-evidence.
- `T5` Bugfix protocol fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` -> replay/schema proof if boundary changed.
- `T6` Goldens are contractual bytes; drift/missing is failure; no self-heal/auto-regenerate in tests.
- `T7` Compile XOR proof required: success lane (`prog.py+contract.json`, no `compile_error.json`) and fail lane inverse.
- `T8` Boundary byte edits (`trace/final/hash/order/clock/cache`) require deterministic rerun x3; add hashseed variation where relevant.
- `T9` Replay-affecting edits must extend replay parity tests; omission blocks merge.
- `T10` Eval anti-fraud tests required: all declared plans execute or typed-return unsupported; no silent skip/default winner.
- `T11` Fail-closed config tests required: unknown provider/cache/variant/plan/path must typed-fail.
- `T12` Ordering claims require explicit permutation + tie-break tests; incidental order coverage is not evidence.
- `T13` Governor/recursion claims require cap/cohesion tests (`warn`,`hard-fail`, deterministic fanout merge).
- `T14` Pointer/projection claims require resolvability + non-destructive projection tests; payload split (`custom data` vs tiny message) must be asserted.
- `T15` Optional capability tests must prove default-off typed unsupported lane and enabled lane.
- `T16` Merge blockers: op/order/id drift, replay drift, schema strictness drift, pointer loss/non-resolve, stdout pollution, tool-surface growth, truncation/redaction drift.
- `T17` Flake triage is fail-closed: pin env, rerun x3, run replay check; unresolved flakes remain red.
- `T18` Test names/docstrings should encode invariant IDs/semantics, not implementation trivia.
