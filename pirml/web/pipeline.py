from __future__ import annotations

from dataclasses import dataclass

from .types import CiteRow, WebFinal


@dataclass(frozen=True)
class WebPlan:
    provider: str
    cache: str
    parser: str
    scorer: str
    cite_mode: str


def project_final(*, answer: str, citations: list[CiteRow], trace_ptr: str) -> WebFinal:
    return {"answer": answer, "citations": citations, "trace_ptr": trace_ptr}


__all__ = ["WebPlan", "project_final"]
