from __future__ import annotations

import asyncio
import json
import sys
import threading
from collections.abc import Iterable, Mapping, Sequence
from contextlib import suppress
from typing import Any, TextIO, cast


class ProtocolError(ValueError):
    pass


type JSONValue = Any
type JSONObject = dict[str, Any]


MAX_LINE_BYTES_DEFAULT = 8192


def canonical_json(value: Any) -> str:
    """S.RPC1: Canon dump"""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _line_bytes(line: str) -> int:
    return len(line.encode("utf-8"))


def read_frame(handle: TextIO) -> JSONObject:
    """S.RPC3: Strict stream read"""
    line = handle.readline()
    if not line:
        raise EOFError("stream closed")
    line = line.rstrip("\n")
    if line == "":
        raise ProtocolError("blank line in stream")
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid json: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ProtocolError("frame must be a JSON object")
    return cast(JSONObject, parsed)


def write_frame(
    handle: TextIO, frame: Mapping[str, Any], max_line_bytes: int = MAX_LINE_BYTES_DEFAULT
) -> None:
    """S.RPC4: Strict stream write"""
    _, line = enforce_line_limit(frame, max_line_bytes)
    handle.write(line)
    handle.write("\n")
    handle.flush()


_program_call_count = 0
_program_call_lock = threading.Lock()


def call(tool: str, args: Mapping[str, Any]) -> JSONObject:
    """S.PG1: Program-side call helper (blocking)"""
    global _program_call_count
    with _program_call_lock:
        _program_call_count += 1
        call_id = f"c{_program_call_count:05d}"
    frame: JSONObject = {
        "op": "call",
        "id": call_id,
        "tool": tool,
        "args": args,
        "ts": 0,
    }
    write_frame(sys.stdout, frame)

    # Wait for result
    while True:
        resp = read_frame(sys.stdin)
        if resp.get("op") == "result":
            if resp.get("id") != call_id:
                # If we get interleaved results in blocking call, it's a protocol violation
                # or missing parallel support.
                raise ProtocolError(f"expected result for {call_id}, got {resp.get('id')}")
            return resp
        if resp.get("op") == "final":
            raise ProtocolError("received final while waiting for result")


class AsyncRpcClient:
    """S.PG2: Async fan-out support"""

    def __init__(self, reader: TextIO = sys.stdin, writer: TextIO = sys.stdout):
        self.reader = reader
        self.writer = writer
        self._pending: dict[str, asyncio.Future[JSONObject]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._call_count = 0
        self._lock = threading.Lock()
        self._read_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._read_task = asyncio.create_task(self._reader_loop())

    async def stop(self) -> None:
        if self._read_task:
            self._read_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._read_task
            self._read_task = None

    async def _reader_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                # read_frame is blocking, run in executor
                frame = await loop.run_in_executor(None, read_frame, self.reader)
                op = frame.get("op")
                if op == "result":
                    call_id = frame.get("id")
                    if isinstance(call_id, str) and call_id in self._pending:
                        self._pending[call_id].set_result(frame)
                        del self._pending[call_id]
                elif op == "final":
                    # Should not really happen inbound to program unless supervisor is weird
                    pass
            except EOFError:
                break
            except Exception as exc:
                for fut in self._pending.values():
                    if not fut.done():
                        fut.set_exception(exc)
                break

    async def call(self, tool: str, args: Mapping[str, Any]) -> JSONObject:
        with self._lock:
            self._call_count += 1
            call_id = f"c{self._call_count:05d}"

        frame: JSONObject = {
            "op": "call",
            "id": call_id,
            "tool": tool,
            "args": args,
            "ts": 0,
        }
        loop = self._loop if self._loop is not None else asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[call_id] = fut
        write_frame(self.writer, frame)
        return await fut


def send_final(ok: bool, result: Mapping[str, Any]) -> None:
    """S.PG1: Program-side final helper"""
    frame: JSONObject = {
        "op": "final",
        "ok": ok,
        "result": result,
        "ts": 0,
    }
    write_frame(sys.stdout, frame)


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


def _truncate_result_output(
    frame: Mapping[str, Any], max_line_bytes: int
) -> tuple[JSONObject, str]:
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


def enforce_line_limit(frame: Mapping[str, Any], max_line_bytes: int) -> tuple[JSONObject, str]:
    """S.RPC2: Byte cap gate"""
    line = canonical_json(frame)
    if _line_bytes(line) <= max_line_bytes:
        return cast(JSONObject, frame), line
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


class StreamValidator:
    """S.SM1: Progressive FSM validator"""

    def __init__(self, max_line_bytes: int = MAX_LINE_BYTES_DEFAULT):
        self.max_line_bytes = max_line_bytes
        self.seen_calls: set[str] = set()
        self.seen_results: set[str] = set()
        self.final_count = 0

    def validate_frame(self, frame: Mapping[str, Any]) -> None:
        line = canonical_json(frame)
        if _line_bytes(line) > self.max_line_bytes:
            raise ProtocolError(f"frame exceeds max_line_bytes={self.max_line_bytes}")

        op = frame.get("op")
        if op not in {"call", "result", "final"}:
            raise ProtocolError(f"unknown op: {op!r}")

        if self.final_count > 0:
            raise ProtocolError("frame after final")

        if op == "call":
            call_id = frame.get("id")
            if not isinstance(call_id, str) or call_id == "":
                raise ProtocolError("invalid call id")
            if call_id in self.seen_calls:
                raise ProtocolError(f"duplicate call id: {call_id}")
            self.seen_calls.add(call_id)

        elif op == "result":
            result_id = frame.get("id")
            if not isinstance(result_id, str) or result_id == "":
                raise ProtocolError("invalid result id")
            if result_id not in self.seen_calls:
                raise ProtocolError(f"unknown result id: {result_id}")
            if result_id in self.seen_results:
                raise ProtocolError(f"duplicate result id: {result_id}")
            self.seen_results.add(result_id)

        elif op == "final":
            self.final_count += 1


def validate_trace(
    frames: Sequence[Mapping[str, Any]], max_line_bytes: int = MAX_LINE_BYTES_DEFAULT
) -> None:
    validator = StreamValidator(max_line_bytes=max_line_bytes)
    for idx, frame in enumerate(frames, start=1):
        try:
            validator.validate_frame(frame)
        except ProtocolError as exc:
            raise ProtocolError(f"line {idx}: {exc}") from exc

        if frame.get("op") == "final" and idx != len(frames):
            raise ProtocolError(f"line {idx}: final frame must be last")

    if validator.final_count != 1:
        raise ProtocolError(f"expected exactly one final, got {validator.final_count}")
