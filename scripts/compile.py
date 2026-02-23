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
    parser.add_argument("--smoke", action="store_true", help="Run smoke test (Cycle C3+)")
    parser.add_argument(
        "--input-file", type=Path, help="Read model response from file (sets PIRML_MODEL_FILE)"
    )

    args = parser.parse_args()

    # 0. Handle input file injection
    if args.input_file:
        import os

        os.environ["PIRML_MODEL_FILE"] = str(args.input_file)

    # 1. Orchestrate compilation
    out: CompileOutput = compile_task(
        task=args.task,
        tools_dir=args.tools_dir,
        out_dir=args.out_dir,
        query=args.query,
        k=args.top_k,
        skip_smoke=not args.smoke,
    )

    # 2. Handle exit codes
    if out.get("ok"):
        # Print summary as per C1.T7 AC
        print(f"Compilation successful: {args.out_dir}", file=sys.stderr)
        return 0

    # Business or Integrity failure
    err_obj = out.get("error", {})
    err_type = "unknown"
    err_msg = "Unknown error"
    errors_list: list[dict[str, Any]] = []

    if "errors" in err_obj:
        # CompileErrorFile (Unified shape)
        errors_list = cast(list[dict[str, Any]], err_obj.get("errors", []))
        stage = err_obj.get("stage", "unknown")

        err_type = "internal_error" if stage == "internal" else f"{stage}_fail"

        if errors_list:
            # Prefer the first error's code/msg for the summary line
            first_err = errors_list[0]
            err_msg = cast(str, first_err.get("msg", "Unknown error"))
            if stage != "internal":
                err_type = cast(str, first_err.get("code", f"{stage}_fail"))

    # Print smoke stderr if available
    if err_obj.get("stage") == "smoke":
        smoke_stderr = err_obj.get("stderr")
        if smoke_stderr:
            print("\nSmoke Stderr:", file=sys.stderr)
            print(smoke_stderr, file=sys.stderr)

    print(
        f"Compilation failed [{err_type}]: {err_msg}",
        file=sys.stderr,
    )

    # DX.P1.02: Print all errors with detail
    if len(errors_list) > 1:
        print("\nAll errors:", file=sys.stderr)
        for i, e in enumerate(errors_list, 1):
            code = e.get("code", "unknown")
            msg = e.get("msg", "Unknown error")
            line = e.get("line")
            sym = e.get("symbol")
            loc = f" (line {line})" if line else ""
            if sym:
                loc += f" [sym: {sym}]"
            print(f"  {i}. [{code}]{loc} {msg}", file=sys.stderr)

    # RC2 for integrity/internal faults
    if err_type == "internal_error":
        return 2

    return 1


if __name__ == "__main__":
    sys.exit(main())
