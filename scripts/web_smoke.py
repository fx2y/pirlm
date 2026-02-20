import asyncio
from pathlib import Path

from pirml.clock import SequenceClock
from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, RealDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import MockProvider
from pirml.web.trace import WebTracer


async def smoke():
    print("Running live smoke (non-gating)...")
    
    # Use a dummy provider for search to avoid real network search
    # but use RealDocFetcher for one specific URL to test real network fetch
    # (Actually, let's use a known stable URL like google.com or similar)
    provider = MockProvider({
        "ping": [{"url": "https://www.google.com", "title": "Google", "snippet": "Search", "rank": 1, "source": "smoke"}]
    })
    
    cache = SqliteCache(Path(".tmp/smoke_cache.sqlite"))
    fetcher = CachedDocFetcher(RealDocFetcher(), cache)
    clock = SequenceClock.from_env()
    tracer = WebTracer()
    
    pipeline = WebPipeline(provider=provider, fetcher=fetcher, clock=clock, tracer=tracer)
    
    plan = WebPlan(
        provider="mock",
        cache="sqlite",
        parser="html_parser_primary",
        scorer="bm25_chunk",
        cite_mode="quote_anchor"
    )
    
    try:
        final = await pipeline.run("ping", plan)
        print(f"Smoke success: answer={final['answer'][:50]}...")
        print(f"Citations: {len(final['citations'])}")
    except Exception as e:
        print(f"Smoke failed (as expected if offline): {e}")


if __name__ == "__main__":
    asyncio.run(smoke())
