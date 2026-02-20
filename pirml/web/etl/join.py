from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pirml.web.types import ChunkRow


def normalize_text_for_dedup(text: str) -> str:
    # Remove whitespace, lowercase, and punctuation for robust dedup
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[^\w]", "", text)
    return text


def join_chunks(chunks: list[ChunkRow]) -> list[ChunkRow]:
    # C2.T6: Dedup by normalized chunk sha
    seen_hashes: dict[str, ChunkRow] = {}
    for chunk in chunks:
        norm = normalize_text_for_dedup(chunk["text"])
        if not norm:
            continue
        h = hashlib.sha256(norm.encode()).hexdigest()
        if h not in seen_hashes:
            seen_hashes[h] = chunk
        else:
            # Keep the one with higher score or earlier occurrence
            existing = seen_hashes[h]
            if chunk["score"] > existing["score"]:
                seen_hashes[h] = chunk

    return list(seen_hashes.values())


def extract_facts(chunk: ChunkRow) -> list[dict[str, str]]:
    # Build fact table rows (entity, date, number, src_chunk)
    # This is a placeholder for more advanced extraction if needed
    facts: list[dict[str, str]] = []
    text = chunk["text"]

    # Simple regex for dates
    dates = re.findall(
        r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
        text,
    )
    for d in dates:
        facts.append({"type": "date", "value": d, "chunk_id": chunk["chunk_id"]})

    # Simple regex for numbers with units
    numbers = re.findall(r"\b\d+(?:\.\d+)?\s*(?:kg|km|m|%|USD|\$|points)\b", text)
    for n in numbers:
        facts.append({"type": "number", "value": n, "chunk_id": chunk["chunk_id"]})

    return facts


__all__ = ["extract_facts", "join_chunks"]
