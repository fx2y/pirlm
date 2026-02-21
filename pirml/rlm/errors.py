from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class RlmErrorType(StrEnum):
    MISSING_FINAL = "rlm_missing_final"
    BUDGET_EXCEEDED = "rlm_budget_exceeded"
    CONTEXT_CAP_EXCEEDED = "rlm_context_cap_exceeded"
    UNSUPPORTED_VARIANT = "rlm_unsupported_variant"


class RlmTypedError(TypedDict):
    type: str
    msg: str
    retryable: bool


def rlm_error(
    error_type: RlmErrorType,
    msg: str,
    *,
    retryable: bool = False,
) -> RlmTypedError:
    return {"type": str(error_type), "msg": msg, "retryable": retryable}
