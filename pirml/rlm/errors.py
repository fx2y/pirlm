from __future__ import annotations

from .types import RlmErrorType, RlmTypedError


def rlm_error(
    error_type: RlmErrorType,
    msg: str,
    *,
    retryable: bool = False,
) -> RlmTypedError:
    return {"type": str(error_type), "msg": msg, "retryable": retryable}


class RlmKernelError(ValueError):
    def __init__(
        self,
        *,
        error_type: RlmErrorType,
        msg: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(msg)
        self.error: RlmTypedError = rlm_error(
            error_type=error_type,
            msg=msg,
            retryable=retryable,
        )
