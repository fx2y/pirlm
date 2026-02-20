from __future__ import annotations

from pirml.clock import SequenceClock

from .types import CiteRow


def _clip_words(text: str, *, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max_words])


def build_citation(
    *,
    url: str,
    doc_sha256: str,
    chunk_id: str,
    quote: str,
    clock: SequenceClock,
    max_words: int = 25,
) -> CiteRow:
    return {
        "url": url,
        "doc_sha256": doc_sha256,
        "chunk_id": chunk_id,
        "quote": _clip_words(quote, max_words=max_words),
        "retrieved_at": clock.now(),
    }


def pack_citations(
    claims: list[tuple[str, str, str, str]], *, clock: SequenceClock
) -> list[CiteRow]:
    return [
        build_citation(
            url=url,
            doc_sha256=doc_sha256,
            chunk_id=chunk_id,
            quote=quote,
            clock=clock,
        )
        for url, doc_sha256, chunk_id, quote in claims
    ]


__all__ = ["build_citation", "pack_citations"]
