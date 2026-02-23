from __future__ import annotations

import re
from typing import Any, cast

from pirml.contracts.schemas import ManifestError, ToolManifest
from pirml.toolsearch.policy import lint_allowed_callers

_ALLOWED_KEYS = {
    "name",
    "description",
    "input_schema",
    "input_examples",
    "idempotent",
    "cacheable",
    "max_payload_bytes",
    "timeout_s",
    "retry",
    "allowed_callers",
    "tags",
    "defer_loading",
    "aliases",
    "verbs",
    "nouns",
}
_REQUIRED_KEYS = {"name", "description", "input_schema"}
_AMBIGUOUS_ARG_NAMES = {"user", "data", "id"}
_INPUT_POLICIES = (
    ("idempotent", bool),
    ("cacheable", bool),
    ("max_payload_bytes", int),
    ("defer_loading", bool),
    ("timeout_s", (int, float)),
)
_LIST_FIELDS = ("tags", "aliases", "verbs", "nouns")
_NAME_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def _add_error(errors: list[ManifestError], code: str, msg: str, path: str) -> None:
    errors.append({"code": code, "msg": msg, "path": path})


def _lint_root_keys(m: dict[str, Any], errors: list[ManifestError]) -> None:
    for key in m:
        if key not in _ALLOWED_KEYS:
            _add_error(errors, "schema", f"unknown root key: {key}", key)
    for key in _REQUIRED_KEYS:
        if key in m:
            continue
        code = {"name": "M1", "description": "M2", "input_schema": "M3"}[key]
        _add_error(errors, code, f"missing required key: {key}", key)


def _lint_name(m: dict[str, Any], errors: list[ManifestError]) -> None:
    name = m.get("name")
    if name is None:
        return
    if not isinstance(name, str):
        _add_error(errors, "M1", "name must be a string", "name")
        return
    if len(name) > 64:
        _add_error(errors, "M1", f"name '{name}' exceeds 64 chars", "name")
    if _NAME_PATTERN.match(name) is None:
        _add_error(errors, "M1", f"name '{name}' must be dotted namespace (e.g. svc.tool)", "name")


def _lint_description(m: dict[str, Any], errors: list[ManifestError]) -> None:
    desc = m.get("description")
    if desc is None:
        return
    if not isinstance(desc, str):
        _add_error(errors, "M2", "description must be a string", "description")
        return
    if len(desc) < 30:
        _add_error(
            errors,
            "M2",
            f"description must be at least 30 chars, got {len(desc)}",
            "description",
        )
    sentences = [s.strip() for s in re.split(r"[.!?]", desc) if s.strip()]
    if len(sentences) < 3:
        _add_error(errors, "M2", "description must have >= 3 sentences", "description")
    desc_l = desc.lower()
    if not any(t in desc_l for t in ("when not to use", "not-when", "avoid", "instead of")):
        _add_error(
            errors,
            "M2",
            "description must include 'when NOT to use' guidance",
            "description",
        )


def _lint_input_schema(m: dict[str, Any], errors: list[ManifestError]) -> dict[str, Any]:
    schema = m.get("input_schema")
    if schema is None:
        return {}
    if not isinstance(schema, dict):
        _add_error(errors, "M3", "input_schema must be an object", "input_schema")
        return {}
    return cast(dict[str, Any], schema)


def _lint_input_examples(
    m: dict[str, Any], schema: dict[str, Any], errors: list[ManifestError]
) -> list[dict[str, Any]]:
    examples = m.get("input_examples")
    if examples is None:
        _add_error(
            errors, "M5", "input_examples must contain at least 3 examples", "input_examples"
        )
        return []
    if not isinstance(examples, list):
        _add_error(errors, "M4", "input_examples must be a list", "input_examples")
        return []
    examples_list = cast(list[Any], examples)
    if len(examples_list) < 3:
        _add_error(
            errors, "M5", "input_examples must contain at least 3 examples", "input_examples"
        )

    props = cast(dict[str, Any], schema.get("properties", {}))
    required = cast(list[str], schema.get("required", []))
    valid_examples: list[dict[str, Any]] = []
    for i, ex in enumerate(examples_list):
        if not isinstance(ex, dict):
            _add_error(errors, "M4", f"example {i} must be an object", f"input_examples[{i}]")
            continue
        ex_dict = cast(dict[str, Any], ex)
        valid_examples.append(ex_dict)

        for arg in ex_dict:
            if arg not in props:
                _add_error(
                    errors,
                    "example_invalid",
                    f"example {i} uses unknown property '{arg}'",
                    f"input_examples[{i}]",
                )
        for req in required:
            if req not in ex_dict:
                _add_error(
                    errors,
                    "example_invalid",
                    f"example {i} missing required property '{req}'",
                    f"input_examples[{i}]",
                )
        for arg, val in ex_dict.items():
            if arg not in props:
                continue
            p_def = cast(dict[str, Any], props[arg])
            p_type = p_def.get("type")
            if not isinstance(p_type, str):
                continue
            validators: dict[str, bool] = {
                "string": isinstance(val, str),
                "number": isinstance(val, (int, float)),
                "integer": isinstance(val, int) and not isinstance(val, bool),
                "boolean": isinstance(val, bool),
                "object": isinstance(val, dict),
                "array": isinstance(val, list),
            }
            valid = validators.get(p_type, True)
            if not valid:
                _add_error(
                    errors,
                    "example_invalid",
                    f"example {i} property '{arg}' type mismatch: expected {p_type}",
                    f"input_examples[{i}]",
                )
    return valid_examples


def _lint_schema_properties(schema: dict[str, Any], errors: list[ManifestError]) -> None:
    props = cast(dict[str, Any], schema.get("properties", {}))
    ambiguous = sorted(_AMBIGUOUS_ARG_NAMES.intersection(props.keys()))
    if ambiguous:
        _add_error(
            errors,
            "M6",
            f"ambiguous input arg names forbidden: {', '.join(ambiguous)}",
            "input_schema.properties",
        )


def _lint_policy_fields(m: dict[str, Any], errors: list[ManifestError]) -> None:
    for key, expected_type in _INPUT_POLICIES:
        value = m.get(key)
        if value is None:
            if key in {"max_payload_bytes", "timeout_s", "idempotent", "cacheable"}:
                _add_error(errors, "M7", f"{key} is required", key)
            continue
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type) or isinstance(value, bool):
                _add_error(errors, "schema", f"{key} must be numeric", key)
                continue
        elif not isinstance(value, expected_type):
            _add_error(errors, "schema", f"{key} must be a {expected_type.__name__}", key)
            continue
        if key == "max_payload_bytes" and cast(int, value) <= 0:
            _add_error(errors, "M7", "max_payload_bytes must be > 0", key)
        if key == "timeout_s" and cast(float, value) <= 0:
            _add_error(errors, "M7", "timeout_s must be > 0", key)

    retry = m.get("retry")
    if retry is None:
        _add_error(errors, "M9", "retry is required", "retry")
    elif not isinstance(retry, dict):
        _add_error(errors, "M9", "retry must be an object", "retry")
    else:
        retry_map = cast(dict[str, Any], retry)
        attempts = retry_map.get("max_attempts")
        if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0:
            _add_error(errors, "M9", "retry.max_attempts must be int >= 0", "retry.max_attempts")
        idempotent = m.get("idempotent")
        if isinstance(attempts, int) and attempts > 0 and idempotent is not True:
            _add_error(
                errors,
                "M9",
                "retry.max_attempts > 0 requires idempotent=true",
                "retry.max_attempts",
            )

    allowed_callers = m.get("allowed_callers")
    if allowed_callers is None:
        _add_error(errors, "M8", "allowed_callers is required", "allowed_callers")
    else:
        errors.extend(lint_allowed_callers(allowed_callers))


def _lint_optional_types(m: dict[str, Any], errors: list[ManifestError]) -> None:
    for key in _LIST_FIELDS:
        if key in m and not isinstance(m[key], list):
            _add_error(errors, "schema", f"{key} must be a list", key)


def _lint_ambiguous_tool_examples(
    m: dict[str, Any],
    schema: dict[str, Any],
    examples: list[dict[str, Any]],
    errors: list[ManifestError],
) -> None:
    has_examples = bool(examples)
    has_aliases = bool(m.get("aliases"))
    props = cast(dict[str, Any], schema.get("properties", {}))
    required = cast(list[str], schema.get("required", []))
    has_optional = any(p not in required for p in props)
    if (has_aliases or has_optional) and not has_examples:
        _add_error(
            errors,
            "M4",
            "Tool is ambiguous (has aliases or optional args) but lacks input_examples",
            "input_examples",
        )


def lint_manifest(manifest: Any) -> list[ManifestError]:
    """C1.T3: Authoring quality gates for a single manifest.
    G.P0.2: Enforce strict schema and unknown key rejection.
    """
    errors: list[ManifestError] = []

    if not isinstance(manifest, dict):
        _add_error(errors, "M0", "Manifest must be an object", "")
        return errors

    m = cast("dict[str, Any]", manifest)
    _lint_root_keys(m, errors)
    _lint_name(m, errors)
    _lint_description(m, errors)
    schema = _lint_input_schema(m, errors)
    examples = _lint_input_examples(m, schema, errors)
    _lint_schema_properties(schema, errors)
    _lint_policy_fields(m, errors)
    _lint_optional_types(m, errors)
    _lint_ambiguous_tool_examples(m, schema, examples, errors)

    return errors


def lint_catalog(
    catalog: dict[str, ToolManifest], *, enforce_hot_count: bool = True
) -> list[ManifestError]:
    """C1.T3: Catalog-wide quality gates.

    `enforce_hot_count=False` is a bootstrap lane for authoring flows where a
    single freshly scaffolded tool should still validate at manifest level.
    """
    errors: list[ManifestError] = []

    # all-deferred reject
    all_deferred = True
    hot_tools: list[str] = []

    for name, manifest in catalog.items():
        if manifest.get("defer_loading") is False:
            all_deferred = False
            hot_tools.append(name)

        # Run individual lint
        m_errors = lint_manifest(manifest)
        for err in m_errors:
            # Prefix path with manifest name
            err["path"] = f"{name}.{err['path']}" if err["path"] else name
            errors.append(err)

    if catalog and enforce_hot_count:
        if all_deferred:
            errors.append(
                {
                    "code": "C1",
                    "msg": "All tools are deferred; must have 3-5 hot tools",
                    "path": "catalog",
                }
            )

        # hot count 3-5
        if len(hot_tools) < 3 or len(hot_tools) > 5:
            errors.append(
                {
                    "code": "C2",
                    "msg": f"Hot tools count must be 3-5, got {len(hot_tools)} ({', '.join(hot_tools)})",
                    "path": "catalog",
                }
            )

    return errors
