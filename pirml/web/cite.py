from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pirml.clock import SequenceClock

if TYPE_CHECKING:
    from .types import ChunkRow, CiteRow


def _clip_words(text: str, *, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def find_quote_in_chunk(chunk: ChunkRow, *, query_hints: list[str]) -> str:
    # B5a: quote span search
    # Find the best sentence containing query hints
    text = chunk["text"]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if not sentences:
        return text[:100]

    best_sentence = sentences[0]
    max_matches = -1
    for s in sentences:
        matches = sum(1 for hint in query_hints if hint.lower() in s.lower())
        if matches > max_matches:
            max_matches = matches
            best_sentence = s

    return best_sentence


def build_citation(
    *,
    chunk: ChunkRow,
    quote: str | None = None,
    query_hints: list[str] | None = None,
    clock: SequenceClock,
    max_words: int = 25,
) -> CiteRow:
    # C2.T7: Enforce url+doc_sha+chunk_id linkage
    if quote is None:
        if query_hints:
            quote = find_quote_in_chunk(chunk, query_hints=query_hints)
        else:
            quote = chunk["text"]

    return {
        "url": chunk["url"],
        "doc_sha256": chunk["doc_sha256"],
        "chunk_id": chunk["chunk_id"],
        "quote": _clip_words(quote, max_words=max_words),
        "retrieved_at": clock.now(),
    }


def pack_citations(
    chunks: list[ChunkRow],
    *,
    clock: SequenceClock,
    query: str = "",
) -> list[CiteRow]:
    if not chunks:
        raise ValueError("chunks must be non-empty")
    query_hints = re.findall(r"\w+", query.lower()) if query else []
    results: list[CiteRow] = []
    for chunk in chunks:
        # B5a: Winner quote_anchor only
        quote = find_quote_in_chunk(chunk, query_hints=query_hints)
        results.append(
            build_citation(
                chunk=chunk,
                quote=quote,
                clock=clock,
            )
        )
    return results


__all__ = ["build_citation", "find_quote_in_chunk", "pack_citations"]
