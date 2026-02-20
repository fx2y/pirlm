from __future__ import annotations

import json
from typing import Any

from pirml.compiler.types import ContractBudget


def build_compile_prompt(
    task: str,
    tools: list[dict[str, Any]],
    budgets: ContractBudget,
    env: dict[str, Any] | None = None,
) -> str:
    """C1.T4: Build compiler prompt with strict directives and sentinels."""
    tool_names = [t.get("name", "") for t in tools]
    tool_names_csv = ", ".join(tool_names)

    # T3 PROMPT_HDR
    header = (
        "You output ONLY 2 blocks with sentinels: <<<PROG>>> python then <<<CONTRACT>>> json.\n"
        "No markdown. No commentary. Code must run on py3.12 stdlib only.\n"
        "All tool calls are async + awaited. Use asyncio.gather for independent calls.\n"
        "Print exactly one final JSON object matching final_schema."
    )

    # T4 PROMPT_TOOLSET
    toolset = (
        f"Allowed tools (exact names): {tool_names_csv}. Do not invent tools.\n"
        "Use only provided input_examples; follow conventions from examples."
    )

    # T5 PROMPT_BUDGETS
    n = budgets.get("max_calls", 40)
    p = budgets.get("max_parallel", 10)
    bi = budgets.get("max_bytes_in", 5000000)
    bo = budgets.get("max_bytes_out", 200000)
    t = budgets.get("timeout_s", 60)
    budget_directives = (
        f"Budgets: max_calls={n}, max_parallel={p}, max_bytes_in={bi}, max_bytes_out={bo}, timeout_s={t}.\n"
        "If uncertain: reduce calls, reuse cached artifacts, early-stop."
    )

    # assemble tools block
    tools_block = "TOOLS:\n"
    for tool in tools:
        # Use canonical JSON for schemas/examples in prompt
        tools_block += f"- name: {tool.get('name')}\n"
        tools_block += f"  description: {tool.get('description')}\n"
        tools_block += f"  input_schema: {json.dumps(tool.get('input_schema', {}))}\n"
        if "input_examples" in tool:
            tools_block += f"  input_examples: {json.dumps(tool['input_examples'])}\n"
        tools_block += "\n"

    prompt = f"{header}\n\n{toolset}\n\n{budget_directives}\n\n{tools_block}TASK:\n{task}"
    return prompt
