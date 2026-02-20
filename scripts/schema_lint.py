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


def main() -> int:
    final_path = Path("out/ci/final.json")
    if not final_path.exists():
        print(f"Skipping: {final_path} not found")
        return 0

    try:
        final = json.loads(final_path.read_text())
    except Exception as exc:
        print(f"Error reading {final_path}: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []

    # Root checks
    if not isinstance(final, dict):
        errors.append("Root must be an object")
    else:
        # Required
        if "ok" not in final:
            errors.append("Root missing required 'ok'")
        if "results" not in final:
            errors.append("Root missing required 'results'")

        # Additional properties check (G17)
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

        if "meta" in final and not isinstance(final["meta"], dict):
            errors.append("Root.meta must be an object")

    if errors:
        print(f"Schema validation failed for {final_path}:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"Verified {final_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
