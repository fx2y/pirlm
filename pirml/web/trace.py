from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict, cast


class WebTraceFrame(TypedDict, total=False):
    op: str
    ts: int
    seq: int
    ms: int
    q: str
    url: str
    provider: str
    status: int
    bytes: int
    sha256: str
    cache_hit: bool
    error: str


class WebTracer:
    def __init__(self, start_ts: int | None = None) -> None:
        self._start_ts = 0 if start_ts is None else start_ts
        self._seq = 1
        self._frames: list[WebTraceFrame] = []

    def emit(self, op: str, **kwargs: Any) -> None:
        ms = self._seq - 1
        frame: WebTraceFrame = cast(
            WebTraceFrame,
            {
                "op": op,
                "ts": self._start_ts + ms,
                "seq": self._seq,
                "ms": ms,
                **kwargs,
            },
        )
        self._frames.append(frame)
        self._seq += 1

    def get_frames(self) -> list[WebTraceFrame]:
        return list(self._frames)

    def write_to(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for frame in self._frames:
                # Use canonical JSON (sorted keys)
                line = json.dumps(frame, sort_keys=True, separators=(",", ":"))
                f.write(line + "\n")


__all__ = ["WebTracer", "WebTraceFrame"]
