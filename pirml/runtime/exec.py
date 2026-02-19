from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..clock import SequenceClock
from ..contracts.schemas import FinalResult, ResultRow
from .rpc import (
    JSONObject,
    ProtocolError,
    StreamValidator,
    enforce_line_limit,
    normalize_frames,
    read_frame,
    write_frame,
)
from .tools import ToolRegistry


@dataclass(frozen=True)
class RunOutput:
    frames: list[JSONObject]
    final_result: FinalResult


def new_call_id(index: int) -> str:
    return f"c{index:05d}"


def run_live(
    program_path: Path,
    registry: ToolRegistry,
    clock: SequenceClock,
    max_line_bytes: int,
    timeout: float = 30.0,
) -> RunOutput:
    """S.EX2, S.EX3: Subprocess supervisor loop"""
    # Ensure subprocess can find pirml
    env = dict(os.environ)
    ppath = env.get("PYTHONPATH", "")
    cwd = os.getcwd()
    env["PYTHONPATH"] = f"{cwd}{os.pathsep}{ppath}" if ppath else cwd

    proc = subprocess.Popen(
        [sys.executable, str(program_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )

    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    validator = StreamValidator(max_line_bytes=max_line_bytes)

    try:
        while True:
            try:
                # C2.T3: Read call/final from prog stdout
                frame = read_frame(proc.stdout)  # type: ignore
            except EOFError:
                break
            except Exception as exc:
                # Protocol error or similar
                raise ProtocolError(f"Supervisor read failed: {exc}") from exc

            frame["ts"] = clock.now()
            validator.validate_frame(frame)
            frames.append(frame)

            op = frame.get("op")
            if op == "call":
                # C2.T4: Dispatch tool -> emit result
                call_id = cast(str, frame.get("id"))
                tool = cast(str, frame.get("tool"))
                args = cast(Mapping[str, Any], frame.get("args"))

                # C3.T5: Retry wrapper
                max_retries = 2
                attempt = 0
                res_payload: Any = {
                    "ok": False,
                    "error": {"type": "unknown", "msg": "no execution", "retryable": False},
                }

                while attempt <= max_retries:
                    res_payload = registry.execute(tool, args)
                    if res_payload.get("ok"):
                        break

                    error = res_payload.get("error", {})
                    if not error.get("retryable"):
                        break

                    attempt += 1
                    # Exponential backoff could be here, but for now simple retry

                res_frame: JSONObject = {
                    "op": "result",
                    "id": call_id,
                    "ok": res_payload.get("ok", False),
                    "ts": clock.now(),
                }
                if res_payload.get("ok"):
                    res_frame["output"] = res_payload.get("output")
                else:
                    res_frame["error"] = res_payload.get("error")

                if "meta" in res_payload:
                    res_frame["meta"] = res_payload["meta"]
                else:
                    res_frame["meta"] = {}

                if attempt > 0:
                    res_frame["meta"]["retries"] = attempt

                res_frame, _ = enforce_line_limit(res_frame, max_line_bytes)
                validator.validate_frame(res_frame)
                write_frame(proc.stdin, res_frame, max_line_bytes)  # type: ignore
                frames.append(res_frame)

                row: ResultRow = {
                    "id": call_id,
                    "tool": tool,
                    "ok": bool(res_frame["ok"]),
                }
                if not res_frame["ok"]:
                    row["error"] = res_frame.get("error")  # type: ignore
                result_rows.append(row)

                if not res_frame["ok"]:
                    # Hard fail on tool error for now to match old behavior?
                    # Spec says "prog subprocess loop supports call/result/final with hard fail semantics"
                    # If tool fails, we send result.ok=false. Prog decides if it wants to continue.
                    pass

            elif op == "final":
                break

        # S.TO1: Process control
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()

        if proc.stdin:
            proc.stdin.close()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            # Route stderr to trace-only channel (implied by S.EX2)
            # For now just read it and print to our stderr if we didn't get a clean final
            err_data = proc.stderr.read()
            if err_data and (not frames or frames[-1].get("op") != "final"):
                print(err_data, file=sys.stderr)
            proc.stderr.close()

    # Ensure we have a final frame
    if not frames or frames[-1].get("op") != "final":
        final_result: FinalResult = {"ok": False, "results": result_rows}
        final_frame: JSONObject = {
            "op": "final",
            "ok": False,
            "result": final_result,
            "ts": clock.now(),
        }
        frames.append(final_frame)
    else:
        final_raw = frames[-1].get("result")
        if not isinstance(final_raw, dict):
            raise ProtocolError("final.result must be an object")
        final_result = cast(FinalResult, final_raw)

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(frames=normalized_frames, final_result=final_result)


def run_replay(frames: list[JSONObject], max_line_bytes: int) -> RunOutput:
    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    final_frame = normalized_frames[-1]
    final_raw = final_frame.get("result")
    if not isinstance(final_raw, dict):
        raise ValueError("final.result must be an object")
    return RunOutput(frames=normalized_frames, final_result=cast(FinalResult, final_raw))
