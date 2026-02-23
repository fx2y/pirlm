from __future__ import annotations

from pirml.compiler.types import CompileContract


def assemble_prog(prog_src: str, contract: CompileContract) -> str:
    """C1.T7: Assemble the final prog.py with TOOL_* wrappers for runtime."""
    tool_deps = contract.get("tool_deps", [])

    wrappers: list[str] = []
    for tool in tool_deps:
        safe_name = tool.replace(".", "_")
        # Core tool mapping: pirml.echo -> echo
        runtime_name = tool
        if tool.startswith("pirml."):
            short = tool.split(".")[-1]
            if short in ("echo", "readfile", "bash"):
                runtime_name = short

        wrappers.append(f"""
async def TOOL_{safe_name}(args):
    return await _PIRML_RUNTIME.call("{runtime_name}", args)
""")
        if "." not in tool:
            wrappers.append(f"""
async def TOOL_{tool}(args):
    return await _PIRML_RUNTIME.call("{runtime_name}", args)
""")

    # We use a lazy-initialized global AsyncRpcClient
    harness = f"""
import asyncio as _p_asyncio
from typing import Any, Mapping as _p_Mapping
from pirml.runtime.rpc import AsyncRpcClient as _p_AsyncRpcClient

class _PIRMLRuntime:
    def __init__(self):
        self.client: _p_AsyncRpcClient | None = None
        self._lock = _p_asyncio.Lock()

    async def call(self, tool: str, args: _p_Mapping[str, Any]):
        async with self._lock:
            if self.client is None:
                self.client = _p_AsyncRpcClient()
                await self.client.start()
        return await self.client.call(tool, args)

    async def stop(self):
        if self.client:
            await self.client.stop()

_PIRML_RUNTIME = _PIRMLRuntime()

# Inject TOOL_* wrappers
{"".join(wrappers)}

# Original program source
{prog_src}
"""
    return harness
