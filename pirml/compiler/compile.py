from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pirml.compiler.extract import ExtractionError, extract_blocks
from pirml.compiler.io import write_compile_error, write_contract, write_prog, write_raw
from pirml.compiler.model import get_model_adapter
from pirml.compiler.prompt import build_compile_prompt
from pirml.compiler.repair import is_trivial_repair, repair_once
from pirml.compiler.smoke import run_smoke_subprocess
from pirml.compiler.types import (
    CompileArtifacts,
    CompileErrorFile,
    CompileOutput,
    ContractBudget,
    VerificationError,
)
from pirml.compiler.verify import verify_compile_output
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

    # T4: Reject tools lacking examples when ambiguous (optional args or aliases)
    for tool in selected_tools:
        name = tool.get("name", "unknown")
        has_examples = bool(tool.get("input_examples"))
        has_aliases = bool(tool.get("aliases"))

        schema = tool.get("input_schema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])
        has_optional = any(p not in required for p in props)

        if (has_aliases or has_optional) and not has_examples:
            raise ValueError(
                f"Tool '{name}' is ambiguous (has aliases or optional args) but lacks input_examples. "
                "Examples are required for ambiguous tools to ensure compiler precision."
            )

    # 3. Render for prompt
    return render_selected_tools(selected_tools)


def compile_task(
    task: str,
    tools_dir: Path,
    out_dir: Path,
    query: str | None = None,
    k: int = 5,
    budgets: ContractBudget | None = None,
    skip_smoke: bool = False,
) -> CompileOutput:
    """C1.T7: Orchestrate compile pipeline.
    assemble -> model -> extract -> verify -> smoke -> write artifacts.
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

        # 5. Verify (Cycle C2)
        tool_names = [t["name"] for t in tools]
        contract, errors = verify_compile_output(prog_src, contract_src, tool_names)

        # C4.P3: Repair-once (Bet-A5)
        if errors:
            can_repair = all(is_trivial_repair(e.get("code", "")) for e in errors)
            if can_repair:
                prog_src, contract_src, repaired = repair_once(prog_src, contract_src, errors)
                if repaired:
                    # Re-verify after repair
                    contract, errors = verify_compile_output(prog_src, contract_src, tool_names)
            else:
                # Add a marker that repair was declined for nontrivial errors
                for e in errors:
                    code = e.get("code", "")
                    if not is_trivial_repair(code):
                        msg = e.get("msg", "Unknown error")
                        e["msg"] = f"[repair_declined] {msg}"

        if errors:
            err_file: CompileErrorFile = {
                "ok": False,
                "errors": cast(Any, errors),
                "warnings": [],
                "stage": "verify",
            }
            write_compile_error(out_dir / "compile_error.json", err_file)
            return {"ok": False, "error": err_file}

        assert contract is not None  # if no errors, contract must be valid

        # 6. Smoke Test (Cycle C3)
        if not skip_smoke:
            smoke_res = run_smoke_subprocess(prog_src, contract)
            # Always emit smoke trace artifact as per P1.05
            (out_dir / "smoke_trace.ndjson").write_text(smoke_res.stdout, encoding="utf-8")

            if not smoke_res.ok:
                smoke_err = smoke_res.error or {
                    "type": "smoke_failed",
                    "msg": "Unknown smoke failure",
                    "retryable": False,
                }
                v_err: VerificationError = {
                    "code": smoke_err.get("type", "smoke_failed"),
                    "msg": smoke_err.get("msg", "Unknown smoke failure"),
                    "line": None,
                    "symbol": None,
                }
                err_file_smoke: CompileErrorFile = {
                    "ok": False,
                    "errors": [v_err],
                    "warnings": [],
                    "stage": "smoke",
                }
                write_compile_error(out_dir / "compile_error.json", err_file_smoke)
                return {"ok": False, "error": err_file_smoke}

        # 7. Write artifacts
        write_prog(out_dir / "prog.py", prog_src)
        write_contract(out_dir / "contract.json", contract)

        artifacts: CompileArtifacts = {
            "prog_src": prog_src,
            "contract": contract,
            "raw_text": raw_text,
        }
        return {"ok": True, "artifacts": artifacts}

    except ExtractionError as e:
        err_file_ext: CompileErrorFile = {
            "ok": False,
            "errors": [{"code": e.type, "msg": e.msg, "line": None, "symbol": None}],
            "warnings": [],
            "stage": "extract",
        }
        write_compile_error(out_dir / "compile_error.json", err_file_ext)
        return {"ok": False, "error": err_file_ext}
    except Exception as e:
        err_file_int: CompileErrorFile = {
            "ok": False,
            "errors": [{"code": "internal_error", "msg": str(e), "line": None, "symbol": None}],
            "warnings": [],
            "stage": "internal",
        }
        write_compile_error(out_dir / "compile_error.json", err_file_int)
        return {"ok": False, "error": err_file_int}
