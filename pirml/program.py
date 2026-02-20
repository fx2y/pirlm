from __future__ import annotations

from pathlib import Path
from typing import cast

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
    raise RuntimeError("pirml.program.load_program is legacy; compiler path forbidden")
