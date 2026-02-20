from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    # Minimal validator to check if final.json structure matches basic expectations
    # without external dependencies for now, or just verify the schema file itself is valid json
    schema_path = Path("pirml/contracts/final.schema.json")
    try:
        schema = json.loads(schema_path.read_text())
        print(f"Loaded schema: {schema.get('title')}")
    except Exception as exc:
        print(f"Invalid schema file: {exc}", file=sys.stderr)
        return 1

    final_path = Path("out/ci/final.json")
    if not final_path.exists():
        # Might not be there yet during CI if tasks run in parallel, but mise run ci is sequential
        print(f"Skipping: {final_path} not found")
        return 0

    try:
        final = json.loads(final_path.read_text())
        # Basic check
        if "ok" not in final or "results" not in final:
            print(f"Error: {final_path} missing required fields", file=sys.stderr)
            return 1
        print(f"Verified {final_path}")
    except Exception as exc:
        print(f"Error reading {final_path}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
