#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


def main() -> int:
    for idx, line in enumerate(sys.stdin, start=1):
        raw = line.rstrip("\n")
        if raw == "":
            print(f"blank line at {idx}", file=sys.stderr)
            return 1
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            print(f"non-json line {idx}", file=sys.stderr)
            return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
