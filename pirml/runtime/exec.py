from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from ..clock import SequenceClock
from ..contracts.schemas import FinalResult, ResultRow
from .rpc import JSONObject, normalize_frames
from .tools import ToolRegistry


@dataclass(frozen=True)
class RunOutput:
    frames: list[JSONObject]
    final_result: FinalResult


def new_call_id(index: int) -> str:
    return f"c{index:05d}"


def run_live(
    program: list[JSONObject],
    registry: ToolRegistry,
    clock: SequenceClock,
    max_line_bytes: int,
) -> RunOutput:
    frames: list[JSONObject] = []
    result_rows: list[ResultRow] = []
    ok = True

    for idx, step in enumerate(program, start=1):
        tool_raw = step.get("tool")
        args_raw = step.get("args")
        if not isinstance(tool_raw, str):
            raise ValueError("step.tool must be a string")
        if not isinstance(args_raw, dict):
            raise ValueError("step.args must be an object")
        tool = tool_raw
        args = cast(Mapping[str, object], args_raw)
        call_id = new_call_id(idx)

        call_frame: JSONObject = {
            "op": "call",
            "id": call_id,
            "tool": tool,
            "args": args_raw,
            "ts": clock.now(),
        }
        frames.append(call_frame)

        try:
            output = registry.execute(str(tool), args)
            result_frame: JSONObject = {
                "op": "result",
                "id": call_id,
                "ok": True,
                "output": output,
                "ts": clock.now(),
            }
        except Exception as exc:  # noqa: BLE001
            ok = False
            result_frame = {
                "op": "result",
                "id": call_id,
                "ok": False,
                "error": str(exc),
                "ts": clock.now(),
            }

        frames.append(result_frame)

        row: ResultRow = {"id": call_id, "tool": str(tool), "ok": bool(result_frame["ok"])}
        if not bool(result_frame["ok"]):
            row["error"] = str(result_frame.get("error", ""))
        result_rows.append(row)

        if not bool(result_frame["ok"]):
            break

    final_result: FinalResult = {"ok": ok, "results": result_rows}
    final_frame: JSONObject = {"op": "final", "ok": ok, "result": final_result, "ts": clock.now()}
    frames.append(final_frame)

    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    return RunOutput(frames=normalized_frames, final_result=final_result)


def run_replay(frames: list[JSONObject], max_line_bytes: int) -> RunOutput:
    normalized_frames = normalize_frames(frames, max_line_bytes=max_line_bytes)
    final_frame = normalized_frames[-1]
    final_raw = final_frame.get("result")
    if not isinstance(final_raw, dict):
        raise ValueError("final.result must be an object")
    return RunOutput(frames=normalized_frames, final_result=cast(FinalResult, final_raw))
