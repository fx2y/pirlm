import asyncio
from pathlib import Path

from pirml.clock import SequenceClock
from pirml.web.cache.sqlite import SqliteCache
from pirml.web.fetch import CachedDocFetcher, RealDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import MockProvider
from pirml.web.trace import WebTracer
from pirml.web.types import CiteRow


def _snippet(text: str, *, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)] + "..."


def _print_citation_summary(citations: list[CiteRow]) -> None:
    if not citations:
        print("Citations: 0")
        return
    print(f"Citations: {len(citations)}")
    for idx, cite in enumerate(citations, start=1):
        url = str(cite.get("url", ""))
        chunk_id = str(cite.get("chunk_id", ""))
        quote = _snippet(str(cite.get("quote", "")), limit=120)
        print(f"  {idx}. {url} [{chunk_id}] {quote}")


async def smoke():
    print("Running live smoke (non-gating)...")

    # Use a dummy provider for search to avoid real network search
    # but use RealDocFetcher for one specific URL to test real network fetch
    # (Actually, let's use a known stable URL like google.com or similar)
    provider = MockProvider(
        {
            "ping": [
                {
                    "url": "https://www.google.com",
                    "title": "Google",
                    "snippet": "Search",
                    "rank": 1,
                    "source": "smoke",
                }
            ]
        }
    )

    cache = SqliteCache(Path(".tmp/smoke_cache.sqlite"))
    fetcher = CachedDocFetcher(RealDocFetcher(), cache)
    clock = SequenceClock.from_env()
    tracer = WebTracer()

    pipeline = WebPipeline(provider=provider, fetcher=fetcher, clock=clock, tracer=tracer)

    plan = WebPlan(
        provider="mock",
        cache="sqlite",
    )

    try:
        final = await pipeline.run("ping", plan)
        print(f"Smoke success: answer={_snippet(str(final['answer']), limit=160)}")
        _print_citation_summary(final["citations"])
    except Exception as e:
        print(f"Smoke failed (as expected if offline): {e}")


if __name__ == "__main__":
    asyncio.run(smoke())
