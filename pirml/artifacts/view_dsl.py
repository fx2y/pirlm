from __future__ import annotations

import hashlib
from typing import Any, Literal, NotRequired, TypedDict

from pirml.artifacts.errors import ArtifactErrorType, ArtifactPathError
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


def view_id_for(aid: str, spec: SliceSpec) -> str:
    """C2.T01: view_id = sha256(artifact_id|spec_json)"""
    spec_json = canonical_json(spec)
    content = f"{aid}|{spec_json}".encode()
    return hashlib.sha256(content).hexdigest()


def parse_spec(spec: dict[str, Any]) -> SliceSpec:
    """I06: Validate and typed-fail on invalid slice spec"""
    op = spec.get("op")
    if op not in ("lines", "bytes", "regex", "html_text"):
        raise ArtifactPathError(
            error_type=ArtifactErrorType.VIEW_OP_UNSUPPORTED,
            msg=f"Unknown view op: {op}",
        )

    if op == "lines":
        a, b = spec.get("a"), spec.get("b")
        if not isinstance(a, int) or not isinstance(b, int) or a < 0 or b < a:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.VIEW_SPEC_INVALID,
                msg=f"Invalid span [a, b] for lines: {a}, {b}",
            )
    elif op == "bytes":
        offset, limit = spec.get("offset"), spec.get("limit")
        if not isinstance(offset, int) or not isinstance(limit, int) or offset < 0 or limit < 0:
            raise ArtifactPathError(
                error_type=ArtifactErrorType.VIEW_SPEC_INVALID,
                msg=f"Invalid offset/limit for bytes: {offset}, {limit}",
            )

    return spec  # type: ignore
