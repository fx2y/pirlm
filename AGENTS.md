# PIRML Constitution

Mission: deterministic orchestration substrate where verification cost `V` stays far below generation cost `G` (`V<<G`) and every run is replay-auditable.

## Hard Laws
- `H0` Policy root is this file only. No sibling policy docs. Detail lives in imported `.codex/rules/*`.
- `H1` Gate contract: `mise run ci` (dev+CI). Inner loop: `mise run fast` (<3s class).
- `H2` Fail-fast ladder is fixed: `fmt > lint > types > unit > proto > trace > schemas > replay`.
- `H3` Determinism is default: pinned env (`PYTHONHASHSEED=0`,`TZ=UTC`,`LC_ALL=C`,`LANG=C`,`SOURCE_DATE_EPOCH`), canonical JSON, sequence clock, stable IDs.
- `H4` Protocol algebra is frozen: `op in {call,result,final}` only; exactly one `final`; `final` is last.
- `H5` ID law: `c%05d`, monotonic, globally unique per run.
- `H6` Line-byte cap is enforced at protocol boundary; only `result` may truncate and must expose `truncated` + `truncated_bytes`.
- `H7` Sprint-1 tool surface is frozen: `echo`,`readfile`,`bash`. Replay executes zero tools (`PIRML_BLOCK_TOOLS=1` path must pass).
- `H8` Trace is product: every run (including fatal paths) emits `trace.ndjson` + `final.json`; replay hash parity for `final.json` is mandatory.
- `H9` Output channel split is strict: stdout = NDJSON protocol only; diagnostics = stderr only.
- `H10` Exit code contract: `0` success (`final.ok=true`), `1` business/tool failure (`final.ok=false`), `2` protocol/config/supervisor integrity failure.

## Engineering Doctrine
- `E0` Python `3.12`, strict pyright. If types are awkward, redesign API before casting.
- `E1` Prefer pure transforms + explicit contracts; hidden mutable state is defect-prone.
- `E2` `final.json` is compact boundary state (`ok`,`results`, optional `output/meta`); never dump raw transcripts there.
- `E3` Scripts run as modules (`python -m scripts.*`) only.
- `E4` Error semantics must be typed and deterministic (`type,msg,retryable`), not regex-on-text.

## Compounding Loop
- `C0` Behavior change without invariant delta is invalid.
- `C1` Every incident/perf regression ships with: failing test first, patch, and stricter invariant/gate/docs update.
- `C2` New pattern learned? Update this constitution or imported rule in the same change.
- `C3` Unknown future iteration rule: choose stricter deterministic contract over convenience unless cost data proves otherwise.

## Operator Entry Points
- Setup: `mise run boot`
- Fast loop: `mise run fast`
- Full gate: `mise run ci`
- Replay parity smoke: `python -m scripts.replay_check`
- Perf smoke: `mise run bench` (`out/bench.json`)

## Memory Layout
- Shared policy: `AGENTS.md` (tracked)
- Conditional detail: `.codex/rules/*.md` (path-scoped)
- Private local prefs: `AGENTS.local.md` (gitignored, optional)

@.codex/rules/10-runtime-protocol.md
@.codex/rules/20-tests-determinism.md
@.codex/rules/30-tooling-tasks.md
