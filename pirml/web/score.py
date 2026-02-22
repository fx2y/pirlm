from __future__ import annotations

import re
import unicodedata


def normalize_exact(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    collapsed = re.sub(r"\s+", " ", normalized)
    return collapsed.strip()


def score_exact_match(
    *, expected: str, actual: str, citation_count: int, require_citations: bool
) -> float:
    if require_citations and citation_count <= 0:
        return 0.0
    return 1.0 if normalize_exact(expected) == normalize_exact(actual) else 0.0


__all__ = ["normalize_exact", "score_exact_match"]
