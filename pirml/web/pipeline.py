from __future__ import annotations

import collections
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pirml.clock import SequenceClock

from .cite import pack_citations
from .etl import fallback_extract, kill_boilerplate, select_top_chunks
from .etl_join import join_chunks
from .etl_score import score_bm25
from .search import rank_and_diversify
from .types import ChunkRow, CiteRow, WebFinal

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
    serp_k: int = 10


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
    ):
        self.provider = provider
        self.fetcher = fetcher
        self.clock = clock
        self.tracer = tracer
        self._global_boilerplate_cache: collections.Counter[str] = collections.Counter()

    async def run(self, query: str, plan: WebPlan) -> WebFinal:
        # 1. Search
        serp = await self.provider.search(query, tracer=self.tracer)

        # 2. Diversify
        selected_serp = rank_and_diversify(
            serp, k=plan.serp_k, per_domain_cap=plan.per_domain_cap, tracer=self.tracer
        )

        # 3. Fetch + ETL
        all_chunks: list[ChunkRow] = []
        for i, row in enumerate(selected_serp):
            try:
                doc = await self.fetcher.fetch(row["url"], tracer=self.tracer)
                if doc["status"] != 200:
                    continue

                # Winner B3b: robust text extraction
                chunks = fallback_extract(
                    doc["body"],
                    url=doc["url"],
                    doc_sha256=doc["body_sha256"],
                    source_rank=row["rank"],
                    doc_rank=i,
                )

                all_chunks.extend(chunks)
            except Exception:
                continue

        # 4. Global ETL
        # C2.T2: Boilerplate kill
        import hashlib
        import re

        for c in all_chunks:
            clean = re.sub(r"\s+", " ", c["text"]).strip().lower()
            if len(clean) >= 20:
                h = hashlib.sha256(clean.encode()).hexdigest()[:16]
                self._global_boilerplate_cache[h] += 1

        filtered_chunks = kill_boilerplate(all_chunks, global_counts=self._global_boilerplate_cache)

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
        # Simple answer generation for now
        answer = " ".join([c["text"] for c in joined_chunks[:3]])

        return project_final(
            answer=answer,
            citations=citations,
            trace_ptr=f"web_trace_{self.clock.now()}.ndjson",
        )


__all__ = ["WebPipeline", "WebPlan", "project_final"]
