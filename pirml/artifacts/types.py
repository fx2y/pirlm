from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict


class ArtifactKind(StrEnum):
    RAW = "raw"
    FILTERED = "filtered"
    SLICE = "slice"
    SUMMARY = "summary"
    REDUCE = "reduce"
    FINAL = "final"


class ArtifactSource(TypedDict, total=False):
    tool: str
    url: str
    params: dict[str, Any]
    vid: str
    aid: str
    spec: Any
    stats: dict[str, Any]


class ArtifactRecord(TypedDict):
    id: str  # sha256
    kind: str  # ArtifactKind
    mime: str
    bytes: int
    sha256: str
    path: str
    parents: list[str]  # parent_ids
    src: ArtifactSource
    ts: int  # ms
    notes: str | None


class ArtifactMeta(TypedDict):
    id: str
    kind: str
    mime: str
    bytes: int
    sha256: str
    parents: list[str]
    src: ArtifactSource
    ts: int
