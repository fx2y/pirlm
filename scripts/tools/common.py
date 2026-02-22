from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn


def typed_error(err_type: str, msg: str, retryable: bool = False) -> dict[str, object]:
    return {"type": err_type, "msg": msg, "retryable": retryable}


def emit_error(err_type: str, msg: str, code: int) -> NoReturn:
    print(json.dumps(typed_error(err_type, msg)), file=sys.stderr)
    raise SystemExit(code)


def resolve_art_root(default_root: Path, projection_root: Path = Path(".pirml/artifacts")) -> Path:
    if default_root == Path("art") and not default_root.exists() and projection_root.exists():
        return projection_root
    return default_root
