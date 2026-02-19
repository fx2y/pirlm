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


class FinalResult(TypedDict):
    ok: bool
    results: list[ResultRow]


class CallFrame(TypedDict):
    op: str  # Literal["call"]
    id: str
    tool: str
    args: dict[str, Any]
    ts: int


class ResultFrame(TypedDict, total=False):
    op: str  # Literal["result"]
    id: str
    ok: bool
    output: Any
    error: ErrorObject
    meta: dict[str, Any]
    ts: int
    truncated: bool
    truncated_bytes: int


class FinalFrame(TypedDict):
    op: str  # Literal["final"]
    ok: bool
    result: FinalResult
    ts: int


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
