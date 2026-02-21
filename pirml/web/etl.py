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
    if not html.strip():
        raise ValueError("html must be non-empty")
    if not url:
        raise ValueError("url must be non-empty")
    if not doc_sha256:
        raise ValueError("doc_sha256 must be non-empty")
    # B3b fallback: strip tags + windowed regex
    # Improved: strip script/style tags AND their contents first
    clean_html = re.sub(
        r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE
    )
    # Strip all other tags
    text = re.sub(r"<[^>]+>", " ", clean_html)
    text = re.sub(r"\s+", " ", text).strip()

    # Split into ~400-800 char windows
    chunks: list[ChunkRow] = []
    chunk_size = 600
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i : i + chunk_size].strip()
        if not chunk_text:
            continue

        chunk_id = f"fb{i // chunk_size:04d}"
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
    if n <= 0:
        raise ValueError("n must be > 0")
    sorted_chunks = stable_chunk_sort(chunks)
    return sorted_chunks[:n]


def chunk_views(view_texts: list[str], max_chars: int = 12000) -> list[str]:
    """C4.T00: Chunker consumes view artifacts and emits deterministic chunk groups"""
    chunks = []
    for text in view_texts:
        # Split by paragraphs or double newlines to keep semantic units if possible
        units = re.split(r"(\n\n+)", text)
        current = []
        current_len = 0
        for unit in units:
            if current_len + len(unit) > max_chars and current:
                chunks.append("".join(current))
                current = []
                current_len = 0
            
            # If a single unit is too large, hard cut
            if len(unit) > max_chars:
                for i in range(0, len(unit), max_chars):
                    chunks.append(unit[i:i+max_chars])
                continue

            current.append(unit)
            current_len += len(unit)
        
        if current:
            chunks.append("".join(current))
            
    return chunks


def pack_batches(chunks: list[str], max_chars: int = 12000) -> list[str]:
    """C4.T01: Batch pack slices into bounded payload windows"""
    batches = []
    current: list[str] = []
    current_len = 0
    for c in chunks:
        if current_len + len(c) > max_chars and current:
            batches.append("\n---\n".join(current))
            current = []
            current_len = 0
        current.append(c)
        current_len += len(c)
    if current:
        batches.append("\n---\n".join(current))
    return batches


__all__ = [
    "clamp_chunk_text",
    "stable_chunk_sort",
    "fallback_extract",
    "kill_boilerplate",
    "select_top_chunks",
    "chunk_views",
    "pack_batches",
]
