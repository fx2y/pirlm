from __future__ import annotations

import collections
import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirml.web.types import ChunkRow


def score_query_overlap(chunk: ChunkRow, *, query: str) -> float:
    # B4a scorer: Query token overlap + answer-shape regex
    text = chunk["text"].lower()
    query = query.lower()

    # Query overlap
    query_tokens = set(re.findall(r"\w+", query))
    if not query_tokens:
        return 0.0

    chunk_tokens = re.findall(r"\w+", text)
    overlap_count = sum(1 for t in chunk_tokens if t in query_tokens)
    overlap_score = overlap_count / len(query_tokens)

    # Answer-shape regex: years, numbers, definitions
    shape_score = 0.0
    if re.search(r"\b\d{4}\b", text):  # Year-like
        shape_score += 0.2
    if re.search(r"\d+[\.\,]\d+", text):  # Float-like
        shape_score += 0.2
    if re.search(r"\b(defined as|is a|means|referred to as)\b", text):  # Def-like
        shape_score += 0.3

    return overlap_score + shape_score


def score_bm25(chunks: list[ChunkRow], *, query: str) -> list[ChunkRow]:
    # B4b scorer: BM25 over chunks
    # Simplified BM25 if not reusing index.py
    # But let's check index.py first
    query_tokens = re.findall(r"\w+", query.lower())
    if not query_tokens or not chunks:
        return chunks

    doc_count = len(chunks)
    df: collections.Counter[str] = collections.Counter()
    for chunk in chunks:
        tokens = set(re.findall(r"\w+", chunk["text"].lower()))
        for t in tokens:
            df[t] += 1

    avg_dl = sum(len(re.findall(r"\w+", c["text"])) for c in chunks) / doc_count

    k1 = 1.2
    b = 0.75

    for chunk in chunks:
        tokens = re.findall(r"\w+", chunk["text"].lower())
        tf = collections.Counter(tokens)
        dl = len(tokens)

        score = 0.0
        for t in query_tokens:
            if t not in df:
                continue
            # IDF
            idf = math.log((doc_count - df[t] + 0.5) / (df[t] + 0.5) + 1.0)
            # BM25 TF
            tf_norm = (tf[t] * (k1 + 1)) / (tf[t] + k1 * (1 - b + b * (dl / avg_dl)))
            score += idf * tf_norm

        chunk["score"] = score

    return chunks


__all__ = ["score_bm25", "score_query_overlap"]
