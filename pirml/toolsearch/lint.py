from __future__ import annotations

import re
from typing import Any, cast

from pirml.contracts.schemas import ManifestError, ToolManifest


def lint_manifest(manifest: Any) -> list[ManifestError]:
    """C1.T3: Authoring quality gates for a single manifest.
    G.P0.2: Enforce strict schema and unknown key rejection.
    """
    errors: list[ManifestError] = []

    if not isinstance(manifest, dict):
        errors.append({"code": "M0", "msg": "Manifest must be an object", "path": ""})
        return errors

    m = cast("dict[str, Any]", manifest)

    # 1. Enforce strict root keys (additionalProperties: false)
    allowed_keys = {
        "name",
        "description",
        "input_schema",
        "input_examples",
        "tags",
        "defer_loading",
        "aliases",
        "verbs",
        "nouns",
    }
    required_keys = {"name", "description", "input_schema"}

    for key in m:
        if key not in allowed_keys:
            errors.append({"code": "schema", "msg": f"unknown root key: {key}", "path": key})

    for key in required_keys:
        if key not in m:
            code = "schema"
            if key == "name":
                code = "M1"
            elif key == "description":
                code = "M2"
            elif key == "input_schema":
                code = "M3"
            errors.append({"code": code, "msg": f"missing required key: {key}", "path": key})

    # name: namespace dotted; <=64
    name = m.get("name")
    if name is not None:
        if not isinstance(name, str):
            errors.append({"code": "M1", "msg": "name must be a string", "path": "name"})
        else:
            if len(name) > 64:
                errors.append(
                    {"code": "M1", "msg": f"name '{name}' exceeds 64 chars", "path": "name"}
                )
            if not re.match(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", name):
                errors.append(
                    {
                        "code": "M1",
                        "msg": f"name '{name}' must be dotted namespace (e.g. svc.tool)",
                        "path": "name",
                    }
                )

    # description: >=3 sentences; >=30 chars; include guidance
    desc = m.get("description")
    if desc is not None:
        if not isinstance(desc, str):
            errors.append(
                {"code": "M2", "msg": "description must be a string", "path": "description"}
            )
        else:
            if len(desc) < 30:
                errors.append(
                    {
                        "code": "M2",
                        "msg": f"description must be at least 30 chars, got {len(desc)}",
                        "path": "description",
                    }
                )
            # Simple sentence count: split by . ! ?
            sentences = [s.strip() for s in re.split(r"[.!?]", desc) if s.strip()]
            if len(sentences) < 3:
                errors.append(
                    {
                        "code": "M2",
                        "msg": "description must have >= 3 sentences",
                        "path": "description",
                    }
                )

            desc_l = desc.lower()
            if not any(t in desc_l for t in ["when not to use", "not-when", "avoid", "instead of"]):
                errors.append(
                    {
                        "code": "M2",
                        "msg": "description must include 'when NOT to use' guidance",
                        "path": "description",
                    }
                )

    # input_schema: object
    schema = m.get("input_schema")
    if schema is not None and not isinstance(schema, dict):
        errors.append(
            {"code": "M3", "msg": "input_schema must be an object", "path": "input_schema"}
        )

    # input_examples: list of objects
    examples = m.get("input_examples")
    if examples is not None:
        if not isinstance(examples, list):
            errors.append(
                {"code": "M4", "msg": "input_examples must be a list", "path": "input_examples"}
            )
        else:
            for i, ex in enumerate(cast("list[Any]", examples)):
                if not isinstance(ex, dict):
                    errors.append(
                        {
                            "code": "M4",
                            "msg": f"example {i} must be an object",
                            "path": f"input_examples[{i}]",
                        }
                    )
                else:
                    # G.P0.2: basic validation of example vs schema
                    ex_dict = cast(dict[str, Any], ex)
                    if isinstance(schema, dict):
                        props = cast(dict[str, Any], schema.get("properties", {}))
                        required = cast(list[str], schema.get("required", []))

                        # Check for unknown properties
                        for arg in ex_dict:
                            if arg not in props:
                                errors.append(
                                    {
                                        "code": "example_invalid",
                                        "msg": f"example {i} uses unknown property '{arg}'",
                                        "path": f"input_examples[{i}]",
                                    }
                                )

                        # Check for missing required properties
                        for req in required:
                            if req not in ex_dict:
                                errors.append(
                                    {
                                        "code": "example_invalid",
                                        "msg": f"example {i} missing required property '{req}'",
                                        "path": f"input_examples[{i}]",
                                    }
                                )

                        # Check for type mismatch
                        for arg, val in ex_dict.items():
                            if arg in props:
                                p_def = props[arg]
                                p_type = p_def.get("type")
                                if p_type:
                                    valid = True
                                    if (p_type == "string" and not isinstance(val, str)) or \
                                       (p_type == "number" and not isinstance(val, (int, float))) or \
                                       (p_type == "integer" and not (isinstance(val, int) and not isinstance(val, bool))) or \
                                       (p_type == "boolean" and not isinstance(val, bool)) or \
                                       (p_type == "object" and not isinstance(val, dict)) or \
                                       (p_type == "array" and not isinstance(val, list)):
                                        valid = False

                                    if not valid:
                                        errors.append(
                                            {
                                                "code": "example_invalid",
                                                "msg": f"example {i} property '{arg}' type mismatch: expected {p_type}",
                                                "path": f"input_examples[{i}]",
                                            }
                                        )

    # other types
    for key, t in [
        ("tags", list),
        ("aliases", list),
        ("verbs", list),
        ("nouns", list),
        ("defer_loading", bool),
    ]:
        if key in m and not isinstance(m[key], t):
            errors.append({"code": "schema", "msg": f"{key} must be a {t.__name__}", "path": key})

    return errors


def lint_catalog(catalog: dict[str, ToolManifest]) -> list[ManifestError]:
    """C1.T3: Catalog-wide quality gates."""
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

    if catalog:
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
