from __future__ import annotations

import hashlib
import re

from pirml.web.types import CiteRow, EvalRow


def metric_tuple(row: EvalRow) -> tuple[float, int, int, int, float]:
    return (row["acc"], -row["bytes"], -row["chunks"], -row["fetches"], row["cache_hit"])


def evidence_accuracy(*, query: str, citations: list[CiteRow]) -> float:
    tokens = sorted(set(re.findall(r"\w+", query.lower())))
    if not tokens:
        return 0.0
    evidence = " ".join(c["quote"].lower() for c in citations)
    matched = sum(1 for tok in tokens if tok in evidence)
    coverage = matched / len(tokens)
    # Prefer evidence coverage; tiny deterministic bonus for having multiple citations.
    bonus = min(len(citations), 3) * 0.02
    return round(min(1.0, (0.35 + (0.6 * coverage) + bonus)), 4)


def deterministic_jitter(*, qid: str, seed: int = 0) -> float:
    # Tie-break only; does not replace evidence-derived accuracy.
    digest = hashlib.sha256(f"{seed}:{qid}".encode()).digest()
    return (int.from_bytes(digest[:2], byteorder="big") % 10) / 10000.0


__all__ = ["deterministic_jitter", "evidence_accuracy", "metric_tuple"]
