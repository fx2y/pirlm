from __future__ import annotations

from typing import NotRequired, TypedDict


class SerpRow(TypedDict):
    url: str
    title: str
    snippet: str
    rank: int
    source: str


class DocRow(TypedDict):
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    content_type: str
    bytes: int
    encoding_guess: str
    body: str
    body_sha256: str


class ChunkRow(TypedDict):
    doc_sha256: str
    url: str
    chunk_id: str
    kind: str
    path_hint: str
    text: str
    score: float
    source_rank: int
    doc_rank: int


class CiteRow(TypedDict):
    url: str
    doc_sha256: str
    chunk_id: str
    quote: str
    retrieved_at: int


class WebFinal(TypedDict):
    answer: str
    citations: list[CiteRow]
    trace_ptr: str


class EvalRow(TypedDict):
    qid: str
    plan: str
    acc: float
    fetches: int
    bytes: int
    chunks: int
    cache_hit: float
    note: NotRequired[str]


__all__ = ["ChunkRow", "CiteRow", "DocRow", "EvalRow", "SerpRow", "WebFinal"]
