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


def enforce_client_search_mode(server_side_search: bool, tools: list[ToolManifest]) -> None:
    """C3.T4: Hard guard: if examples enabled then forbid server-side ToolSearch mode."""
    if server_side_search and any("input_examples" in tool for tool in tools):
        raise RenderError(
            "invalid_policy_combo",
            "ToolSearch incompatible with tool use examples.",
        )
