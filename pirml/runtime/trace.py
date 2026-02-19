from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .rpc import JSONObject, canonical_json, normalize_frames


def write_trace(path: Path, frames: list[JSONObject], max_line_bytes: int) -> list[JSONObject]:
    """S.TR1: Trace writer"""
    normalized = normalize_frames(frames, max_line_bytes=max_line_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for frame in normalized:
            handle.write(canonical_json(frame))
            handle.write("\n")
    return normalized


def write_final(path: Path, final_result: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(canonical_json(final_result))


def emit_stdout(frames: list[JSONObject], max_line_bytes: int) -> None:
    normalized = normalize_frames(frames, max_line_bytes=max_line_bytes)
    for frame in normalized:
        print(canonical_json(frame), flush=False)
