from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .rpc import JSONObject, canonical_json, normalize_frames


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_metrics(
    path: Path,
    frames: list[JSONObject],
    final_result: Mapping[str, Any],
    trace_path: Path,
    final_path: Path,
) -> None:
    """C4.T5: Emit metrics row"""
    calls = sum(1 for f in frames if f.get("op") == "call")
    retries = 0
    for f in frames:
        if f.get("op") == "result":
            meta = f.get("meta", {})
            if isinstance(meta, Mapping):
                retry_count = cast(Mapping[str, Any], meta).get("retries", 0)
                if isinstance(retry_count, int):
                    retries += retry_count

    failures = sum(1 for f in frames if f.get("op") == "result" and not f.get("ok"))

    # wall_ms from last frame ms
    last_frame = frames[-1] if frames else {}
    wall_ms = cast(int, last_frame.get("ms", 0))
    final_ok = final_result.get("ok", False)
    trace_sha = _sha256_path(trace_path)
    final_sha = _sha256_path(final_path)

    row = [
        str(calls),
        str(retries),
        str(failures),
        str(wall_ms),
        "1" if final_ok else "0",
        trace_sha,
        final_sha,
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", encoding="utf-8") as handle:
        if write_header:
            handle.write("calls,retries,failures,wall_ms,final_ok,trace_sha,final_sha\n")
        handle.write(",".join(row) + "\n")


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
