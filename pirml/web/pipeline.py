from __future__ import annotations

import asyncio
import collections
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pirml.clock import SequenceClock

from .cite import pack_citations
from .etl import fallback_extract, kill_boilerplate, select_top_chunks
from .etl_join import join_chunks
from .etl_score import score_bm25
from .search import rank_and_diversify
from .types import ChunkRow, CiteRow, SerpRow, WebFinal

if TYPE_CHECKING:
    from .fetch import Fetcher
    from .search import Provider
    from .trace import WebTracer


@dataclass(frozen=True)
class WebPlan:
    provider: str
    cache: str
    max_chunks: int = 40
    per_domain_cap: int = 2
    serp_k: int = 8
    max_parallel_fetch: int = 4


def project_final(*, answer: str, citations: list[CiteRow], trace_ptr: str) -> WebFinal:
    return {"answer": answer, "citations": citations, "trace_ptr": trace_ptr}


class WebPipeline:
    def __init__(
        self,
        *,
        provider: Provider,
        fetcher: Fetcher,
        clock: SequenceClock,
        tracer: WebTracer | None = None,
        trace_dir: Path = Path("out"),
    ):
        self.provider = provider
        self.fetcher = fetcher
        self.clock = clock
        self.tracer = tracer
        self.trace_dir = trace_dir

    async def run(self, query: str, plan: WebPlan, trace_filename: str | None = None) -> WebFinal:
        # 1. Search
        serp = await self.provider.search(query, tracer=self.tracer)

        # 2. Diversify
        selected_serp = rank_and_diversify(
            serp, k=min(plan.serp_k, 8), per_domain_cap=plan.per_domain_cap, tracer=self.tracer
        )

        # Common trace pointer generation for T02
        if trace_filename is None:
            trace_filename = f"web_trace_{self.clock.now()}.ndjson"
        trace_ptr = str(self.trace_dir / trace_filename)

        if not selected_serp:
            # T04: empty SERP
            if self.tracer is not None:
                self.tracer.write_to(Path(trace_ptr))
            return project_final(
                answer="No search results found.",
                citations=[],
                trace_ptr=trace_ptr,
            )

        # 3. Fetch + ETL (bounded parallel fanout; stable merge order)
        semaphore = asyncio.Semaphore(max(plan.max_parallel_fetch, 1))

        async def _fetch_extract(i: int, row: SerpRow) -> list[ChunkRow]:
            row_url = row["url"]
            try:
                async with semaphore:
                    doc = await self.fetcher.fetch(row_url, tracer=self.tracer)
                if doc["status"] != 200:
                    return []
                # Winner B3b: robust text extraction
                return fallback_extract(
                    doc["body"],
                    url=doc["url"],
                    doc_sha256=doc["body_sha256"],
                    source_rank=row["rank"],
                    doc_rank=i,
                )
            except Exception as exc:
                if self.tracer is not None:
                    self.tracer.emit(
                        "fetch_result",
                        url=row_url,
                        status=0,
                        error=str(exc),
                        cache_hit=False,
                    )
                return []

        tasks = [_fetch_extract(i, row) for i, row in enumerate(selected_serp)]
        batches = await asyncio.gather(*tasks)
        all_chunks = [chunk for batch in batches for chunk in batch]

        if not all_chunks:
            # T04: empty extracts
            if self.tracer is not None:
                self.tracer.write_to(Path(trace_ptr))
            return project_final(
                answer="No relevant content could be extracted from search results.",
                citations=[],
                trace_ptr=trace_ptr,
            )

        # 4. Global ETL
        # C2.T2: Boilerplate kill
        global_boilerplate_cache: collections.Counter[str] = collections.Counter()
        for c in all_chunks:
            clean = re.sub(r"\s+", " ", c["text"]).strip().lower()
            if len(clean) >= 20:
                h = hashlib.sha256(clean.encode()).hexdigest()[:16]
                global_boilerplate_cache[h] += 1

        filtered_chunks = kill_boilerplate(all_chunks, global_counts=global_boilerplate_cache)

        # Winner B4b: BM25 scoring
        filtered_chunks = score_bm25(filtered_chunks, query=query)

        # C2.T5: Global selector
        top_chunks = select_top_chunks(filtered_chunks, n=plan.max_chunks)

        # 5. Join
        # C2.T6: Dedup
        joined_chunks = join_chunks(top_chunks)

        # 6. Cite
        # C2.T7: Pack citations
        citations = pack_citations(joined_chunks, clock=self.clock, query=query)

        # 7. Project final
        # T05: Concise answer generator
        answer_parts: list[str] = []
        for c in joined_chunks[:3]:
            sent = re.split(r"(?<=[.!?])\s+", c["text"])[0]
            if sent not in answer_parts:
                answer_parts.append(sent)
        answer = " ".join(answer_parts) if answer_parts else "No relevant information found."

        if self.tracer is not None:
            self.tracer.write_to(Path(trace_ptr))
        return project_final(
            answer=answer,
            citations=citations,
            trace_ptr=trace_ptr,
        )


__all__ = ["WebPipeline", "WebPlan", "project_final"]
