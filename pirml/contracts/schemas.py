from __future__ import annotations

from typing import Any, TypedDict


class ErrorObject(TypedDict, total=False):
    type: str
    msg: str
    retryable: bool


class ResultRow(TypedDict, total=False):
    """S.TY1: Typed payload"""

    id: str
    tool: str
    ok: bool
    error: ErrorObject


class FinalResult(TypedDict, total=False):
    ok: bool
    results: list[ResultRow]
    output: Any
    meta: dict[str, Any]


class CallFrame(TypedDict, total=False):
    op: str  # Literal["call"]
    id: str
    tool: str
    args: dict[str, Any]
    timeout: float
    ts: int
    seq: int
    dir: str
    ms: int
    sha256_args: str


class ResultFrame(TypedDict, total=False):
    op: str  # Literal["result"]
    id: str
    ok: bool
    output: Any
    error: ErrorObject
    meta: dict[str, Any]
    ts: int
    seq: int
    dir: str
    ms: int
    sha256_output: str
    truncated: bool
    truncated_bytes: int


class FinalFrame(TypedDict, total=False):
    op: str  # Literal["final"]
    ok: bool
    result: FinalResult
    meta: dict[str, Any]
    ts: int
    seq: int
    dir: str
    ms: int
    sha256_output: str


# S.CT1: Contract schema seed
FINAL_JSON_SCHEMA = {
    "type": "object",
    "required": ["ok", "results"],
    "properties": {
        "ok": {"type": "boolean"},
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "tool", "ok"],
                "properties": {
                    "id": {"type": "string"},
                    "tool": {"type": "string"},
                    "ok": {"type": "boolean"},
                    "error": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string"},
                            "msg": {"type": "string"},
                            "retryable": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    },
}
