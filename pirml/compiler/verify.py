from __future__ import annotations

import ast
import json
from typing import cast

from pirml.compiler.types import CompileContract, VerificationError

# S.AST1: Import allowlist
ALLOW_IMPORTS = {
    "asyncio",
    "json",
    "re",
    "math",
    "statistics",
    "datetime",
    "html.parser",
    "urllib.parse",
    "pirml.runtime.rpc",
}

# S.AST2: Banned calls
BAN_CALLS = {"eval", "exec", "compile", "__import__", "open"}

# S.AST8: SERIAL_OK reason allowlist
ALLOW_SERIAL_REASONS = {"dependency_chain", "rate_limit", "ordering_required"}


class CompileVerifier:
    def __init__(self, allowed_tools: list[str]):
        self.allowed_tools = set(allowed_tools)
        self.errors: list[VerificationError] = []

    def add_error(self, code: str, msg: str, line: int | None = None, symbol: str | None = None):
        self.errors.append({"code": code, "msg": msg, "line": line, "symbol": symbol})

    def verify_contract(self, contract_src: str) -> CompileContract | None:
        """C2.T1-T3: Validate contract shape and semantics."""
        try:
            data = json.loads(contract_src)
        except json.JSONDecodeError as e:
            self.add_error("invalid_contract_json", str(e))
            return None

        # S.CT5: Alias normalize
        if "final_schema" in data:
            data.setdefault("io_schema", {})["final_schema"] = data.pop("final_schema")

        # S.CT1: Contract required keys
        REQ = {"tool_deps", "io_schema", "budgets", "assertions"}
        miss = REQ - set(data.keys())
        if miss:
            self.add_error("contract_missing_keys", f"Missing required keys: {sorted(list(miss))}")
            return None

        # Validate against schema (simplified here as per S.CT2-S.CT4)
        # S.CT2: Budget key check
        b = data["budgets"]
        for k in ["max_calls", "max_parallel", "max_bytes_in", "max_bytes_out", "timeout_s"]:
            val = b.get(k)
            if not isinstance(val, int) or val <= 0:
                self.add_error("invalid_budget", f"Budget {k} must be positive int", symbol=k)

        # S.CT3: tool_deps subset
        deps = data.get("tool_deps", [])
        unknown = set(deps) - self.allowed_tools
        if unknown:
            self.add_error("unknown_tool_deps", f"Unknown tools: {sorted(list(unknown))}")

        # S.CT4: io schema fields
        io = data["io_schema"]
        if not isinstance(io.get("trace_ptr"), str):
            self.add_error("invalid_io_schema", "trace_ptr must be str")
        if "final_schema" not in io:
            self.add_error("invalid_io_schema", "final_schema missing")
        if "citations_schema" not in io:
            self.add_error("invalid_io_schema", "citations_schema missing")

        if self.errors:
            return None

        return cast(CompileContract, data)

    def verify_ast(self, prog_src: str, contract: CompileContract):
        """C2.T4-T8: Enforce AST policies."""
        try:
            tree = ast.parse(prog_src)
        except SyntaxError as e:
            self.add_error("syntax_error", str(e), line=e.lineno)
            return

        # C2.T4: Import allowlist
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    if alias.name not in ALLOW_IMPORTS:
                        self.add_error(
                            "ast_import_denied",
                            f"Import {alias.name} not allowed",
                            line=n.lineno,
                            symbol=alias.name,
                        )
            if isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                # Check if the module or sub-module is allowed
                if mod not in ALLOW_IMPORTS and not any(
                    mod.startswith(a + ".") for a in ALLOW_IMPORTS
                ):
                    self.add_error(
                        "ast_import_denied",
                        f"Import from {mod} not allowed",
                        line=n.lineno,
                        symbol=mod,
                    )

        # C2.T5: Banned calls (S.AST2)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in BAN_CALLS:
                self.add_error(
                    "banned_call", f"Call to {n.func.id} is banned", line=n.lineno, symbol=n.func.id
                )

        # C2.T6: Single async main (S.AST3)
        m = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "main"]
        if len(m) != 1:
            self.add_error(
                "missing_async_main", f"Exactly one async def main() required, found {len(m)}"
            )

        # C2.T6: Single send_final (S.AST4)
        emit = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "send_final"
        ]
        if len(emit) != 1:
            self.add_error(
                "invalid_final_emit", f"Exactly one send_final() required, found {len(emit)}"
            )

        # C2.T7: Extract awaited TOOL_* deps (S.AST5)
        ast_deps = {
            n.func.id[5:]
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id.startswith("TOOL_")
        }
        contract_deps = {t.replace(".", "_") for t in contract["tool_deps"]}
        if ast_deps != contract_deps:
            missing = contract_deps - ast_deps
            extra = ast_deps - contract_deps
            msg: list[str] = []
            if missing:
                msg.append(f"missing in AST: {sorted(list(missing))}")
            if extra:
                msg.append(f"missing in contract: {sorted(list(extra))}")
            self.add_error("tool_dep_mismatch", "; ".join(msg))

        # C2.T8: Parallelism policy (S.AST6, S.AST7)
        uses_gather = any(
            isinstance(n, ast.Attribute) and n.attr == "gather" for n in ast.walk(tree)
        )
        # Simple fanout check: more than one await call in main?
        # Actually S.AST6 just checks for 'gather' attribute.
        # Let's check if there are multiple awaited tool calls and no gather.

        tool_call_nodes = [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Await)
            and isinstance(n.value, ast.Call)
            and isinstance((f := n.value.func), ast.Name)
            and f.id.startswith("TOOL_")
        ]

        if len(tool_call_nodes) > 1 and not uses_gather:
            # Check for SERIAL_OK (S.AST7)
            if "SERIAL_OK:" not in prog_src:
                self.add_error(
                    "missing_gather",
                    "Multiple tool calls found without asyncio.gather() or SERIAL_OK: escape",
                )
            else:
                # C2.T8: Check reason (S.AST8)
                # This is a bit crude, we just check if any line has SERIAL_OK: with a valid reason
                found_valid_reason = False
                for line in prog_src.splitlines():
                    if "SERIAL_OK:" in line:
                        reason = line.split("SERIAL_OK:", 1)[1].strip().split()[0]  # get first word
                        if reason in ALLOW_SERIAL_REASONS:
                            found_valid_reason = True
                            break
                if not found_valid_reason:
                    self.add_error(
                        "invalid_serial_reason", "SERIAL_OK: found but reason is not in allowlist"
                    )


def verify_compile_output(
    prog_src: str, contract_src: str, allowed_tools: list[str]
) -> tuple[CompileContract | None, list[VerificationError]]:
    v = CompileVerifier(allowed_tools)
    contract = v.verify_contract(contract_src)
    if contract:
        v.verify_ast(prog_src, contract)
    return contract, v.errors
