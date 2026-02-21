from __future__ import annotations

from pathlib import Path
from typing import Any

from pirml.clock import SequenceClock
from pirml.runtime.rpc import canonical_json


class ArtifactTraceWriter:
    def __init__(self, path: Path, clock: SequenceClock | None = None) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or SequenceClock.from_env()
        self._seq = 1

    @property
    def clock(self) -> SequenceClock:
        return self._clock

    def append(self, ev: str, aid: str | None = None, **payload: Any) -> None:
        """C1.T05: Append-only trace with canonical NDJSON"""
        frame = {
            "id": f"c{self._seq:05d}",
            "seq": self._seq,
            "ts": self._clock.now(),
            "ev": ev,
        }
        if aid:
            frame["aid"] = aid
        frame.update(payload)

        with self._path.open("a", encoding="utf-8") as f:
            f.write(canonical_json(frame))
            f.write("\n")
            f.flush()

        self._seq += 1
