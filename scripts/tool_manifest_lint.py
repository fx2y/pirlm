from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pirml.runtime.lint import lint_catalog
from pirml.runtime.load import load_catalog


def main() -> int:
    """C1.T4: CLI for manifest linting with deterministic exit codes.
    0 = pass
    1 = manifest business failure (lint errors)
    2 = config/io/integrity failure
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-dir", default="tools")
    args = parser.parse_args()

    tools_dir = Path(args.tools_dir)
    if not tools_dir.exists():
        # Directory might not exist yet in early stages; if so, nothing to lint but technically not a 'pass' if we expected tools
        print(f"Error: tools directory not found: {tools_dir}", file=sys.stderr)
        return 2

    try:
        catalog = load_catalog(tools_dir)
        if not catalog:
            # Empty catalog is a failure in this context
            print(f"Error: no manifests found in {tools_dir}", file=sys.stderr)
            return 1

        errors = lint_catalog(catalog)
    except Exception as exc:
        print(f"Integrity failure: {exc}", file=sys.stderr)
        return 2

    if errors:
        print(f"Manifest lint failed for {tools_dir}:", file=sys.stderr)
        for err in errors:
            print(f"  [{err['code']}] {err['path']}: {err['msg']}", file=sys.stderr)
        return 1

    print(f"Verified {len(catalog)} manifests in {tools_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
