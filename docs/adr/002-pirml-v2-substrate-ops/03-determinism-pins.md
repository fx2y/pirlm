# Determinism Pins (V2-Substrate)

## Environment Pins (HC1):
- **PYTHONHASHSEED**: `0`. Mandatory for `hash()` stability.
- **TZ**: `UTC`. Mandatory for `ts` (timestamp) consistency.
- **LC_ALL**: `C.UTF-8`. Mandatory for `locale` consistency.
- **SDE**: `1`. Software Deterministic Environment.
- **PIRML_BLOCK_TOOLS**: `1` (Replay only). Blocks tool execution.
- **PIRML_BLOCK_CLOCK**: `1` (Replay only). Pins `ts` to live trace timestamps.
- **PIRML_BLOCK_SEED**: `1` (Replay only). Reuses live random seed if applicable.

## SequenceClock (HC1):
- **Implementation**: `count(start=0)`.
- **Usage**:
    - `ms`: Elapsed from 0.
    - `ts`: `2026-02-20T10:00:00Z` + `seq`.
    - `id`: `c%05d`.

## Canonical JSON (HC1):
- **Codec**: `json.dumps(obj, sort_keys=True, separators=(",", ":"))`.
- **Invariants**:
    - No trailing whitespace.
    - Keys alphabetically ordered.
    - Stable width for integers.
    - Float precision fixed (if applicable).

## Product-Grade Trace (HC4):
- **Envelope-First**: Every line is a complete event.
- **Hash-Chain**: Optional (Future). Current: `h` = `sha256(payload)`.
- **Ordered**: `seq` and `ms` must be non-decreasing.
- **Persistence**: `ALWAYS return RunOutput`. `rc2` paths still emit `trace.ndjson` + `final.json` (compact failure).
