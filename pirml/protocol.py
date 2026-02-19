from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

type JSONValue = Any
type JSONObject = dict[str, Any]

MAX_LINE_BYTES_DEFAULT = 8192


class ProtocolError(ValueError):
    pass


def canonical_json(value: JSONValue) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _line_bytes(line: str) -> int:
    return len(line.encode("utf-8"))


def parse_ndjson_lines(lines: Iterable[str]) -> list[JSONObject]:
    frames: list[JSONObject] = []
    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        if line == "":
            raise ProtocolError(f"blank line at {idx}")
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"invalid json at line {idx}: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ProtocolError(f"line {idx} must be a JSON object")
        frames.append(cast(JSONObject, parsed))
    if not frames:
        raise ProtocolError("trace is empty")
    return frames


def load_jsonl(path: Path) -> list[JSONObject]:
    with path.open("r", encoding="utf-8") as handle:
        return parse_ndjson_lines(handle)


def _truncate_result_output(frame: JSONObject, max_line_bytes: int) -> tuple[JSONObject, str]:
    output = frame.get("output")
    if not isinstance(output, str):
        raise ProtocolError("line exceeds max bytes and cannot be truncated")

    full_bytes = len(output.encode("utf-8"))
    candidate = dict(frame)
    candidate["truncated"] = True

    lo, hi = 0, len(output)
    best = -1
    while lo <= hi:
        mid = (lo + hi) // 2
        probe = dict(candidate)
        sliced = output[:mid]
        probe["output"] = sliced
        probe["truncated_bytes"] = full_bytes - len(sliced.encode("utf-8"))
        probe_line = canonical_json(probe)
        if _line_bytes(probe_line) <= max_line_bytes:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1

    if best < 0:
        raise ProtocolError("max_line_bytes too small for protocol overhead")

    truncated = dict(candidate)
    sliced = output[:best]
    truncated["output"] = sliced
    truncated["truncated_bytes"] = full_bytes - len(sliced.encode("utf-8"))
    line = canonical_json(truncated)
    if _line_bytes(line) > max_line_bytes:
        raise ProtocolError("failed to truncate to max_line_bytes")
    return truncated, line


def enforce_line_limit(frame: JSONObject, max_line_bytes: int) -> tuple[JSONObject, str]:
    line = canonical_json(frame)
    if _line_bytes(line) <= max_line_bytes:
        return frame, line
    if frame.get("op") != "result":
        raise ProtocolError("non-result frame exceeds max_line_bytes")
    return _truncate_result_output(frame, max_line_bytes)


def normalize_frames(frames: list[JSONObject], max_line_bytes: int) -> list[JSONObject]:
    normalized: list[JSONObject] = []
    for frame in frames:
        normalized_frame, _line = enforce_line_limit(frame, max_line_bytes)
        normalized.append(normalized_frame)
    validate_trace(normalized, max_line_bytes=max_line_bytes)
    return normalized


def validate_trace(frames: list[JSONObject], max_line_bytes: int = MAX_LINE_BYTES_DEFAULT) -> None:
    seen_calls: set[str] = set()
    seen_results: set[str] = set()
    final_count = 0

    for idx, frame in enumerate(frames, start=1):
        line = canonical_json(frame)
        if _line_bytes(line) > max_line_bytes:
            raise ProtocolError(f"line {idx} exceeds max_line_bytes={max_line_bytes}")

        op = frame.get("op")
        if op not in {"call", "result", "final"}:
            raise ProtocolError(f"unknown op at line {idx}: {op!r}")

        if op == "call":
            call_id = frame.get("id")
            if not isinstance(call_id, str) or call_id == "":
                raise ProtocolError(f"invalid call id at line {idx}")
            if call_id in seen_calls:
                raise ProtocolError(f"duplicate call id at line {idx}: {call_id}")
            seen_calls.add(call_id)

        elif op == "result":
            result_id = frame.get("id")
            if not isinstance(result_id, str) or result_id == "":
                raise ProtocolError(f"invalid result id at line {idx}")
            if result_id not in seen_calls:
                raise ProtocolError(f"unknown result id at line {idx}: {result_id}")
            if result_id in seen_results:
                raise ProtocolError(f"duplicate result id at line {idx}: {result_id}")
            seen_results.add(result_id)

        elif op == "final":
            final_count += 1
            if idx != len(frames):
                raise ProtocolError("final frame must be last")

    if final_count != 1:
        raise ProtocolError(f"expected exactly one final, got {final_count}")


def write_trace(path: Path, frames: list[JSONObject], max_line_bytes: int) -> list[JSONObject]:
    normalized = normalize_frames(frames, max_line_bytes=max_line_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for frame in normalized:
            handle.write(canonical_json(frame))
            handle.write("\n")
    return normalized


def write_final(path: Path, final_result: JSONObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(canonical_json(final_result))


def emit_stdout(frames: list[JSONObject], max_line_bytes: int) -> None:
    normalized = normalize_frames(frames, max_line_bytes=max_line_bytes)
    for frame in normalized:
        print(canonical_json(frame), flush=False)
