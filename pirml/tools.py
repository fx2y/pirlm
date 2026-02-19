from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from .protocol import JSONValue

ToolFn = Callable[[Mapping[str, JSONValue]], JSONValue]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def execute(self, name: str, args: Mapping[str, JSONValue]) -> JSONValue:
        if os.environ.get("PIRML_BLOCK_TOOLS") == "1":
            raise RuntimeError("tool execution blocked by PIRML_BLOCK_TOOLS")
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name](args)


def _expect_str(args: Mapping[str, JSONValue], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _stable_env() -> dict[str, str]:
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


def tool_echo(args: Mapping[str, JSONValue]) -> JSONValue:
    return _expect_str(args, "text")


def tool_readfile(args: Mapping[str, JSONValue]) -> JSONValue:
    path = Path(_expect_str(args, "path"))
    return path.read_text(encoding="utf-8")


def tool_bash(args: Mapping[str, JSONValue]) -> JSONValue:
    command = _expect_str(args, "command")
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=_stable_env(),
        shell=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"bash failed rc={completed.returncode}: {stderr}")
    return completed.stdout


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("echo", tool_echo)
    registry.register("readfile", tool_readfile)
    registry.register("bash", tool_bash)
    return registry
