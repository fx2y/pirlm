from __future__ import annotations

import collections
import math
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirml.web.types import ChunkRow


def score_bm25(chunks: list[ChunkRow], *, query: str) -> list[ChunkRow]:
    # B4b scorer: BM25 over chunks
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


__all__ = ["score_bm25"]
