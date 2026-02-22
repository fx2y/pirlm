from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, cast

from ..contracts.schemas import ErrorObject
from .rpc import canonical_json


class PolicyIssue(TypedDict, total=False):
    code: str
    msg: str
    symbol: str | None


@dataclass(frozen=True)
class ToolRuntimePolicy:
    idempotent: bool = False
    cacheable: bool = False
    max_payload_bytes: int | None = None
    retry_n: int = 0
    timeout_s: float | None = None


@dataclass(frozen=True)
class RuntimePolicySet:
    artifact_writes: tuple[str, ...] = ()
    tool_policies: dict[str, ToolRuntimePolicy] = field(default_factory=dict)
    default_timeout_s: float | None = None
    timeout_overrides_s: dict[str, float] = field(default_factory=dict)

    def for_tool(self, tool: str) -> ToolRuntimePolicy | None:
        return self.tool_policies.get(tool)

    def timeout_for_tool(self, tool: str) -> float | None:
        return self.timeout_overrides_s.get(tool, self.default_timeout_s)


def _issue(code: str, msg: str, symbol: str | None = None) -> PolicyIssue:
    row: PolicyIssue = {"code": code, "msg": msg}
    if symbol is not None:
        row["symbol"] = symbol
    return row


def _path_is_within_artifacts(path_str: str) -> bool:
    path = Path(path_str)
    if path.is_absolute():
        return False
    parts = path.parts
    if not parts or parts[0] != "artifacts":
        return False
    return ".." not in parts


def parse_runtime_policy_set(
    contract: Mapping[str, Any],
    *,
    declared_tools: set[str] | None = None,
    budget_max_bytes_out: int | None = None,
) -> tuple[RuntimePolicySet | None, list[PolicyIssue]]:
    issues: list[PolicyIssue] = []

    artifact_writes: tuple[str, ...] = ()
    raw_artifacts = contract.get("artifact_writes")
    if raw_artifacts is not None:
        if not isinstance(raw_artifacts, list):
            issues.append(_issue("invalid_artifact_writes", "artifact_writes must be list[str]"))
        else:
            seen: set[str] = set()
            rows: list[str] = []
            for item in cast(list[Any], raw_artifacts):
                if not isinstance(item, str):
                    issues.append(_issue("invalid_artifact_writes", "artifact_writes must be list[str]"))
                    continue
                if item in seen:
                    issues.append(_issue("invalid_artifact_writes", "duplicate artifact_writes path", item))
                    continue
                seen.add(item)
                if not _path_is_within_artifacts(item):
                    issues.append(
                        _issue(
                            "artifact_path_denied",
                            "artifact_writes paths must be relative under artifacts/",
                            item,
                        )
                    )
                    continue
                rows.append(item)
            artifact_writes = tuple(rows)

    tool_policies: dict[str, ToolRuntimePolicy] = {}
    raw_tool_policies = contract.get("tool_policies")
    if raw_tool_policies is not None:
        if not isinstance(raw_tool_policies, Mapping):
            issues.append(_issue("invalid_tool_policies", "tool_policies must be object"))
        else:
            for tool_name, raw_policy in cast(Mapping[str, Any], raw_tool_policies).items():
                if not isinstance(tool_name, str):
                    issues.append(_issue("invalid_tool_policies", "tool_policies keys must be strings"))
                    continue
                if declared_tools is not None and tool_name not in declared_tools:
                    issues.append(
                        _issue("unknown_tool_policy", "tool_policies key must be declared in tool_deps", tool_name)
                    )
                if not isinstance(raw_policy, Mapping):
                    issues.append(_issue("invalid_tool_policy", "tool policy must be object", tool_name))
                    continue

                policy_map = cast(Mapping[str, Any], raw_policy)
                allowed_keys = {"idempotent", "cacheable", "max_payload_bytes", "retry", "timeout_s"}
                extra_keys = set(policy_map.keys()) - allowed_keys
                if extra_keys:
                    issues.append(
                        _issue(
                            "invalid_tool_policy",
                            f"unexpected tool policy keys: {sorted(list(extra_keys))}",
                            tool_name,
                        )
                    )

                idempotent = False
                if "idempotent" in policy_map:
                    val = policy_map.get("idempotent")
                    if not isinstance(val, bool):
                        issues.append(_issue("invalid_tool_policy", "idempotent must be bool", tool_name))
                    else:
                        idempotent = val

                cacheable = False
                if "cacheable" in policy_map:
                    val = policy_map.get("cacheable")
                    if not isinstance(val, bool):
                        issues.append(_issue("invalid_tool_policy", "cacheable must be bool", tool_name))
                    else:
                        cacheable = val
                        if cacheable:
                            issues.append(
                                _issue(
                                    "unsupported_policy_variant",
                                    "cacheable=true runtime adapter is not implemented",
                                    tool_name,
                                )
                            )

                max_payload_bytes: int | None = None
                if "max_payload_bytes" in policy_map:
                    val = policy_map.get("max_payload_bytes")
                    if not isinstance(val, int) or val <= 0:
                        issues.append(
                            _issue("invalid_tool_policy", "max_payload_bytes must be positive int", tool_name)
                        )
                    else:
                        max_payload_bytes = val
                        if budget_max_bytes_out is not None and max_payload_bytes > budget_max_bytes_out:
                            issues.append(
                                _issue(
                                    "policy_budget_conflict",
                                    "tool max_payload_bytes exceeds budgets.max_bytes_out",
                                    tool_name,
                                )
                            )

                retry_n = 0
                if "retry" in policy_map:
                    retry_val = policy_map.get("retry")
                    if not isinstance(retry_val, Mapping):
                        issues.append(_issue("invalid_tool_policy", "retry must be object", tool_name))
                    else:
                        retry_map = cast(Mapping[str, Any], retry_val)
                        retry_extra = set(retry_map.keys()) - {"n"}
                        if retry_extra:
                            issues.append(
                                _issue(
                                    "invalid_tool_policy",
                                    f"retry has unexpected keys: {sorted(list(retry_extra))}",
                                    tool_name,
                                )
                            )
                        n_val = retry_map.get("n")
                        if not isinstance(n_val, int) or n_val < 0:
                            issues.append(
                                _issue("invalid_tool_policy", "retry.n must be non-negative int", tool_name)
                            )
                        else:
                            retry_n = n_val
                            if retry_n > 0 and not idempotent:
                                issues.append(
                                    _issue(
                                        "invalid_tool_policy",
                                        "retry.n > 0 requires idempotent=true",
                                        tool_name,
                                    )
                                )

                timeout_s: float | None = None
                if "timeout_s" in policy_map:
                    timeout_val = policy_map.get("timeout_s")
                    if not isinstance(timeout_val, (int, float)) or float(timeout_val) <= 0:
                        issues.append(_issue("invalid_tool_policy", "timeout_s must be > 0", tool_name))
                    else:
                        timeout_s = float(timeout_val)

                tool_policies[tool_name] = ToolRuntimePolicy(
                    idempotent=idempotent,
                    cacheable=cacheable,
                    max_payload_bytes=max_payload_bytes,
                    retry_n=retry_n,
                    timeout_s=timeout_s,
                )

    default_timeout_s: float | None = None
    timeout_overrides_s: dict[str, float] = {}
    raw_timeouts = contract.get("timeouts")
    if raw_timeouts is not None:
        if not isinstance(raw_timeouts, Mapping):
            issues.append(_issue("invalid_timeouts", "timeouts must be object"))
        else:
            timeouts = cast(Mapping[str, Any], raw_timeouts)
            extra = set(timeouts.keys()) - {"default_s", "tool_overrides"}
            if extra:
                issues.append(_issue("invalid_timeouts", f"unexpected timeout keys: {sorted(list(extra))}"))
            if "default_s" in timeouts:
                default_val = timeouts.get("default_s")
                if not isinstance(default_val, (int, float)) or float(default_val) <= 0:
                    issues.append(_issue("invalid_timeouts", "timeouts.default_s must be > 0"))
                else:
                    default_timeout_s = float(default_val)
            if "tool_overrides" in timeouts:
                overrides_val = timeouts.get("tool_overrides")
                if not isinstance(overrides_val, Mapping):
                    issues.append(_issue("invalid_timeouts", "timeouts.tool_overrides must be object"))
                else:
                    for tool_name, timeout_val in cast(Mapping[str, Any], overrides_val).items():
                        if not isinstance(tool_name, str):
                            issues.append(_issue("invalid_timeouts", "tool_overrides keys must be strings"))
                            continue
                        if declared_tools is not None and tool_name not in declared_tools:
                            issues.append(
                                _issue(
                                    "unknown_timeout_tool",
                                    "timeouts.tool_overrides key must be declared in tool_deps",
                                    tool_name,
                                )
                            )
                        if not isinstance(timeout_val, (int, float)) or float(timeout_val) <= 0:
                            issues.append(
                                _issue(
                                    "invalid_timeouts",
                                    "tool timeout override must be > 0",
                                    tool_name,
                                )
                            )
                            continue
                        timeout_overrides_s[tool_name] = float(timeout_val)

    if issues:
        return None, issues
    return RuntimePolicySet(
        artifact_writes=artifact_writes,
        tool_policies=tool_policies,
        default_timeout_s=default_timeout_s,
        timeout_overrides_s=timeout_overrides_s,
    ), issues


def cache_key_for_call(tool: str, args: Mapping[str, Any]) -> str:
    payload = {"tool": tool, "args": dict(cast(Mapping[str, Any], args))}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def resolve_effective_timeout(
    *,
    call_timeout: float | None,
    remaining_timeout: float,
    policy_timeout: float | None,
) -> float:
    candidates = [remaining_timeout]
    if call_timeout is not None:
        candidates.append(call_timeout)
    if policy_timeout is not None:
        candidates.append(policy_timeout)
    return min(candidates)


def execution_policy_error(tool: str, policy: ToolRuntimePolicy) -> ErrorObject | None:
    if policy.cacheable:
        return {
            "type": "unsupported",
            "msg": f"cacheable runtime policy unsupported for {tool}",
            "retryable": False,
        }
    if policy.retry_n > 0 and not policy.idempotent:
        return {
            "type": "unsupported",
            "msg": f"retry policy requires idempotent=true for {tool}",
            "retryable": False,
        }
    return None


def clamp_retry_budget(max_retries: int, policy: ToolRuntimePolicy | None) -> int:
    if policy is None:
        return max_retries
    if policy.retry_n < 0:
        return 0
    return min(max_retries, policy.retry_n)


def enforce_payload_cap(
    *,
    tool: str,
    payload: Mapping[str, Any],
    policy: ToolRuntimePolicy | None,
) -> Mapping[str, Any]:
    if policy is None or policy.max_payload_bytes is None:
        return payload
    if not bool(payload.get("ok")):
        return payload
    output = payload.get("output")
    out_bytes = len(canonical_json(output).encode("utf-8"))
    if out_bytes <= policy.max_payload_bytes:
        return payload
    meta_src = payload.get("meta")
    meta = dict(cast(Mapping[str, Any], meta_src)) if isinstance(meta_src, Mapping) else {}
    meta["policy_max_payload_bytes"] = policy.max_payload_bytes
    meta["output_bytes"] = out_bytes
    return {
        "ok": False,
        "error": {
            "type": "output_too_large",
            "msg": f"tool output exceeds max_payload_bytes for {tool}",
            "retryable": False,
        },
        "meta": meta,
    }
