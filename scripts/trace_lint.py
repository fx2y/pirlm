#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from pirml.protocol import (
    MAX_LINE_BYTES_DEFAULT,
    ProtocolError,
    canonical_json,
    load_jsonl,
    validate_trace,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_int(frame: dict[str, object], key: str, line: int) -> int:
    value = frame.get(key)
    if not isinstance(value, int):
        raise ProtocolError(f"line {line}: {key} must be int")
    return value


def _require_hash(frame: dict[str, object], key: str, line: int) -> None:
    value = frame.get(key)
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ProtocolError(f"line {line}: {key} must be lowercase sha256 hex")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default="out/trace.ndjson")
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES_DEFAULT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        frames = load_jsonl(Path(args.trace))
        limit = int(args.max_line_bytes)
        validate_trace(frames, max_line_bytes=limit)
        expected_seq = 1
        for idx, frame in enumerate(frames, start=1):
            line = canonical_json(frame)
            if len(line.encode("utf-8")) > limit:
                raise ProtocolError(f"line {idx} exceeds max_line_bytes={limit}")
            seq = _require_int(frame, "seq", idx)
            if seq != expected_seq:
                raise ProtocolError(f"line {idx}: seq must be {expected_seq}, got {seq}")
            expected_seq += 1

            direction = frame.get("dir")
            if direction not in {"in", "out"}:
                raise ProtocolError(f"line {idx}: dir must be 'in' or 'out'")

            ms = _require_int(frame, "ms", idx)
            if ms < 0:
                raise ProtocolError(f"line {idx}: ms must be >= 0")
            _require_int(frame, "ts", idx)

            op = frame.get("op")
            if op == "call":
                _require_hash(frame, "sha256_args", idx)
            elif op in {"result", "final"}:
                _require_hash(frame, "sha256_output", idx)
    except (OSError, ProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
