from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from pirml.contracts.schemas import ErrorObject, ToolManifest

# Alias for consistent naming as per spec-04
CompileErr = ErrorObject


class ContractBudget(TypedDict, total=False):
    max_calls: int
    max_parallel: int
    max_bytes_in: int
    max_bytes_out: int
    timeout_s: int


class CompileContract(TypedDict, total=False):
    tool_deps: List[str]
    io_schema: Dict[str, Any]
    budgets: ContractBudget
    assertions: List[str]
    trace_ptr: str


class CompileArtifacts(TypedDict, total=False):
    prog_src: str
    contract: CompileContract
    raw_text: str


class CompileInput(TypedDict, total=False):
    task: str
    tools: List[ToolManifest]
    budgets: ContractBudget
    env: Dict[str, Any]


class CompileOutput(TypedDict, total=False):
    ok: bool
    artifacts: CompileArtifacts
    error: CompileErr
