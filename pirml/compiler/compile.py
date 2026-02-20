from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, cast

from pirml.compiler.extract import ExtractionError, extract_blocks
from pirml.compiler.io import write_compile_error, write_contract, write_prog, write_raw
from pirml.compiler.model import get_model_adapter
from pirml.compiler.prompt import build_compile_prompt
from pirml.compiler.types import (
    CompileArtifacts,
    CompileContract,
    CompileErr,
    CompileOutput,
    ContractBudget,
)
from pirml.contracts.schemas import ToolManifest
from pirml.toolsearch.loader import load_catalog, load_selected
from pirml.toolsearch.render import render_selected_tools
from pirml.toolsearch.search import search_tools


def assemble_tools_topk(
    tools_dir: Path,
    query: str,
    k: int = 5,
    mode: str | None = None,
    catalog: Mapping[str, ToolManifest] | None = None,
) -> list[dict[str, Any]]:
    """C1.T3: Assemble top-k tools for compilation.
    query -> search_tools -> load_selected(strict) -> render_selected_tools.
    """
    if catalog is None:
        catalog = load_catalog(str(tools_dir), strict=True)

    # 1. Search for top-k tools
    names = search_tools(catalog, query, mode=mode, k=k)

    # 2. Load selected tools (strict)
    selected_tools = load_selected(names, str(tools_dir))

    # 3. Render for prompt
    return render_selected_tools(selected_tools)


def compile_task(
    task: str,
    tools_dir: Path,
    out_dir: Path,
    query: str | None = None,
    k: int = 5,
    budgets: ContractBudget | None = None,
    model: str | None = None,
) -> CompileOutput:
    """C1.T7: Orchestrate compile pipeline.
    assemble -> model -> extract -> write artifacts.
    """
    if budgets is None:
        budgets = {
            "max_calls": 40,
            "max_parallel": 10,
            "max_bytes_in": 5000000,
            "max_bytes_out": 200000,
            "timeout_s": 60,
        }

    search_query = query or task
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Assemble tools
        tools = assemble_tools_topk(tools_dir, search_query, k=k)

        # 2. Build prompt
        prompt = build_compile_prompt(task, tools, budgets)

        # 3. Model call
        adapter = get_model_adapter()
        raw_text = adapter.compile_once(prompt)

        # Write raw capture immediately as per C1.T5
        write_raw(out_dir / "raw.txt", raw_text)

        # 4. Extract blocks
        prog_src, contract_src = extract_blocks(raw_text)

        # Parse contract JSON
        try:
            contract_data = json.loads(contract_src)
            # typed cast/wrap
            contract = cast_contract(contract_data)
        except json.JSONDecodeError as e:
            raise ExtractionError("invalid_contract_json", str(e))

        # 5. Write artifacts
        write_prog(out_dir / "prog.py", prog_src)
        write_contract(out_dir / "contract.json", contract)

        artifacts: CompileArtifacts = {
            "prog_src": prog_src,
            "contract": contract,
            "raw_text": raw_text,
        }
        return {"ok": True, "artifacts": artifacts}

    except ExtractionError as e:
        err: CompileErr = {"type": e.type, "msg": e.msg, "retryable": False}
        write_compile_error(out_dir / "compile_error.json", err)
        return {"ok": False, "error": err}
    except Exception as e:
        err: CompileErr = {"type": "internal_error", "msg": str(e), "retryable": False}
        write_compile_error(out_dir / "compile_error.json", err)
        return {"ok": False, "error": err}


def cast_contract(data: Any) -> CompileContract:
    """Helper to ensure CompileContract shape."""
    # In Cycle C2 we'll have a strict verifier.
    # For C1 we just ensure basic keys for the TypedDict.
    res: CompileContract = {
        "tool_deps": data.get("tool_deps", []),
        "io_schema": data.get("io_schema", {}),
        "budgets": data.get("budgets", {}),
        "assertions": data.get("assertions", []),
        "trace_ptr": data.get("trace_ptr", "trace.ndjson"),
    }
    return res
