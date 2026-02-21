from __future__ import annotations

import enum
from typing import Literal, NotRequired, TypedDict


class RlmErrorType(enum.StrEnum):
    BUDGET_EXCEEDED = "rlm_budget_exceeded"
    MAX_ITERS_REACHED = "rlm_max_iters_reached"
    FINAL_MISSING = "rlm_final_missing"
    SANDBOX_ERROR = "rlm_sandbox_error"
    INVALID_ARGS = "rlm_invalid_args"
    INTEGRITY = "rlm_integrity_error"


class RlmTypedError(TypedDict):
    type: str
    msg: str
    retryable: bool


class RlmBudget(TypedDict):
    max_iters: int
    max_subcalls: int
    max_parallel: int
    timeout_s: float


class RlmHistoryFrame(TypedDict):
    seq: int
    prefix: str  # First 100 chars
    len: int  # Full stdout length
    ts: int
    ev: Literal["call", "result", "log"]
    code: NotRequired[str]  # The code that was executed
    aid: NotRequired[str]  # artifact_id link
    vid: NotRequired[str]  # view_id link
