---
paths:
  - "tests/*.py"
  - "tests/**/*.py"
  - "tests/fixtures/**/*.jsonl"
  - "tests/golden/**/*"
---
# Test + Determinism Rules

## T0-T7 Test Frame
- `T0` Determinism mandatory: no live network/oracle, no wall-clock asserts, no unseeded randomness, no locale/TZ coupling.
- `T1` Tests rerun-stable and order-independent; isolate artifacts in temp roots; never share mutable `out/**`.
- `T2` Contract-first proofs: prefer CLI/artifact black-box checks; internals only when boundary cannot encode invariant.
- `T3` Every invariant has dual lanes: pass + typed fail.
- `T4` Done claims require executable evidence; prose/logs are non-evidence.
- `T5` Bugfix protocol fixed: reproduce -> failing test -> patch -> `mise run fast` -> `mise run ci` (+ replay/schema proofs if boundary changed).
- `T6` Goldens are byte contracts; drift/missing fails; no self-heal/auto-regenerate in tests.
- `T7` Compile XOR proof required: success `{prog.py+contract.json}` and inverse fail `{compile_error.json}`.

## T8-T15 Deterministic Integrity
- `T8` Boundary-byte edits (`trace|final|hash|order|clock|cache|trunc`) require deterministic rerun x3; include hashseed variation when relevant.
- `T9` Replay-affecting edits must extend replay parity tests, including real task-level replay-guard lanes.
- `T10` Eval anti-fraud tests required: every declared row executes or typed-returns unsupported; no silent skip/default winner.
- `T11` Fail-closed config tests required: unknown provider/cache/variant/plan/path/flag typed-fail early.
- `T12` CLI parse tests required: parse failures emit typed stderr envelope + correct `rc`; no raw `usage:` dumps.
- `T13` Dataset integrity tests required: explicit ingress, prompt-key semantics, duplicate `task_id` rejection, anti-tautology guards.
- `T14` Resume/report integrity tests required: seq drift, duplicate terminals, corrupt NDJSON => integrity/code2.
- `T15` Ordering claims require explicit permutation + tie-break tests; incidental order coverage is not proof.

## T16-T23 Coverage Obligations
- `T16` Metrics/taxonomy tests required: required key set, single-label `fail_tag`, explicit `NO_CITE`, exact persisted `acc`.
- `T17` Pointer/projection tests required: resolvability + non-destructive projection + payload split (`details` vs one-line hint `<=120`).
- `T18` Optional-capability tests required: default-off typed unsupported lane plus enabled lane.
- `T19` Merge blockers: op/order/id drift, replay drift, schema strictness drift, pointer non-resolve, stdout pollution, tool-surface growth, trunc/redaction drift.
- `T20` Flake triage is fail-closed: pin env, rerun x3, replay-check; unresolved flake stays red.
- `T21` Test names/docstrings encode invariant IDs/semantics, not implementation trivia.
- `T22` Matrix refs must resolve to executable suite/case (or explicit typed placeholder lane).
- `T23` If any authority proof fails post-`done`, reopen impacted cycle/task before new feature work.

## T24-T30 Product-Layer Hardening
- `T24` Command-matrix tests enforce single-source rows, owner-path validation, and alias non-authority.
- `T25` Proof-pack tests enforce required lane execution, deterministic index bytes, and pointer resolvability.
- `T26` Incident tests enforce fixed chain (`trace->classify->replay->artifact`) and truthful root `rc`.
- `T27` Resolver tests enforce strict parse typed failures, read-only behavior, and no hidden ingress.
- `T28` Claim-packaging tests enforce machine-claim rows with resolvable `artifact_ptr` + invariant/proof bind.
- `T29` Gate-helper tests enforce additive-only task growth and unchanged `fast/ci` byte contracts.
- `T30` Showcase/doc-command tests enforce shell-valid blocks + explicit-ingress examples for authority commands.
