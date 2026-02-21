from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class ArtifactErrorType(StrEnum):
    PATH_INVALID = "artifact_path_invalid"
    PATH_UNSUPPORTED_VARIANT = "artifact_path_unsupported_variant"
    NOT_FOUND = "artifact_not_found"
    ALREADY_EXISTS = "artifact_already_exists"
    VIEW_SPEC_INVALID = "view_spec_invalid"
    INTEGRITY = "artifact_integrity_error"


class ArtifactTypedError(TypedDict):
    type: str
    msg: str
    retryable: bool


def artifact_error(
    error_type: ArtifactErrorType,
    msg: str,
    *,
    retryable: bool = False,
) -> ArtifactTypedError:
    return {"type": str(error_type), "msg": msg, "retryable": retryable}


class ArtifactPathError(ValueError):
    def __init__(
        self,
        *,
        error_type: ArtifactErrorType,
        msg: str,
        retryable: bool = False,
    ) -> None:
        super().__init__(msg)
        self.error: ArtifactTypedError = artifact_error(
            error_type=error_type,
            msg=msg,
            retryable=retryable,
        )
