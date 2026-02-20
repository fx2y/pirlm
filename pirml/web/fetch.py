from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

from .types import DocRow
from .urlnorm import normalize_url


class Fetcher(Protocol):
    def fetch(self, url: str) -> DocRow: ...


class FixtureRow(TypedDict):
    url: str
    final_url: str
    status: int
    headers: dict[str, str]
    content_type: str
    encoding_guess: str
    body_file: str


@dataclass(frozen=True)
class _FixturePayload:
    row: FixtureRow
    body: bytes


def _decode_body(body: bytes, encoding_guess: str) -> str:
    candidates = [encoding_guess, "utf-8", "cp1252", "latin-1"]
    for candidate in candidates:
        try:
            return body.decode(candidate)
        except UnicodeDecodeError:
            continue
    return body.decode("latin-1", errors="replace")


def _load_fixture_manifest(path: Path) -> list[FixtureRow]:
    payload_raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, dict):
        raise ValueError("fixture manifest must be an object")
    payload = cast(dict[str, Any], payload_raw)
    rows_candidate = payload.get("responses")
    if not isinstance(rows_candidate, list):
        raise ValueError("fixture manifest missing list field: responses")
    rows_raw = cast(list[Any], rows_candidate)
    rows: list[FixtureRow] = []
    for item in rows_raw:
        if not isinstance(item, dict):
            raise ValueError("fixture response must be an object")
        row_map = cast(dict[str, Any], item)
        row: FixtureRow = {
            "url": cast(str, row_map["url"]),
            "final_url": cast(str, row_map["final_url"]),
            "status": cast(int, row_map["status"]),
            "headers": cast(dict[str, str], row_map["headers"]),
            "content_type": cast(str, row_map["content_type"]),
            "encoding_guess": cast(str, row_map["encoding_guess"]),
            "body_file": cast(str, row_map["body_file"]),
        }
        rows.append(row)
    return rows


class FixtureDocFetcher:
    """Deterministic fetch substrate for offline unit tests."""

    def __init__(self, fixtures_path: Path) -> None:
        base = fixtures_path.parent
        records: dict[str, _FixturePayload] = {}
        for row in _load_fixture_manifest(fixtures_path):
            body_path = base / row["body_file"]
            body = body_path.read_bytes()
            records[normalize_url(row["url"])] = _FixturePayload(row=row, body=body)
        self._records = records

    def fetch(self, url: str) -> DocRow:
        key = normalize_url(url)
        if key not in self._records:
            raise KeyError(f"fixture not found for normalized url: {key}")
        payload = self._records[key]
        body_sha256 = hashlib.sha256(payload.body).hexdigest()
        body_text = _decode_body(payload.body, payload.row["encoding_guess"])
        return {
            "url": key,
            "final_url": normalize_url(payload.row["final_url"]),
            "status": payload.row["status"],
            "headers": dict(payload.row["headers"]),
            "content_type": payload.row["content_type"],
            "bytes": len(payload.body),
            "encoding_guess": payload.row["encoding_guess"],
            "body": body_text,
            "body_sha256": body_sha256,
        }


def load_fixture_fetcher(path: Path) -> FixtureDocFetcher:
    return FixtureDocFetcher(fixtures_path=path)


__all__ = ["Fetcher", "FixtureDocFetcher", "FixtureRow", "load_fixture_fetcher"]
