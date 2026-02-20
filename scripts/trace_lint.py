#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pirml.protocol import (
    MAX_LINE_BYTES_DEFAULT,
    ProtocolError,
    load_jsonl,
    validate_strict_trace,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", default="out/trace.ndjson")
    parser.add_argument("--max-line-bytes", type=int, default=MAX_LINE_BYTES_DEFAULT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        frames = load_jsonl(Path(args.trace))
        validate_strict_trace(frames, max_line_bytes=int(args.max_line_bytes))
    except (OSError, ProtocolError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
