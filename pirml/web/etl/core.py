from __future__ import annotations

from pirml.web.types import ChunkRow


def clamp_chunk_text(text: str, *, max_chars: int = 800) -> str:
    return text[:max_chars]


def stable_chunk_sort(chunks: list[ChunkRow]) -> list[ChunkRow]:
    return sorted(
        chunks,
        key=lambda row: (-row["score"], row["source_rank"], row["doc_rank"], row["chunk_id"]),
    )


__all__ = ["clamp_chunk_text", "stable_chunk_sort"]
