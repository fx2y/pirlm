from dataclasses import dataclass
from typing import TypedDict


class ErrorRow(TypedDict):
    type: str
    msg: str
    retryable: bool


@dataclass
class UxError(Exception):
    type: str
    msg: str
    retryable: bool = False

    def to_row(self) -> ErrorRow:
        return {
            "type": self.type,
            "msg": self.msg,
            "retryable": self.retryable,
        }


class IntegrityError(UxError):
    def __init__(self, msg: str):
        super().__init__(type="integrity", msg=msg, retryable=False)


class ConfigError(UxError):
    def __init__(self, msg: str):
        super().__init__(type="config", msg=msg, retryable=False)


class TimeoutError(UxError):
    def __init__(self, msg: str):
        super().__init__(type="timeout", msg=msg, retryable=True)


class RuntimeError(UxError):
    def __init__(self, msg: str, retryable: bool = False):
        super().__init__(type="runtime", msg=msg, retryable=retryable)


class ArtifactError(UxError):
    def __init__(self, msg: str):
        super().__init__(type="artifact", msg=msg, retryable=False)
