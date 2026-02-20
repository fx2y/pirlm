from __future__ import annotations

from pathlib import Path

from .protocol import JSONObject


def load_program(path: Path) -> list[JSONObject]:
    raise RuntimeError("pirml.program.load_program is legacy; compiler path forbidden")
