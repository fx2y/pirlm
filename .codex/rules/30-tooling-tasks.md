---
paths:
  - ".mise.toml"
  - "pyproject.toml"
  - "pyrightconfig.json"
  - "requirements-dev.txt"
  - "scripts/*.py"
  - "scripts/**/*.py"
  - "spec-0/**/*.jsonl"
---
# Tooling + Task Rules

## G0-G8 Gate Authority
- `G0` `mise` is execution contract; release authority is `mise run ci`.
- `G1` Gate order immutable fail-fast: `fmt>lint>types>unit>proto>trace>schemas>replay`.
- `G2` `fast` stays `<3s`, high-yield, reject-only; never mini-CI.
- `G3` Script entry style is module-only: `python -m scripts.*`.
- `G4` Tool/runtime/version pins are policy (determinism + supply-chain), not convenience.
- `G5` Dependency admission bar: measurable correctness/determinism/perf gain > maintenance/risk cost.
- `G6` Gate/task edits must prove value in same merge via `mise run fast` + `mise run ci` (+ replay/schema proof if boundary changed).
- `G7` Gating consumes explicit artifacts (`out/<run>/...`), never hidden process state.
- `G8` Ingress explicit-only: schema/report/artifact lint commands need explicit args; missing declared artifact hard-fails; recursive scans forbidden.

## G9-G17 Runtime/Wrapper Governance
- `G9` Emitted pointers (`trace_ptr`, artifact/view refs, projection refs) must resolve and pass schema/frame checks.
- `G10` Eval harness executes every declared row or emits typed unsupported; no silent skip/fallback.
- `G11` CI authority uses canonical compact bytes only; human summaries are non-authoritative.
- `G12` Exit-code law across wrappers/runners: `0 success`, `1 biz/unsupported/tool/validation`, `2 integrity/config/internal`.
- `G13` Fail lanes emit typed JSON stderr envelopes (`type,msg,retryable`).
- `G14` UX wrappers/extensions/toolpack delegate to one execution owner path; no alternate runtime path.
- `G15` Runtime tool-surface freeze: wrapper growth stays external; runtime registry remains `{echo,readfile,bash}`.
- `G16` All CLI parsers/subparsers/legacy use strict fail-closed parse; parse failures are typed stderr JSON (no `usage:` leakage).
- `G17` Helper lanes additive-only; `tasks.ci.run` and `tasks.fast.run` byte contracts cannot drift silently.

## G18-G27 Status + Compounding
- `G18` Status authority is current-cycle `spec-0/*-tasks.jsonl`; other ledgers are support only.
- `G19` Behavior deltas co-update `spec-0/00-learnings.jsonl`, current `spec-0/*-tasks.jsonl`, current `spec-0/*-tutorial.jsonl` in same merge.
- `G20` `done` only when live locus exists, named tests exist, contradictions resolved (`owner+enforce`), matrix refs resolve, proof cmds rerun clean.
- `G21` Matrix owner/test refs must resolve in-repo (real or typed-placeholder suites); unresolved refs block done.
- `G22` In-repo fixture helpers are labeled smoke; non-fixture benchmarks need explicit dataset override in commands/docs.
- `G23` Report commands consume suite-scoped shard logs via explicit args; flat/implicit patterns invalid.
- `G24` Setup commands (e.g., `mise run boot`) must be idempotent on provisioned workspaces.
- `G25` Release-ready minimum proof set: `mise run fast`, `mise run ci`, replay check, artifact rebuild check, relevant cycle smoke/parity suites.
- `G26` If any authority proof later fails, flip impacted cycle/task from done to active before new claims.
- `G27` Any new `op|tool|gate|schema|runtime|cli-surface` needs invariant delta + failing test + synced handoff ledgers/docs.
