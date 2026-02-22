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


# --- Web Pipeline Contracts (Sprint-4) ---


class WebTraceFrame(TypedDict, total=False):
    op: str  # search_call, search_result, fetch_call, fetch_result
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


# --- ToolSearch Contracts (Sprint-2) ---


class ToolManifest(TypedDict, total=False):
    """S.MF1: Tool manifest contract"""

    name: str
    description: str
    input_schema: dict[str, Any]
    input_examples: list[dict[str, Any]]
    idempotent: bool
    cacheable: bool
    max_payload_bytes: int
    timeout_s: float
    retry: dict[str, Any]
    allowed_callers: list[str]
    tags: list[str]
    defer_loading: bool
    aliases: list[str]
    verbs: list[str]
    nouns: list[str]


class SearchMode(str):
    BM25 = "bm25"
    REGEX = "regex"


class SearchErrorType(str):
    INVALID_PATTERN = "invalid_pattern"
    LENGTH_CAP_EXCEEDED = "length_cap_exceeded"
    NOT_FOUND = "not_found"


class ManifestError(TypedDict):
    """Authoring failure detail"""

    code: str
    msg: str
    path: str


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
