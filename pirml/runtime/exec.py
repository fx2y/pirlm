from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..clock import SequenceClock
from ..contracts.schemas import ErrorObject, FinalResult, ResultRow
from .rpc import (
    JSONObject,
    ProtocolError,
    StreamValidator,
    canonical_json,
    enforce_line_limit,
    normalize_frames,
    read_frame,
    write_frame,
)
from .tools import ToolRegistry

_SENSITIVE_ARG_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "password",
        "secret",
        "token",
    }
)


@dataclass(frozen=True)
class RunOutput:
    frames: list[JSONObject]
    final_result: FinalResult


@dataclass
class _EnvelopeState:
    start_ts: int
    seq: int = 0

    def apply(self, frame: Mapping[str, Any], *, direction: str, sanitize_args: bool) -> JSONObject:
        stamped = dict(frame)
        ts_val = stamped.get("ts")
        if not isinstance(ts_val, int):
            raise ProtocolError("frame ts must be int")

        self.seq += 1
        stamped["seq"] = self.seq
        stamped["dir"] = direction
        stamped["ms"] = ts_val - self.start_ts
        return _attach_hashes(stamped, sanitize_call_args=sanitize_args)


@dataclass(frozen=True)
class _ReplayPlan:
    call_ids: list[str]
    cassette: dict[str, JSONObject]
    source_final_result: Mapping[str, Any] | None


def new_call_id(index: int) -> str:
    return f"c{index:05d}"


def _sha256_val(val: Any) -> str:
    return hashlib.sha256(canonical_json(val).encode("utf-8")).hexdigest()


def _sha256_json(val: Any) -> str:
    return hashlib.sha256(canonical_json(val).encode("utf-8")).hexdigest()


def _sanitize_args(value: Any, *, key_hint: str | None = None) -> Any:
    if key_hint is not None and key_hint.lower() in _SENSITIVE_ARG_KEYS:
        return {"redacted_sha256": _sha256_val(value)}
    if isinstance(value, Mapping):
        return {
            str(k): _sanitize_args(v, key_hint=str(k))
            for k, v in cast(Mapping[str, Any], value).items()
        }
    if isinstance(value, list):
        items = cast(list[Any], value)
        return [_sanitize_args(item) for item in items]
    return value


def _attach_hashes(frame: Mapping[str, Any], *, sanitize_call_args: bool) -> JSONObject:
    updated = dict(frame)
    op = updated.get("op")
    if op == "call":
        args = updated.get("args")
        updated["sha256_args"] = _sha256_val(args)
        if sanitize_call_args:
            updated["args"] = _sanitize_args(args)
    elif op == "result":
        if "output" in updated:
            updated["sha256_output"] = _sha256_val(updated.get("output"))
        elif "error" in updated:
            updated["sha256_output"] = _sha256_val(updated.get("error"))
    elif op == "final":
        updated["sha256_output"] = _sha256_val(updated.get("result"))
    return updated


def _refresh_result_hash(frame: Mapping[str, Any]) -> JSONObject:
    updated = dict(frame)
    if "output" in updated:
        updated["sha256_output"] = _sha256_val(updated.get("output"))
    elif "error" in updated:
        updated["sha256_output"] = _sha256_val(updated.get("error"))
    return updated


def _fit_result_frame(frame: Mapping[str, Any], max_line_bytes: int) -> JSONObject:
    limited, _ = enforce_line_limit(frame, max_line_bytes)
    if limited.get("truncated") is True:
        limited = _refresh_result_hash(limited)
        limited, _ = enforce_line_limit(limited, max_line_bytes)
    return limited


def _spawn_program(program_path: Path, *, block_tools: bool) -> subprocess.Popen[str]:
    env = dict(os.environ)
    ppath = env.get("PYTHONPATH", "")
    cwd = os.getcwd()
    env["PYTHONPATH"] = f"{cwd}{os.pathsep}{ppath}" if ppath else cwd
    if block_tools:
        env["PIRML_BLOCK_TOOLS"] = "1"

    return subprocess.Popen(
        [sys.executable, str(program_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )


def _shutdown_process(proc: subprocess.Popen[str], frames: list[JSONObject]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)

    if proc.stdin:
        proc.stdin.close()
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        err_data = proc.stderr.read()
        if err_data and (not frames or frames[-1].get("op") != "final"):
            print(err_data, file=sys.stderr)
        proc.stderr.close()


def _require_call_fields(frame: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    call_id = frame.get("id")
    tool = frame.get("tool")
    args = frame.get("args")
    if not isinstance(call_id, str) or call_id == "":
        raise ProtocolError("call.id must be non-empty string")
    if not isinstance(tool, str) or tool == "":
        raise ProtocolError("call.tool must be non-empty string")
    if not isinstance(args, Mapping):
        raise ProtocolError("call.args must be an object")
    return call_id, tool, cast(Mapping[str, Any], args)


def _build_result_frame(
    *,
    call_id: str,
    payload: Mapping[str, Any],
    ts: int,
    retries: int,
) -> JSONObject:
    ok = bool(payload.get("ok"))
    frame: JSONObject = {
        "op": "result",
        "id": call_id,
        "ok": ok,
        "ts": ts,
    }
    if ok:
        frame["output"] = payload.get("output")
    else:
        error = payload.get("error")
        if not isinstance(error, Mapping):
            error = {"type": "unknown", "msg": "missing error payload", "retryable": False}
        frame["error"] = dict(cast(Mapping[str, Any], error))

    meta = payload.get("meta")
    frame["meta"] = dict(cast(Mapping[str, Any], meta)) if isinstance(meta, Mapping) else {}
    if retries > 0:
        frame["meta"]["retries"] = retries

    if payload.get("truncated") is True:
        frame["truncated"] = True
        truncated_bytes = payload.get("truncated_bytes")
        if not isinstance(truncated_bytes, int) or truncated_bytes < 0:
            truncated_bytes = 0
        frame["truncated_bytes"] = truncated_bytes

    return frame


def _result_row(call_id: str, tool: str, result_frame: Mapping[str, Any]) -> ResultRow:
    row: ResultRow = {
        "id": call_id,
        "tool": tool,
        "ok": bool(result_frame.get("ok")),
    }
    if not bool(result_frame.get("ok")):
        error = result_frame.get("error")
        if isinstance(error, Mapping):
            row["error"] = cast(ErrorObject, dict(cast(Mapping[str, Any], error)))
    return row


def _execute_with_retry(
    registry: ToolRegistry,
    *,
    tool: str,
    args: Mapping[str, Any],
    max_retries: int,
) -> tuple[Mapping[str, Any], int]:
    retries = 0
    while True:
        payload = registry.execute(tool, args)
        if payload.get("ok"):
            return payload, retries

        error = payload.get("error")
        retryable = isinstance(error, Mapping) and bool(error.get("retryable"))
        if not retryable or retries >= max_retries:
            return payload, retries
        retries += 1


def _result_payload_from_trace(frame: Mapping[str, Any]) -> JSONObject:
    payload: JSONObject = {"ok": bool(frame.get("ok"))}
    if payload["ok"]:
        payload["output"] = copy.deepcopy(frame.get("output"))
    else:
        error = frame.get("error")
        if isinstance(error, Mapping):
            payload["error"] = copy.deepcopy(dict(cast(Mapping[str, Any], error)))
        else:
            payload["error"] = {
                "type": "unknown",
                "msg": "missing error payload",
                "retryable": False,
            }

    meta = frame.get("meta")
    if isinstance(meta, Mapping):
        payload["meta"] = copy.deepcopy(dict(cast(Mapping[str, Any], meta)))

    if frame.get("truncated") is True:
        payload["truncated"] = True
        truncated_bytes = frame.get("truncated_bytes")
        if isinstance(truncated_bytes, int) and truncated_bytes >= 0:
            payload["truncated_bytes"] = truncated_bytes
        else:
            payload["truncated_bytes"] = 0
    return payload


def _build_replay_plan(replay_frames: list[JSONObject]) -> _ReplayPlan:
    call_ids: list[str] = []
    cassette: dict[str, JSONObject] = {}
    source_final_result: Mapping[str, Any] | None = None

    for frame in replay_frames:
        op = frame.get("op")
        if op == "call":
            call_id = frame.get("id")
            if not isinstance(call_id, str) or call_id == "":
                raise ProtocolError("Replay error: invalid call id in replay trace")
            call_ids.append(call_id)
        elif op == "result":
            call_id = frame.get("id")
            if not isinstance(call_id, str) or call_id == "":
                raise ProtocolError("Replay error: invalid result id in replay trace")
            cassette[call_id] = _result_payload_from_trace(frame)
        elif op == "final":
            result = frame.get("result")
            if isinstance(result, Mapping):
                source_final_result = dict(cast(Mapping[str, Any], result))
        else:
            raise ProtocolError(f"Replay error: unknown op in replay trace: {op!r}")

    return _ReplayPlan(
        call_ids=call_ids,
        cassette=cassette,
        source_final_result=source_final_result,
    )


def _replay_parity_meta(
    *,
    actual_final_result: Mapping[str, Any],
    source_final_result: Mapping[str, Any] | None,
) -> JSONObject | None:
    if source_final_result is None:
        return None
    expected_sha = _sha256_json(source_final_result)
    actual_sha = _sha256_json(actual_final_result)
    return {
        "replay_expected_final_sha256": expected_sha,
        "replay_actual_final_sha256": actual_sha,
        "replay_match": expected_sha == actual_sha,
    }


def _fallback_final(
    clock: SequenceClock, envelope: _EnvelopeState, result_rows: list[ResultRow]
) -> JSONObject:
    final_result: FinalResult = {"ok": False, "results": result_rows}
    frame: JSONObject = {
        "op": "final",
        "ok": False,
        "result": final_result,
        "ts": clock.now(),
    }
    return envelope.apply(frame, direction="in", sanitize_args=False)


def run_live(
    program_path: Path,
    registry: ToolRegistry,
    clock: SequenceClock,
    max_line_bytes: int,
    timeout: float = 30.0,
) -> RunOutput:
    """S.EX2, S.EX3: Subprocess supervisor loop"""
    _ = timeout
    proc = _spawn_program(program_path, block_tools=False)

    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    validator = StreamValidator(max_line_bytes=max_line_bytes)

    envelope = _EnvelopeState(start_ts=clock.now())

    try:
        while True:
            try:
                frame = read_frame(proc.stdout)  # type: ignore
            except EOFError:
                break
            except Exception as exc:
                raise ProtocolError(f"Supervisor read failed: {exc}") from exc

            inbound_with_ts = dict(frame)
            inbound_with_ts["ts"] = clock.now()
            inbound_frame = envelope.apply(
                inbound_with_ts,
                direction="in",
                sanitize_args=True,
            )
            validator.validate_frame(inbound_frame)
            frames.append(inbound_frame)

            op = inbound_frame.get("op")
            if op == "call":
                call_id, tool, args = _require_call_fields(frame)
                payload, retries = _execute_with_retry(
                    registry,
                    tool=tool,
                    args=args,
                    max_retries=2,
                )
                res_frame = _build_result_frame(
                    call_id=call_id,
                    payload=payload,
                    ts=clock.now(),
                    retries=retries,
                )
                res_frame = envelope.apply(
                    res_frame,
                    direction="out",
                    sanitize_args=False,
                )
                res_frame = _fit_result_frame(res_frame, max_line_bytes=max_line_bytes)
                validator.validate_frame(res_frame)
                write_frame(proc.stdin, res_frame, max_line_bytes)  # type: ignore
                frames.append(res_frame)
                result_rows.append(_result_row(call_id, tool, res_frame))
            elif op == "final":
                break

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)

    finally:
        _shutdown_process(proc, frames)

    if not frames or frames[-1].get("op") != "final":
        final_frame = _fallback_final(clock, envelope, result_rows)
        frames.append(final_frame)
        final_result = cast(FinalResult, final_frame["result"])
    else:
        final_raw = frames[-1].get("result")
        if not isinstance(final_raw, dict):
            raise ProtocolError("final.result must be an object")
        final_result = cast(FinalResult, final_raw)

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(frames=normalized_frames, final_result=final_result)


def run_replay(
    program_path: Path,
    replay_frames: list[JSONObject],
    clock: SequenceClock,
    max_line_bytes: int,
    timeout: float = 30.0,
) -> RunOutput:
    """C4.T3/C4.T4: Replay mode execution at adapter-boundary cassette."""
    _ = timeout
    plan = _build_replay_plan(replay_frames)
    proc = _spawn_program(program_path, block_tools=True)

    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    validator = StreamValidator(max_line_bytes=max_line_bytes)
    envelope = _EnvelopeState(start_ts=clock.now())

    call_index = 0

    try:
        while True:
            try:
                frame = read_frame(proc.stdout)  # type: ignore
            except EOFError:
                break

            inbound_with_ts = dict(frame)
            inbound_with_ts["ts"] = clock.now()
            inbound_frame = envelope.apply(
                inbound_with_ts,
                direction="in",
                sanitize_args=True,
            )
            validator.validate_frame(inbound_frame)
            frames.append(inbound_frame)

            op = inbound_frame.get("op")
            if op == "call":
                call_id, tool, _args = _require_call_fields(frame)
                if call_index >= len(plan.call_ids):
                    raise ProtocolError(f"Replay error: unexpected extra call id {call_id}")
                expected_id = plan.call_ids[call_index]
                if call_id != expected_id:
                    raise ProtocolError(
                        f"Replay error: expected call id {expected_id}, got {call_id}"
                    )
                payload = plan.cassette.get(call_id)
                if payload is None:
                    raise ProtocolError(
                        f"Replay error: missing cassette entry for call id {call_id}"
                    )

                res_frame = _build_result_frame(
                    call_id=call_id,
                    payload=payload,
                    ts=clock.now(),
                    retries=0,
                )
                res_frame = envelope.apply(
                    res_frame,
                    direction="out",
                    sanitize_args=False,
                )
                res_frame = _fit_result_frame(res_frame, max_line_bytes=max_line_bytes)
                validator.validate_frame(res_frame)
                write_frame(proc.stdin, res_frame, max_line_bytes)  # type: ignore
                frames.append(res_frame)
                result_rows.append(_result_row(call_id, tool, res_frame))
                call_index += 1
            elif op == "final":
                if call_index != len(plan.call_ids):
                    raise ProtocolError(
                        f"Replay error: call sequence ended early ({call_index}/{len(plan.call_ids)})"
                    )
                break

        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1)

    finally:
        _shutdown_process(proc, frames)

    if not frames or frames[-1].get("op") != "final":
        final_frame = _fallback_final(clock, envelope, result_rows)
        frames.append(final_frame)
        final_result = cast(FinalResult, final_frame["result"])
    else:
        final_raw = frames[-1].get("result")
        if not isinstance(final_raw, dict):
            raise ProtocolError("final.result must be an object")
        final_result = cast(FinalResult, final_raw)

    parity_meta = _replay_parity_meta(
        actual_final_result=final_result,
        source_final_result=plan.source_final_result,
    )
    if parity_meta is not None and frames and frames[-1].get("op") == "final":
        final_frame = dict(frames[-1])
        final_frame["meta"] = parity_meta
        frames[-1] = final_frame

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(frames=normalized_frames, final_result=final_result)
