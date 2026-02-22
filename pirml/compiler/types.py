from __future__ import annotations

from typing import Any, TypedDict

from pirml.contracts.schemas import ErrorObject, ToolManifest

# Alias for consistent naming as per spec-04
CompileErr = ErrorObject


class VerificationError(TypedDict, total=False):
    code: str
    msg: str
    line: int | None
    symbol: str | None


class CompileErrorFile(TypedDict):
    ok: bool
    errors: list[VerificationError]
    warnings: list[VerificationError]
    stage: str


class ContractBudget(TypedDict):
    max_calls: int
    max_parallel: int
    max_bytes_in: int
    max_bytes_out: int
    timeout_s: int


class ContractRetryPolicy(TypedDict):
    n: int


class ContractToolPolicy(TypedDict, total=False):
    idempotent: bool
    cacheable: bool
    max_payload_bytes: int
    timeout_s: float
    retry: ContractRetryPolicy


class ContractTimeouts(TypedDict, total=False):
    default_s: float
    tool_overrides: dict[str, float]


class CompileContract(TypedDict, total=False):
    tool_deps: list[str]
    io_schema: dict[str, Any]
    budgets: ContractBudget
    assertions: list[str]
    artifact_writes: list[str]
    tool_policies: dict[str, ContractToolPolicy]
    timeouts: ContractTimeouts


class CompileArtifacts(TypedDict):
    prog_src: str
    contract: CompileContract
    raw_text: str


class CompileInput(TypedDict):
    task: str
    tools: list[ToolManifest]
    budgets: ContractBudget
    env: dict[str, Any]


class CompileOutput(TypedDict, total=False):
    ok: bool
    artifacts: CompileArtifacts
    error: CompileErr | CompileErrorFile
