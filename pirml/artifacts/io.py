from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from pirml.runtime.rpc import canonical_json


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    """C1.T02: Hash emitted/stored bytes only"""
    return hashlib.sha256(data).hexdigest()


def cas_path(obj_dir: Path, sha: str) -> Path:
    """C1.T01: Sharded CAS path"""
    return obj_dir / sha[:2] / sha[2:4] / sha


def atomic_write(path: Path, data: bytes) -> None:
    """C1.T01: Atomic write (no overwrite)"""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
