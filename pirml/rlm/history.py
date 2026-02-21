from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal

from .types import RlmHistoryFrame


class RlmHistory:
    def __init__(self) -> None:
        self._frames: list[RlmHistoryFrame] = []
        self._seq = 1

    def append(
        self,
        ev: Literal["call", "result", "log", "custom"],
        prefix: str,
        full_len: int,
        ts: int,
        **payload: Any,
    ) -> RlmHistoryFrame:
        """C3.T03: Capture code stdout; append metadata {prefix,len} only to history"""
        frame: RlmHistoryFrame = {
            "seq": self._seq,
            "prefix": prefix[:100],
            "len": full_len,
            "ts": ts,
            "ev": ev,
        }
        frame.update(payload)  # type: ignore
        self._frames.append(frame)
        self._seq += 1
        return frame

    def __iter__(self) -> Iterator[RlmHistoryFrame]:
        return iter(self._frames)

    def __len__(self) -> int:
        return len(self._frames)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [dict(f) for f in self._frames]
