# PIRML Agent Constitution

Repo mission: deterministic harness where verification cost `V` stays far below generation cost `G` (`V<<G`), with hard fail gradients and replayable evidence.

## Non-Negotiables
- Single repo-level policy file is this file (`AGENTS.md`); no sibling policy docs. Heavy detail lives only in imported `.codex/rules/*`.
- One gate contract: `mise run ci` (dev+CI). Fast loop: `mise run fast` (<3s target).
- Gate order is fixed and fail-fast: `fmt > lint > types > unit > proto > trace > replay`.
- Determinism first: pinned env (`PYTHONHASHSEED=0`,`TZ=UTC`,`LC_ALL=C`,`LANG=C`,`SOURCE_DATE_EPOCH`), canonical JSON (`sort_keys`,`separators`), stable call ids, sequence clock.
- Sprint-1 tool surface frozen: `echo`,`readfile`,`bash`. Replay executes zero tools (`PIRML_BLOCK_TOOLS=1` path must pass).
- Trace is product: every run emits `trace.ndjson` + `final.json`; replay hash of `final.json` must match live.
- Protocol algebra frozen to `{call,result,final}`; exactly one `final`, and it is last.
- Max-line-bytes enforced at protocol boundary; only `result` frames may truncate and must expose `truncated` + `truncated_bytes`.

## Build / Validate Entrypoints
- Setup: `mise run boot`
- Full gate: `mise run ci`
- Fast gate: `mise run fast`
- Perf smoke: `mise run bench` (writes `out/bench.json`)
- Watch loop: `mise watch fast`

## Coding Style (Opinionated)
- Python 3.12 + strict pyright; if type precision is hard, redesign API before adding casts.
- Prefer pure transforms + explicit data contracts; hidden mutable state is a bug magnet.
- Keep stdout protocol-clean (NDJSON only). Human diagnostics go to stderr.
- Scripts run as modules (`python -m scripts.*`), never path-hack execution.
- State model: append-only frame log + derived compact final summary (`id/tool/ok/error`), never duplicate raw payloads in `final.json`.

## UI / Content Rules
- No GUI currently; “UI” is CLI/protocol output.
- Output must be machine-first, stable, ASCII-safe, diff-friendly, and order-deterministic.
- If future UI is added: render from trace/final artifacts, no hidden client-only truth.

## Living Spec Loop (Compounding)
- Any bug/incident/perf regression must land with one of: new invariant, new/updated test, or stricter gate; prefer all three.
- Behavioral diffs without test delta are invalid.
- New pattern discovered? Update this constitution (or imported rule) in the same change; no “tribal memory”.

## Debug Playbook (Symptom -> Move)
- Flake/non-repro -> freeze env/time/hashseed, remove network, rerun x3, then replay.
- Protocol break -> lint trace first (`mise run proto`/`mise run trace`), inspect frame order/ids, then code.
- Replay mismatch -> compare `trace.ndjson` bytes and final hash; check canonicalization/id/clock drift.
- Slow loop -> keep heavy checks in `ci`, shrink `fast` scope, benchmark with `mise run bench`.

## Memory Layout
- Shared policy: `AGENTS.md` (tracked).
- Conditional detail: `.codex/rules/*.md` (path-scoped).
- Private local prefs: `AGENTS.local.md` (ignored by git, optional).

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
