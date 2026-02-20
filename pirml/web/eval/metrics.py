from __future__ import annotations

from pirml.web.types import EvalRow


def metric_tuple(row: EvalRow) -> tuple[float, int, int, int, float]:
    return (row["acc"], -row["bytes"], -row["chunks"], -row["fetches"], row["cache_hit"])


__all__ = ["metric_tuple"]
