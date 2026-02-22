from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from pirml.contracts.schemas import ManifestError

ALLOWED_CALLERS: frozenset[str] = frozenset({"direct", "code_exec"})


def lint_allowed_callers(value: object, *, path: str = "allowed_callers") -> list[ManifestError]:
    errors: list[ManifestError] = []
    if not isinstance(value, list):
        errors.append(
            {
                "code": "M8",
                "msg": "allowed_callers must be a list containing exactly one value",
                "path": path,
            }
        )
        return errors
    values = cast(list[object], value)
    callers = [item for item in values if isinstance(item, str)]
    if len(callers) != len(values):
        errors.append(
            {"code": "M8", "msg": "allowed_callers must contain strings only", "path": path}
        )
        return errors
    if len(callers) != 1:
        errors.append(
            {
                "code": "M8",
                "msg": "allowed_callers must contain exactly one value (direct xor code_exec)",
                "path": path,
            }
        )
    unknown = sorted(set(callers) - ALLOWED_CALLERS)
    if unknown:
        errors.append(
            {
                "code": "M8",
                "msg": f"allowed_callers has unknown value(s): {', '.join(unknown)}",
                "path": path,
            }
        )
    return errors


def require_caller_allowed(manifest: Mapping[str, Any], *, caller: str, tool_name: str) -> None:
    allowed_callers = manifest.get("allowed_callers")
    if allowed_callers is None:
        raise ValueError(f"Tool '{tool_name}' is missing required policy field: allowed_callers")
    errors = lint_allowed_callers(allowed_callers)
    if errors:
        raise ValueError(f"Tool '{tool_name}' has invalid allowed_callers policy")
    allowed = str(allowed_callers[0])
    if allowed != caller:
        raise ValueError(
            f"Tool '{tool_name}' denies caller '{caller}' via allowed_callers={allowed_callers}"
        )
