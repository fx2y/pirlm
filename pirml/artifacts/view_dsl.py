from __future__ import annotations

import hashlib
from typing import Any, Literal, NotRequired, TypedDict

from pirml.runtime.rpc import canonical_json


class ViewOpSpec(TypedDict):
    op: Literal["score", "join", "dedup", "sort", "limit"]
    params: dict[str, Any]


class SliceLines(TypedDict):
    op: Literal["lines"]
    a: int
    b: int
    post: NotRequired[list[ViewOpSpec]]


class SliceBytes(TypedDict):
    op: Literal["bytes"]
    offset: int
    limit: int
    post: NotRequired[list[ViewOpSpec]]


class SliceRegex(TypedDict):
    op: Literal["regex"]
    pat: str
    max_hits: NotRequired[int]
    post: NotRequired[list[ViewOpSpec]]


class SliceHtmlText(TypedDict):
    op: Literal["html_text"]
    post: NotRequired[list[ViewOpSpec]]


SliceSpec = SliceLines | SliceBytes | SliceRegex | SliceHtmlText


class ViewSpec(TypedDict):
    aid: str
    spec: SliceSpec


def derive_view_id(aid: str, spec: SliceSpec) -> str:
    """C2.T01: view_id = sha256(artifact_id|spec_json)"""
    spec_json = canonical_json(spec)
    content = f"{aid}|{spec_json}".encode()
    return hashlib.sha256(content).hexdigest()
