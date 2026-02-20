from __future__ import annotations

import collections
import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirml.web.types import ChunkRow


def clamp_chunk_text(text: str, *, max_chars: int = 800) -> str:
    return text[:max_chars]


def stable_chunk_sort(chunks: list[ChunkRow]) -> list[ChunkRow]:
    return sorted(
        chunks,
        key=lambda row: (-row["score"], row["source_rank"], row["doc_rank"], row["chunk_id"]),
    )


def fallback_extract(
    html: str, *, url: str, doc_sha256: str, source_rank: int, doc_rank: int
) -> list[ChunkRow]:
    # B3b fallback: strip tags + windowed regex
    # Simplified: regex-based sentence/paragraph extraction
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    # Split into ~400-800 char windows
    chunks: list[ChunkRow] = []
    chunk_size = 600
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size].strip()
        if not chunk_text:
            continue

        chunk_id = f"fb{i//chunk_size:04d}"
        chunks.append(
            {
                "url": url,
                "doc_sha256": doc_sha256,
                "chunk_id": chunk_id,
                "kind": "fallback",
                "path_hint": "fallback",
                "text": chunk_text,
                "score": 0.0,
                "source_rank": source_rank,
                "doc_rank": doc_rank,
            }
        )
    return chunks


def kill_boilerplate(
    chunks: list[ChunkRow], *, global_counts: collections.Counter[str], threshold: int = 3
) -> list[ChunkRow]:
    # C2.T2: Boilerplate kill
    # Repeated chunk-hash across docs
    filtered: list[ChunkRow] = []
    for chunk in chunks:
        # Canonical text for hashing
        clean_text = re.sub(r"\s+", " ", chunk["text"]).strip().lower()
        if not clean_text or len(clean_text) < 20:
            continue

        h = hashlib.sha256(clean_text.encode()).hexdigest()[:16]
        if global_counts[h] >= threshold:
            continue

        # Link density kill (simplified: ignore navigation-like chunks)
        if chunk["kind"] in ("nav", "header", "footer"):
            continue

        filtered.append(chunk)

    return filtered


def select_top_chunks(chunks: list[ChunkRow], *, n: int = 40) -> list[ChunkRow]:
    # C2.T5: Global selector
    sorted_chunks = stable_chunk_sort(chunks)
    return sorted_chunks[:n]


__all__ = [
    "clamp_chunk_text",
    "stable_chunk_sort",
    "fallback_extract",
    "kill_boilerplate",
    "select_top_chunks",
]
