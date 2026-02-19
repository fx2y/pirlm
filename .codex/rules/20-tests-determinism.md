---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
---
# Test + Determinism Rules

- Determinism is mandatory: no wall-clock assertions, no unseeded randomness, no network.
- Use temp dirs for writes; tests must be order-independent and rerun-stable.
- Validate protocol behavior through CLI traces, not private internals.
- Every invariant in runtime must have at least one failing-path test.
- Bugfix policy: reproduce -> write failing test -> patch -> replay/ci prove closure.
- Golden files are contracts; update only with explicit rationale tied to intended behavior change.
- Replay parity is required for behavior changes affecting trace/final content.
- Keep tests narrow and named by invariant, not by implementation trivia.
