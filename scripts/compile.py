from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

from pirml.compiler.compile import compile_task
from pirml.compiler.types import CompileOutput


def main() -> int:
    parser = argparse.ArgumentParser(description="PIRML Compiler CLI (Cycle C1)")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument(
        "--tools-dir", required=True, type=Path, help="Directory containing tool manifests"
    )
    parser.add_argument("--query", help="Search query for tool discovery (defaults to task)")
    parser.add_argument("--top-k", type=int, default=5, help="Number of tools to select")
    parser.add_argument(
        "--out-dir", required=True, type=Path, help="Output directory for artifacts"
    )
    parser.add_argument("--model", help="Model name (optional for now)")
    parser.add_argument("--smoke", action="store_true", help="Run smoke test (Cycle C3+)")

    args = parser.parse_args()

    # 1. Orchestrate compilation
    out: CompileOutput = compile_task(
        task=args.task,
        tools_dir=args.tools_dir,
        out_dir=args.out_dir,
        query=args.query,
        k=args.top_k,
        model=args.model,
    )

    # 2. Handle exit codes
    if out.get("ok"):
        # Print summary as per C1.T7 AC
        print(f"Compilation successful: {args.out_dir}", file=sys.stderr)
        return 0
    else:
        # Business failure
        err_obj = out.get("error", {})
        # err_obj can be CompileErr or CompileErrorFile
        err_msg = "Unknown error"
        if err_obj:
            # ErrorObject has 'msg', CompileErrorFile might have 'errors'
            if "msg" in err_obj:
                err_msg = str(err_obj.get("msg"))
            elif "errors" in err_obj:
                # Need to cast or use get safely
                errors_list = cast(dict[str, Any], err_obj).get("errors", [])
                err_msg = f"Verification failed with {len(errors_list)} errors"

        print(
            f"Compilation failed: {err_msg}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
