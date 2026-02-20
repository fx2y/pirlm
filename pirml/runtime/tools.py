from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict

from .rpc import JSONValue


class ErrorType(StrEnum):
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"
    TOOL_NOT_FOUND = "tool_not_found"
    ARGUMENT_ERROR = "argument_error"
    EXECUTION_ERROR = "execution_error"
    FILE_NOT_FOUND = "file_not_found"
    PERMISSION_DENIED = "permission_denied"


class ErrorObject(TypedDict, total=False):
    type: str
    msg: str
    retryable: bool


class ToolResult(TypedDict, total=False):
    ok: bool
    output: Any
    error: ErrorObject
    meta: dict[str, Any]


ToolFn = Callable[[Mapping[str, JSONValue], float | None], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def execute(
        self, name: str, args: Mapping[str, JSONValue], timeout: float | None = None
    ) -> ToolResult:
        """S.TL1: Tool choke-point"""
        if os.environ.get("PIRML_BLOCK_TOOLS") == "1":
            return {
                "ok": False,
                "error": {
                    "type": ErrorType.PERMISSION_DENIED,
                    "msg": "tool execution blocked by PIRML_BLOCK_TOOLS",
                    "retryable": False,
                },
            }
        if name not in self._tools:
            return {
                "ok": False,
                "error": {
                    "type": ErrorType.TOOL_NOT_FOUND,
                    "msg": f"unknown tool: {name}",
                    "retryable": False,
                },
            }
        try:
            return self._tools[name](args, timeout)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": {
                    "type": ErrorType.EXECUTION_ERROR,
                    "msg": str(exc),
                    "retryable": False,
                },
            }


def _expect_str(args: Mapping[str, JSONValue], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def stable_env() -> dict[str, str]:
    stable = dict(os.environ)
    stable.update(
        {
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
        }
    )
    return stable


def tool_echo(args: Mapping[str, JSONValue], timeout: float | None = None) -> ToolResult:
    _ = timeout
    try:
        text = _expect_str(args, "text")
        return {"ok": True, "output": text}
    except ValueError as exc:
        return {
            "ok": False,
            "error": {"type": ErrorType.ARGUMENT_ERROR, "msg": str(exc), "retryable": False},
        }


def tool_readfile(args: Mapping[str, JSONValue], timeout: float | None = None) -> ToolResult:
    _ = timeout
    try:
        path_str = _expect_str(args, "path")
        path = Path(path_str)
        # C3.T3: Byte cap arg/default
        max_bytes = args.get("max_bytes")
        if max_bytes is not None and not isinstance(max_bytes, int):
            raise ValueError("max_bytes must be an integer")

        # Default to 1MB if not specified for safety, though protocol has its own limit
        read_limit = max_bytes if max_bytes is not None else 1024 * 1024

        if not path.exists():
            return {
                "ok": False,
                "error": {
                    "type": ErrorType.FILE_NOT_FOUND,
                    "msg": f"file not found: {path_str}",
                    "retryable": False,
                },
            }

        stats = path.stat()
        full_size = stats.st_size

        with path.open("rb") as f:
            raw_data = f.read(read_limit)

        # G7: Decode with replace to handle potential mid-char truncation
        data = raw_data.decode("utf-8", errors="replace")

        truncated = len(raw_data) < full_size
        meta = {"size": full_size, "read_bytes": len(raw_data), "truncated": truncated}

        return {"ok": True, "output": data, "meta": meta}

    except ValueError as exc:
        return {
            "ok": False,
            "error": {"type": ErrorType.ARGUMENT_ERROR, "msg": str(exc), "retryable": False},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": {"type": ErrorType.EXECUTION_ERROR, "msg": str(exc), "retryable": False},
        }


def tool_bash(args: Mapping[str, JSONValue], timeout: float | None = None) -> ToolResult:
    try:
        command = _expect_str(args, "command")
        # C3.T4: Structured output
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            env=stable_env(),
            shell=True,
            text=True,
            timeout=timeout,
        )

        output = completed.stdout
        meta = {
            "exitCode": completed.returncode,
            "stderr": completed.stderr,
        }

        if completed.returncode != 0:
            # Default to not retryable unless classified
            return {
                "ok": False,
                "output": output,
                "error": {
                    "type": ErrorType.EXECUTION_ERROR,
                    "msg": f"bash failed rc={completed.returncode}",
                    "retryable": False,
                },
                "meta": meta,
            }

        return {"ok": True, "output": output, "meta": meta}

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": {
                "type": ErrorType.TIMEOUT,
                "msg": f"tool timeout after {timeout}s",
                "retryable": False,
            },
        }
    except ValueError as exc:
        return {
            "ok": False,
            "error": {"type": ErrorType.ARGUMENT_ERROR, "msg": str(exc), "retryable": False},
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": {"type": ErrorType.EXECUTION_ERROR, "msg": str(exc), "retryable": False},
        }


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("echo", tool_echo)
    registry.register("readfile", tool_readfile)
    registry.register("bash", tool_bash)
    return registry
