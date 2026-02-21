from __future__ import annotations

from typing import Any

from pirml.runtime.rpc import canonical_json


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")
