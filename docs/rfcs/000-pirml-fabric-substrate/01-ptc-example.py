# Example: PTC Miniprogram for Entangled Search
# emitted by PiRLM Compiler

import asyncio

from pirml.runtime import call_tool, get_args


async def main():
    args = get_args()  # noqa: F841 # Query: "Compare Q4 revenue of Apple and Microsoft"

    # 1. High-fanout parallel search
    # This avoids 2 roundtrips to the LLM.
    search_tasks = [
        call_tool("web.search", q="Apple Q4 2025 revenue investor relations"),
        call_tool("web.search", q="Microsoft Q4 2025 revenue investor relations"),
    ]
    search_results = await asyncio.gather(*search_tasks)

    # 2. Dynamic Filtering (ETL)
    # The model defines the extraction logic in Python.
    # No need to send raw HTML back to LLM.
    extracted_data = []
    for res in search_results:
        html = await call_tool("web.fetch", url=res["top_url"])
        # Dynamic ETL: filter for tables or regex
        revenue = parse_revenue_from_html(html)
        extracted_data.append({"source": res["top_url"], "revenue": revenue})

    # 3. Final distill
    # Only this small JSON enters the LLM final-pass context.
    return {"comparison": extracted_data, "status": "success"}


def parse_revenue_from_html(html: str) -> str:
    # Minimal extraction logic pushdown
    if "Revenue" in html:
        return "Found"  # Real implementation would use regex/html.parser
    return "Not found"


if __name__ == "__main__":
    asyncio.run(main())
