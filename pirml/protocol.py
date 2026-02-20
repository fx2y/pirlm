from __future__ import annotations

from pathlib import Path

from .runtime.rpc import (
    MAX_LINE_BYTES_DEFAULT,
    JSONObject,
    JSONValue,
    ProtocolError,
    StreamValidator,
    call,
    canonical_json,
    enforce_line_limit,
    normalize_frames,
    parse_ndjson_lines,
    read_frame,
    send_final,
    validate_strict_trace,
    validate_trace,
    write_frame,
)
from .runtime.trace import (
    emit_stdout,
    write_final,
    write_metrics,
    write_trace,
)


def load_jsonl(path: Path) -> list[JSONObject]:
    with path.open("r", encoding="utf-8") as handle:
        return parse_ndjson_lines(handle)


__all__ = [
    "MAX_LINE_BYTES_DEFAULT",
    "JSONObject",
    "JSONValue",
    "ProtocolError",
    "StreamValidator",
    "call",
    "canonical_json",
    "enforce_line_limit",
    "normalize_frames",
    "parse_ndjson_lines",
    "read_frame",
    "send_final",
    "validate_trace",
    "validate_strict_trace",
    "write_frame",
    "emit_stdout",
    "write_final",
    "write_metrics",
    "write_trace",
    "load_jsonl",
]
