from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, cast

from .protocol import JSONObject


def _validate_step(raw_step: object, idx: int) -> JSONObject:
    if not isinstance(raw_step, dict):
        raise ValueError(f"PROGRAM[{idx}] must be an object")
    step = cast(dict[str, object], raw_step)

    tool = step.get("tool")
    if not isinstance(tool, str) or tool == "":
        raise ValueError(f"PROGRAM[{idx}].tool must be a non-empty string")

    args_raw = step.get("args", {})
    if not isinstance(args_raw, dict):
        raise ValueError(f"PROGRAM[{idx}].args must be an object")

    return {"tool": tool, "args": args_raw}


def load_program(path: Path) -> list[JSONObject]:
    namespace = cast(dict[str, object], runpy.run_path(str(path)))
    raw_program = namespace.get("PROGRAM")
    if not isinstance(raw_program, list):
        raise ValueError("PROGRAM must be a list of tool calls")

    steps: list[JSONObject] = []
    for idx, raw_step in enumerate(cast(list[Any], raw_program)):
        steps.append(_validate_step(raw_step, idx))
    return steps
