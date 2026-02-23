
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


# Original program source
import asyncio
from pirml.runtime.rpc import send_final

async def main() -> None:
    send_final(True, {"ok": True, "results": []})


if __name__ == "__main__":
    asyncio.run(main())
