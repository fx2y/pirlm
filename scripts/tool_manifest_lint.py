from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args
from pirml.runtime.lint import LintFailure, lint_tools_dir


def main() -> int:
    """C1.T4: CLI for manifest linting with deterministic exit codes.
    0 = pass
    1 = manifest business failure (lint errors)
    2 = config/io/integrity failure
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools-dir", default="tools")
    try:
        args = strict_parse_args(parser)
    except CliFailure as err:
        return emit_failure(err)

    tools_dir = Path(args.tools_dir)

    try:
        catalog, errors = lint_tools_dir(tools_dir)
    except LintFailure as err:
        return emit_failure(CliFailure(err.err_type, err.msg, err.code, err.retryable))

    if errors:
        print(
            json.dumps(
                {
                    "type": "validation",
                    "msg": f"manifest lint failed: {len(errors)} error(s) in {tools_dir}",
                    "retryable": False,
                }
            ),
            file=sys.stderr,
        )
        return 1

    print(f"Verified {len(catalog)} manifests in {tools_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
