from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, strict_parse_args
from pirml.runtime.lint import LintFailure, lint_tools_dir
from pirml.runtime.rpc import canonical_json
from pirml.toolsearch.index import K_CAP, tool_doc_fields
from pirml.toolsearch.lint import lint_catalog
from pirml.toolsearch.loader import catalog_hash, load_catalog
from pirml.toolsearch.search import search_tools

_TOOL_NAME_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")


def _base_manifest(name: str) -> dict[str, Any]:
    description = (
        f"{name} processes deterministic inputs and returns bounded structured output. "
        "Use it when a focused transformation is required. "
        "When NOT to use: avoid this tool for broad workflows or unbounded output."
    )
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Primary deterministic input string.",
                }
            },
            "required": ["input"],
        },
        "input_examples": [{"input": "alpha"}, {"input": "beta"}, {"input": "gamma"}],
        "idempotent": True,
        "cacheable": True,
        "max_payload_bytes": 4096,
        "timeout_s": 5,
        "retry": {"max_attempts": 1},
        "allowed_callers": ["code_exec"],
        "tags": ["custom"],
        "defer_loading": True,
    }


def _init_scaffold(name: str, tools_dir: Path, force: bool) -> dict[str, str]:
    if _TOOL_NAME_RE.match(name) is None:
        raise CliFailure(
            "validation",
            "tool name must match dotted namespace (e.g. svc.tool_name)",
            1,
            retryable=False,
        )
    tools_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = tools_dir / f"{name}.json"
    readme_path = tools_dir / f"{name}.README.md"
    examples_path = tools_dir / f"{name}.examples.jsonl"

    paths = (manifest_path, readme_path, examples_path)
    if not force and any(path.exists() for path in paths):
        raise CliFailure("validation", f"tool scaffold already exists: {name}", 1, retryable=False)

    manifest = _base_manifest(name)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    readme_path.write_text(
        (
            f"# {name}\n\n"
            "Inputs: pass explicit fields only.\n"
            "Outputs: keep payload bounded and deterministic.\n"
        ),
        encoding="utf-8",
    )
    examples_path.write_text(
        "\n".join(canonical_json(example) for example in manifest["input_examples"]) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": str(manifest_path.resolve()),
        "readme": str(readme_path.resolve()),
        "examples": str(examples_path.resolve()),
    }


def _lint_command(tools_dir: Path) -> int:
    try:
        catalog, errors = lint_tools_dir(tools_dir)
    except LintFailure as err:
        raise CliFailure(err.err_type, err.msg, err.code, err.retryable) from err
    if errors:
        raise CliFailure(
            "validation",
            f"manifest lint failed: {len(errors)} error(s) in {tools_dir}",
            1,
            retryable=False,
        )
    print(json.dumps({"ok": True, "tools_dir": str(tools_dir), "count": len(catalog)}))
    return 0


def _pack_payload(tools_dir: Path) -> dict[str, Any]:
    if not tools_dir.exists():
        raise CliFailure("config", f"tools directory not found: {tools_dir}", 2, retryable=False)
    try:
        catalog = load_catalog(tools_dir, strict=True)
    except Exception as exc:
        raise CliFailure("integrity", str(exc), 2, retryable=False) from exc
    if not catalog:
        raise CliFailure("validation", f"no manifests found in {tools_dir}", 1, retryable=False)
    lint_errors = lint_catalog(catalog)
    if lint_errors:
        raise CliFailure(
            "validation",
            f"cannot pack invalid catalog: {len(lint_errors)} lint error(s)",
            1,
            retryable=False,
        )

    docs: list[dict[str, Any]] = []
    rankings: list[dict[str, Any]] = []
    for name in sorted(catalog.keys()):
        manifest = catalog[name]
        schema = manifest.get("input_schema") or {}
        props = cast(dict[str, Any], schema.get("properties") or {})
        docs.append(
            {
                "name": name,
                "arg_names": sorted(props.keys()),
                "defer_loading": bool(manifest.get("defer_loading", True)),
                "doc": tool_doc_fields(manifest),
            }
        )
        rankings.append({"query": name, "top_k": search_tools(catalog, name, k=K_CAP)})
    return {
        "catalog_hash": catalog_hash(catalog),
        "k_cap": K_CAP,
        "doc_count": len(docs),
        "docs": docs,
        "rankings": rankings,
    }


def _pack_command(tools_dir: Path, out: Path) -> int:
    payload = _pack_payload(tools_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    print(
        json.dumps({"ok": True, "out": str(out.resolve()), "catalog_hash": payload["catalog_hash"]})
    )
    return 0


def run_tool_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pirml tool")
    sub = parser.add_subparsers(dest="tool_cmd", required=True)

    init_parser = sub.add_parser("init", help="Create deterministic tool scaffold files")
    init_parser.add_argument("name")
    init_parser.add_argument("--tools-dir", default="tools")
    init_parser.add_argument("--force", action="store_true")

    lint_parser = sub.add_parser("lint", help="Lint tool manifests")
    lint_parser.add_argument("--tools-dir", default="tools")

    pack_parser = sub.add_parser("pack", help="Write deterministic tool index artifact")
    pack_parser.add_argument("--tools-dir", default="tools")
    pack_parser.add_argument("--out", default="out/tool-pack.json")

    args = strict_parse_args(parser, argv)
    tool_cmd = str(args.tool_cmd)
    if tool_cmd == "init":
        files = _init_scaffold(str(args.name), Path(args.tools_dir), bool(args.force))
        print(json.dumps({"ok": True, "name": args.name, "files": files}, sort_keys=True))
        return 0
    if tool_cmd == "lint":
        return _lint_command(Path(args.tools_dir))
    if tool_cmd == "pack":
        return _pack_command(Path(args.tools_dir), Path(args.out))
    raise CliFailure("config", f"unknown tool command: {tool_cmd}", 2, retryable=False)
