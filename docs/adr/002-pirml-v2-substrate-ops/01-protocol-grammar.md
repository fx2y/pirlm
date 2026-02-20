# Protocol Grammar (V2-Substrate)

## Frame: {id: str, op: str, ...}
- **id**: `c%05d` (e.g., `c00001`). Monotonic.
- **op**: `call` | `result` | `final`.

## op: call
- **tool**: `str`. Registry-mapped.
- **args**: `dict[str, Any]`. Redacted in trace (auth*/token/password/secret/api_key).

## op: result
- **ok**: `bool`.
- **output**: `str` (optional). Truncated at line-cap boundary.
- **error**: `dict` (optional). `{type: ErrorType, msg: str, retryable: bool}`. Msg truncated at cap.
- **meta**: `dict` (optional). `{read_bytes: int, exit_code: int, retries: int}`.
- **truncated**: `bool`. `true` if output/error.msg exceeded cap.
- **truncated_bytes**: `int`. Count of bytes removed.

## op: final
- **ok**: `bool`.
- **results**: `list[ResultRow]`. Summary only. `[{id: str, tool: str, ok: bool, error: {type: str, msg: str}}]`.
- **output**: `Any` (optional). Program-defined summary.
- **meta**: `dict` (optional). Program-defined KPIs.

## Envelope: {seq: int, dir: str, ms: int, ts: str, p: Frame, h: str}
- **seq**: Monotonic 1-based.
- **dir**: `>` (to supervisor) | `<` (to program).
- **ms**: Offset from start (int).
- **ts**: ISO-8601 (Canonical Clock).
- **p**: Payload (Frame).
- **h**: SHA-256 of `p` (Canonical JSON).
