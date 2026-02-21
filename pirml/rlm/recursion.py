from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .kernel import RlmKernel


async def amap_recursive(kernel: RlmKernel, prompts: list[str]) -> list[str]:
    """C4.T02: Map step uses bounded asyncio.gather; merge order equals source chunk order"""

    async def _limited_query(p: str) -> str:
        async with kernel.parallel_sem:
            return await kernel.llm_query_helper(p)

    tasks = [asyncio.create_task(_limited_query(p)) for p in prompts]
    return list(await asyncio.gather(*tasks))
