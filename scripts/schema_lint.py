from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast


def validate_error(error: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(error, dict):
        return [f"{path} must be an object"]

    # Required
    if "type" not in error:
        errors.append(f"{path} missing required 'type'")
    if "msg" not in error:
        errors.append(f"{path} missing required 'msg'")

    # Additional properties check (G17)
    allowed = {"type", "msg", "retryable"}
    for k in cast(Mapping[str, Any], error):
        if k not in allowed:
            errors.append(f"{path} has unexpected field '{k}'")

    if "type" in error and not isinstance(error["type"], str):
        errors.append(f"{path}.type must be a string")
    if "msg" in error and not isinstance(error["msg"], str):
        errors.append(f"{path}.msg must be a string")
    if "retryable" in error and not isinstance(error["retryable"], bool):
        errors.append(f"{path}.retryable must be a boolean")

    return errors


def validate_result(result: Any, index: int) -> list[str]:
    errors: list[str] = []
    path = f"results[{index}]"
    if not isinstance(result, dict):
        return [f"{path} must be an object"]

    # Required
    for req in ["id", "tool", "ok"]:
        if req not in result:
            errors.append(f"{path} missing required '{req}'")

    # Additional properties check (G17)
    allowed = {"id", "tool", "ok", "error"}
    for k in cast(Mapping[str, Any], result):
        if k not in allowed:
            errors.append(f"{path} has unexpected field '{k}'")

    if "id" in result:
        res_id = cast(str, result["id"])
        if not re.match(r"^c[0-9]{5}$", res_id):
            errors.append(f"{path}.id '{res_id}' violates pattern ^c[0-9]{5}$")

    if "tool" in result and not isinstance(result["tool"], str):
        errors.append(f"{path}.tool must be a string")
    if "ok" in result and not isinstance(result["ok"], bool):
        errors.append(f"{path}.ok must be a boolean")

    if "error" in result:
        errors.extend(validate_error(result["error"], f"{path}.error"))

    return errors


def validate_contract(contract: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract, dict):
        return [f"{path} must be an object"]

    # Required: ["tool_deps", "io_schema", "budgets", "assertions"]
    for req in ["tool_deps", "io_schema", "budgets", "assertions"]:
        if req not in contract:
            errors.append(f"{path} missing required '{req}'")

    if "tool_deps" in contract:
        if not isinstance(contract["tool_deps"], list):
            errors.append(f"{path}.tool_deps must be a list")
        elif not all(isinstance(x, str) for x in contract["tool_deps"]):
            errors.append(f"{path}.tool_deps must be a list of strings")

    if "io_schema" in contract:
        io = contract["io_schema"]
        if not isinstance(io, dict):
            errors.append(f"{path}.io_schema must be an object")
        else:
            for req in ["trace_ptr", "final_schema", "citations_schema"]:
                if req not in io:
                    errors.append(f"{path}.io_schema missing required '{req}'")
            if "trace_ptr" in io and not isinstance(io["trace_ptr"], str):
                errors.append(f"{path}.io_schema.trace_ptr must be a string")

    if "budgets" in contract:
        budgets = contract["budgets"]
        if not isinstance(budgets, dict):
            errors.append(f"{path}.budgets must be an object")
        else:
            fields = ["max_calls", "max_parallel", "max_bytes_in", "max_bytes_out", "timeout_s"]
            for f in fields:
                if f not in budgets:
                    errors.append(f"{path}.budgets missing required '{f}'")
                elif not isinstance(budgets[f], int) or budgets[f] < 1:
                    errors.append(f"{path}.budgets.{f} must be a positive integer")

    if "assertions" in contract and not isinstance(contract["assertions"], list):
        errors.append(f"{path}.assertions must be a list")

    return errors


def main() -> int:
    exit_code = 0

    # 1. Validate final.json
    final_path = Path("out/ci/final.json")
    if final_path.exists():
        try:
            final = json.loads(final_path.read_text())
            errors = []
            if not isinstance(final, dict):
                errors.append("Root must be an object")
            else:
                if "ok" not in final:
                    errors.append("Root missing required 'ok'")
                if "results" not in final:
                    errors.append("Root missing required 'results'")
                allowed = {"ok", "results", "output", "meta"}
                for k in cast(Mapping[str, Any], final):
                    if k not in allowed:
                        errors.append(f"Root has unexpected field '{k}'")
                if "ok" in final and not isinstance(final["ok"], bool):
                    errors.append("Root.ok must be a boolean")
                if "results" in final:
                    results = cast(list[Any], final["results"])
                    for i, res in enumerate(results):
                        errors.extend(validate_result(res, i))
            if errors:
                print(f"Schema validation failed for {final_path}:", file=sys.stderr)
                for err in errors:
                    print(f"  - {err}", file=sys.stderr)
                exit_code = 1
            else:
                print(f"Verified {final_path}")
        except Exception as exc:
            print(f"Error reading {final_path}: {exc}", file=sys.stderr)
            exit_code = 1

    # 2. Validate all contract.json in out/
    for contract_path in Path("out").rglob("contract.json"):
        try:
            contract = json.loads(contract_path.read_text())
            errors = validate_contract(contract, str(contract_path))
            if errors:
                print(f"Schema validation failed for {contract_path}:", file=sys.stderr)
                for err in errors:
                    print(f"  - {err}", file=sys.stderr)
                exit_code = 1
            else:
                print(f"Verified {contract_path}")
        except Exception as exc:
            print(f"Error reading {contract_path}: {exc}", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
