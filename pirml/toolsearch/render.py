from __future__ import annotations

from typing import Any

from pirml.contracts.schemas import ToolManifest


class RenderError(Exception):
    def __init__(self, type: str, msg: str):
        self.type = type
        self.msg = msg
        super().__init__(f"{type}: {msg}")


def render_selected_tools(tools: list[ToolManifest]) -> list[dict[str, Any]]:
    """C3.T3: Pure renderer returning [{name,description,input_schema,input_examples}] for selected tools only."""
    rendered: list[dict[str, Any]] = []
    for tool in tools:
        row: dict[str, Any] = {
            "name": tool.get("name", ""),
            "description": tool.get("description", ""),
            "input_schema": tool.get("input_schema", {}),
        }
        # input_examples is optional in ToolManifest schema
        if "input_examples" in tool:
            row["input_examples"] = tool["input_examples"]
        rendered.append(row)
    return rendered


def enforce_client_search_mode(use_server_search: bool, include_examples: bool) -> None:
    """C3.T4: Hard guard: if examples enabled then forbid server-side ToolSearch mode.
    G.P2.1: API refined to use explicit flag.
    """
    if use_server_search and include_examples:
        raise RenderError(
            "invalid_policy_combo",
            "ToolSearch incompatible with tool use examples.",
        )


def enforce_client_search_mode_compat(server_side_search: bool, tools: list[ToolManifest]) -> None:
    """Legacy wrapper for C3.T4 contract."""
    include_examples = any("input_examples" in tool for tool in tools)
    enforce_client_search_mode(server_side_search, include_examples)
