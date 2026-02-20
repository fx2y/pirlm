from __future__ import annotations

import re
from typing import Any, cast

from pirml.contracts.schemas import ManifestError, ToolManifest


def lint_manifest(manifest: Any) -> list[ManifestError]:
    """C1.T3: Authoring quality gates for a single manifest."""
    errors: list[ManifestError] = []

    if not isinstance(manifest, dict):
        errors.append({"code": "M0", "msg": "Manifest must be an object", "path": ""})
        return errors

    m = cast("dict[str, Any]", manifest)

    # unique dotted name <= 64
    name = m.get("name")
    if not isinstance(name, str):
        errors.append({"code": "M1", "msg": "name must be a string", "path": "name"})
    else:
        if len(name) > 64:
            errors.append({"code": "M1", "msg": f"name '{name}' exceeds 64 chars", "path": "name"})
        # Spec: "namespace dotted; <=64; no spaces"
        if not re.match(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", name):
            errors.append(
                {
                    "code": "M1",
                    "msg": f"name '{name}' must be dotted namespace (e.g. svc.tool)",
                    "path": "name",
                }
            )

    # desc >= 3 sentences incl not-when token
    desc = m.get("description")
    if not isinstance(desc, str):
        errors.append({"code": "M2", "msg": "description must be a string", "path": "description"})
    else:
        # Simple sentence count: split by . ! ?
        sentences = [s.strip() for s in re.split(r"[.!?]", desc) if s.strip()]
        if len(sentences) < 3:
            errors.append(
                {"code": "M2", "msg": "description must have >= 3 sentences", "path": "description"}
            )

        # Anthropic docs: "when NOT to use" token or similar is good
        desc_l = desc.lower()
        if not any(t in desc_l for t in ["when not to use", "not-when", "avoid", "instead of"]):
            errors.append(
                {
                    "code": "M2",
                    "msg": "description must include 'when NOT to use' guidance",
                    "path": "description",
                }
            )

    # input_schema required
    if "input_schema" not in m:
        errors.append({"code": "M3", "msg": "input_schema is required", "path": "input_schema"})

    # input_examples validation
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
                # TODO: Implement deep schema validation if a library becomes available

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
