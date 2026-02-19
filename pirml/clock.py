from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_EPOCH = 1_700_000_000


@dataclass
class SequenceClock:
    start: int
    step: int = 1
    _tick: int = 0

    @classmethod
    def from_env(cls) -> SequenceClock:
        raw = os.environ.get("SOURCE_DATE_EPOCH")
        if raw is None:
            return cls(start=_DEFAULT_EPOCH)
        return cls(start=int(raw))

    def now(self) -> int:
        current = self.start + (self._tick * self.step)
        self._tick += 1
        return current
