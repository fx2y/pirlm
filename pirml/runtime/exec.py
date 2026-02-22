from __future__ import annotations

import copy
import hashlib
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

from ..clock import SequenceClock
from ..contracts.schemas import ErrorObject, FinalResult, ResultRow
from .policy import (
    RuntimePolicySet,
    ToolRuntimePolicy,
    clamp_retry_budget,
    enforce_payload_cap,
    execution_policy_error,
    resolve_effective_timeout,
)
from .rpc import (
    JSONObject,
    ProtocolError,
    StreamValidator,
    canonical_json,
    enforce_line_limit,
    normalize_frames,
    read_frame,
    validate_strict_trace,
    write_frame,
)
from .tools import ToolRegistry, stable_env

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
    protocol_error: bool = False


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


@dataclass(frozen=True)
class _FrameEvent:
    kind: str
    payload: JSONObject | Exception | None = None


def new_call_id(index: int) -> str:
    return f"c{index:05d}"


def _sha256_val(val: Any) -> str:
    return hashlib.sha256(canonical_json(val).encode("utf-8")).hexdigest()


def _is_sensitive_key(key: str) -> bool:
    lk = key.lower()
    if lk.startswith("auth"):
        return True
    return lk in _SENSITIVE_ARG_KEYS


def _sanitize_args(value: Any, *, key_hint: str | None = None) -> Any:
    if key_hint is not None and _is_sensitive_key(key_hint):
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
    elif op == "custom":
        data = updated.get("data")
        updated["sha256_data"] = _sha256_val(data)
        if sanitize_call_args:
            updated["data"] = _sanitize_args(data)
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
    env = stable_env()
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


def _shutdown_process(proc: subprocess.Popen[str] | None, frames: list[JSONObject]) -> None:
    if proc is None:
        return
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


def _remaining_timeout_seconds(start_time: float, timeout: float) -> float:
    remaining = timeout - (time.monotonic() - start_time)
    if remaining <= 0:
        raise ProtocolError(f"global timeout reached ({timeout}s)")
    return remaining


def _start_frame_reader(
    proc: subprocess.Popen[str],
) -> tuple[queue.Queue[_FrameEvent], threading.Thread]:
    stdout = proc.stdout
    if stdout is None:
        raise ProtocolError("program stdout is not available")
    text_stdout = cast(TextIO, stdout)

    events: queue.Queue[_FrameEvent] = queue.Queue()

    def _pump() -> None:
        while True:
            try:
                frame = read_frame(text_stdout)
            except EOFError:
                events.put(_FrameEvent("eof"))
                return
            except Exception as exc:  # noqa: BLE001
                events.put(_FrameEvent("error", exc))
                return
            events.put(_FrameEvent("frame", frame))

    reader = threading.Thread(target=_pump, name="pirml-frame-reader", daemon=True)
    reader.start()
    return events, reader


def _read_program_frame(
    events: queue.Queue[_FrameEvent],
    *,
    start_time: float,
    timeout: float,
    poll_step: float = 0.05,
) -> JSONObject:
    while True:
        wait_s = min(poll_step, _remaining_timeout_seconds(start_time, timeout))
        try:
            event = events.get(timeout=wait_s)
        except queue.Empty:
            continue

        if event.kind == "frame":
            payload = event.payload
            if isinstance(payload, dict):
                return payload
            raise ProtocolError("reader returned non-object frame")
        if event.kind == "eof":
            raise EOFError("stream closed")
        if event.kind == "error":
            payload = event.payload
            if isinstance(payload, Exception):
                raise payload
            raise ProtocolError("reader thread failed")
        raise ProtocolError(f"unknown reader event: {event.kind}")


def _require_call_fields(
    frame: Mapping[str, Any],
) -> tuple[str, str, Mapping[str, Any], float | None]:
    if "id" not in frame or "tool" not in frame or "args" not in frame:
        raise ProtocolError("call frame missing required fields")
    call_id = frame["id"]
    tool = frame["tool"]
    args = frame["args"]
    timeout_val = frame["timeout"] if "timeout" in frame else None  # noqa: SIM401

    if not isinstance(call_id, str) or call_id == "":
        raise ProtocolError("call.id must be non-empty string")
    if not isinstance(tool, str) or tool == "":
        raise ProtocolError("call.tool must be non-empty string")
    if not isinstance(args, Mapping):
        raise ProtocolError("call.args must be an object")

    timeout: float | None = None
    if timeout_val is not None:
        if not isinstance(timeout_val, (int, float)):
            raise ProtocolError("call.timeout must be a number")
        timeout = float(timeout_val)

    return call_id, tool, cast(Mapping[str, Any], args), timeout


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
        truncated_bytes = payload.get("truncated_bytes", 0)
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
        error_val = result_frame.get("error")
        if isinstance(error_val, Mapping):
            # G14: Sanitize error fields to prevent leaks
            error_src = cast(Mapping[str, Any], error_val)
            error_dst: ErrorObject = {
                "type": str(error_src.get("type", "unknown")),
                "msg": str(error_src.get("msg", "")),
            }
            if "retryable" in error_src:
                error_dst["retryable"] = bool(error_src.get("retryable"))
            row["error"] = error_dst
    return row


def execute_with_retry(
    registry: ToolRegistry,
    *,
    tool: str,
    args: Mapping[str, Any],
    timeout: float | None,
    max_retries: int,
    policy: ToolRuntimePolicy | None = None,
) -> tuple[Mapping[str, Any], int]:
    if policy is not None:
        policy_error = execution_policy_error(tool, policy)
        if policy_error is not None:
            return {"ok": False, "error": policy_error}, 0

    retry_budget = clamp_retry_budget(max_retries, policy)
    retries = 0
    while True:
        payload = registry.execute(tool, args, timeout=timeout)
        payload = enforce_payload_cap(tool=tool, payload=payload, policy=policy)
        if payload.get("ok"):
            return payload, retries

        error = payload.get("error")
        retryable = isinstance(error, Mapping) and bool(error.get("retryable"))
        if policy is not None and not policy.idempotent:
            retryable = False
        if not retryable or retries >= retry_budget:
            return payload, retries
        retries += 1


def _result_payload_from_trace(frame: Any) -> JSONObject:
    ok = bool(frame["ok"]) if "ok" in frame else False
    payload: JSONObject = {"ok": ok}
    if ok:
        if "output" in frame:
            payload["output"] = copy.deepcopy(frame["output"])
    else:
        if "error" in frame:
            payload["error"] = copy.deepcopy(dict(cast(Mapping[str, Any], frame["error"])))
        else:
            payload["error"] = {
                "type": "unknown",
                "msg": "missing error payload",
                "retryable": False,
            }

    if "meta" in frame:
        payload["meta"] = copy.deepcopy(dict(cast(Mapping[str, Any], frame["meta"])))

    if "truncated" in frame and frame["truncated"] is True:
        payload["truncated"] = True
        truncated_bytes = frame["truncated_bytes"] if "truncated_bytes" in frame else 0  # noqa: SIM401
        if isinstance(truncated_bytes, int) and truncated_bytes >= 0:
            payload["truncated_bytes"] = truncated_bytes
        else:
            payload["truncated_bytes"] = 0
    return payload


def _build_replay_plan(replay_frames: list[JSONObject], max_line_bytes: int) -> _ReplayPlan:
    validate_strict_trace(replay_frames, max_line_bytes=max_line_bytes)
    call_ids: list[str] = []
    cassette: dict[str, JSONObject] = {}
    source_final_result: Mapping[str, Any] | None = None

    for frame in replay_frames:
        if "op" not in frame:
            raise ProtocolError("Replay error: missing 'op' in replay trace frame")
        op = frame["op"]
        if op == "call":
            if "id" not in frame:
                raise ProtocolError("Replay error: call frame missing id")
            call_id = frame["id"]
            if not isinstance(call_id, str):
                raise ProtocolError("Replay error: call id must be str")
            call_ids.append(call_id)
        elif op == "result":
            if "id" not in frame:
                raise ProtocolError("Replay error: result frame missing id")
            call_id = frame["id"]
            if not isinstance(call_id, str):
                raise ProtocolError("Replay error: result id must be str")
            if call_id in cassette:
                raise ProtocolError(f"Replay error: duplicate result id in replay trace: {call_id}")
            cassette[call_id] = _result_payload_from_trace(frame)
        elif op == "final":
            if "result" in frame:
                res = frame["result"]
                if isinstance(res, Mapping):
                    source_final_result = dict(cast(Mapping[str, Any], res))

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
    expected_sha = _sha256_val(source_final_result)
    actual_sha = _sha256_val(actual_final_result)
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


def _project_final_result(raw: Any, fallback_results: list[ResultRow]) -> FinalResult:
    """G4: Project and sanitize final results array to prevent leaks."""
    if not isinstance(raw, Mapping):
        return {"ok": False, "results": fallback_results}

    m_raw = cast(Mapping[str, Any], raw)
    ok = bool(m_raw["ok"]) if "ok" in m_raw else False

    # G15: Always favor supervisor's ground truth for results.
    # Program-provided results are ignored to ensure no extra fields leak (G14).
    results = fallback_results

    projected: FinalResult = {
        "ok": ok,
        "results": results,
    }
    if "output" in m_raw:
        projected["output"] = m_raw["output"]
    if "meta" in m_raw:
        projected["meta"] = cast(dict[str, Any], m_raw["meta"])
    return projected


def run_live(
    program_path: Path,
    registry: ToolRegistry,
    clock: SequenceClock,
    max_line_bytes: int,
    timeout: float = 30.0,
    runtime_policies: RuntimePolicySet | None = None,
) -> RunOutput:
    """S.EX2, S.EX3: Subprocess supervisor loop"""
    start_time = time.monotonic()
    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    validator = StreamValidator(max_line_bytes=max_line_bytes)
    envelope = _EnvelopeState(start_ts=clock.now())
    protocol_error = False
    proc = None
    frame_reader = None

    try:
        try:
            proc = _spawn_program(program_path, block_tools=False)
            frame_events, frame_reader_thread = _start_frame_reader(proc)
            frame_reader = frame_reader_thread

            while True:
                try:
                    frame = _read_program_frame(
                        frame_events,
                        start_time=start_time,
                        timeout=timeout,
                    )
                except EOFError:
                    break
                except (ProtocolError, TimeoutError, Exception) as exc:
                    protocol_error = True
                    print(f"Supervisor fatal error: {exc}", file=sys.stderr)
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
                    call_id, tool, args, tool_timeout = _require_call_fields(frame)

                    remaining = _remaining_timeout_seconds(start_time, timeout)
                    tool_policy = runtime_policies.for_tool(tool) if runtime_policies else None
                    policy_timeout = tool_policy.timeout_s if tool_policy is not None else None
                    if runtime_policies is not None and tool in runtime_policies.timeout_overrides_s:
                        policy_timeout = runtime_policies.timeout_overrides_s[tool]
                    elif (
                        runtime_policies is not None
                        and runtime_policies.default_timeout_s is not None
                        and policy_timeout is None
                    ):
                        policy_timeout = runtime_policies.default_timeout_s
                    effective_timeout = resolve_effective_timeout(
                        call_timeout=tool_timeout,
                        remaining_timeout=remaining,
                        policy_timeout=policy_timeout,
                    )

                    payload, retries = execute_with_retry(
                        registry,
                        tool=tool,
                        args=args,
                        timeout=effective_timeout,
                        max_retries=2,
                        policy=tool_policy,
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

            if proc and proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        except (ProtocolError, Exception) as exc:
            protocol_error = True
            print(f"Supervisor fatal error during run: {exc}", file=sys.stderr)

    finally:
        _shutdown_process(proc, frames)
        if frame_reader:
            frame_reader.join(timeout=0.2)

    if not frames or frames[-1].get("op") != "final":
        final_frame = _fallback_final(clock, envelope, result_rows)
        frames.append(final_frame)
        final_result = _project_final_result(final_frame.get("result"), result_rows)
    else:
        final_raw = frames[-1].get("result")
        final_result = _project_final_result(final_raw, result_rows)
        frames[-1]["result"] = final_result

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(
        frames=normalized_frames,
        final_result=final_result,
        protocol_error=protocol_error,
    )


def run_replay(
    program_path: Path,
    replay_frames: list[JSONObject],
    clock: SequenceClock,
    max_line_bytes: int,
    timeout: float = 30.0,
) -> RunOutput:
    """C4.T3/C4.T4: Replay mode execution at adapter-boundary cassette."""
    start_time = time.monotonic()
    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    validator = StreamValidator(max_line_bytes=max_line_bytes)
    envelope = _EnvelopeState(start_ts=clock.now())
    call_index = 0
    protocol_error = False
    proc = None
    frame_reader = None
    plan = None

    try:
        try:
            plan = _build_replay_plan(replay_frames, max_line_bytes=max_line_bytes)
            proc = _spawn_program(program_path, block_tools=True)
            frame_events, frame_reader_thread = _start_frame_reader(proc)
            frame_reader = frame_reader_thread

            while True:
                try:
                    frame = _read_program_frame(
                        frame_events,
                        start_time=start_time,
                        timeout=timeout,
                    )
                except EOFError:
                    break
                except (ProtocolError, TimeoutError, Exception) as exc:
                    protocol_error = True
                    print(f"Supervisor fatal error: {exc}", file=sys.stderr)
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
                    call_id, tool, _args, _tool_timeout = _require_call_fields(frame)
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

            if proc and proc.poll() is None:
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
        except (ProtocolError, Exception) as exc:
            protocol_error = True
            print(f"Supervisor fatal error during replay run: {exc}", file=sys.stderr)

    finally:
        _shutdown_process(proc, frames)
        if frame_reader:
            frame_reader.join(timeout=0.2)

    if not frames or frames[-1].get("op") != "final":
        final_frame = _fallback_final(clock, envelope, result_rows)
        frames.append(final_frame)
        final_result = _project_final_result(final_frame.get("result"), result_rows)
    else:
        final_raw = frames[-1].get("result")
        final_result = _project_final_result(final_raw, result_rows)
        frames[-1]["result"] = final_result

    # If plan was never built, source_final_result is unknown
    source_final_result = plan.source_final_result if plan else None

    parity_meta = _replay_parity_meta(
        actual_final_result=final_result,
        source_final_result=source_final_result,
    )
    if parity_meta is not None and frames and frames[-1].get("op") == "final":
        final_frame = dict(frames[-1])
        final_frame["meta"] = parity_meta
        frames[-1] = final_frame
        if parity_meta.get("replay_match") is False:
            protocol_error = True
            print("Supervisor fatal error: replay hash mismatch", file=sys.stderr)

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(
        frames=normalized_frames,
        final_result=final_result,
        protocol_error=protocol_error,
    )
