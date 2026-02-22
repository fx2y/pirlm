from __future__ import annotations

import ast
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from pirml.compiler.types import CompileContract, VerificationError
from pirml.runtime.policy import parse_runtime_policy_set

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
BAN_CALLS = {"eval", "exec", "compile", "__import__", "open", "print"}

# S.AST8: SERIAL_OK reason allowlist
ALLOW_SERIAL_REASONS = {"dependency_chain", "rate_limit", "ordering_required"}

CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "contracts" / "compile_contract.schema.json"
)


@lru_cache(maxsize=1)
def load_contract_schema() -> dict[str, Any]:
    raw = json.loads(CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("compile_contract.schema.json root must be object")
    return cast(dict[str, Any], raw)


class CompileVerifier:
    def __init__(self, allowed_tools: list[str]):
        self.allowed_tools = set(allowed_tools)
        self.errors: list[VerificationError] = []

    def add_error(self, code: str, msg: str, line: int | None = None, symbol: str | None = None):
        self.errors.append({"code": code, "msg": msg, "line": line, "symbol": symbol})

    def verify_contract(self, contract_src: str) -> CompileContract | None:
        """C2.T1-T3: Validate contract shape and semantics."""
        try:
            parsed = json.loads(contract_src)
        except json.JSONDecodeError as e:
            self.add_error("invalid_contract_json", str(e))
            return None

        if not isinstance(parsed, dict):
            self.add_error("invalid_contract_shape", "Root must be an object")
            return None

        data = cast(dict[str, Any], parsed)
        try:
            schema = load_contract_schema()
        except Exception as exc:
            self.add_error("contract_schema_invalid", str(exc))
            return None

        def _schema_keys(
            obj_schema: dict[str, Any], label: str
        ) -> tuple[set[str], set[str]] | None:
            req_raw_obj = obj_schema.get("required")
            if not isinstance(req_raw_obj, list):
                self.add_error("contract_schema_invalid", f"{label}.required must be list[str]")
                return None
            req_raw = cast(list[Any], req_raw_obj)
            req: set[str] = set()
            for item in req_raw:
                if not isinstance(item, str):
                    self.add_error("contract_schema_invalid", f"{label}.required must be list[str]")
                    return None
                req.add(item)

            props_raw_obj = obj_schema.get("properties")
            if not isinstance(props_raw_obj, dict):
                self.add_error("contract_schema_invalid", f"{label}.properties must be object")
                return None
            props_raw = cast(dict[str, Any], props_raw_obj)
            allowed = set(props_raw.keys())
            return req, allowed

        schema_keys = _schema_keys(schema, "root")
        if schema_keys is None:
            return None
        root_req, root_allowed = schema_keys

        schema_props = schema.get("properties")
        if not isinstance(schema_props, dict):
            self.add_error("contract_schema_invalid", "root.properties must be object")
            return None
        schema_props_dict = cast(dict[str, Any], schema_props)
        budgets_schema_obj = schema_props_dict.get("budgets")
        io_schema_obj = schema_props_dict.get("io_schema")
        if not isinstance(budgets_schema_obj, dict) or not isinstance(io_schema_obj, dict):
            self.add_error(
                "contract_schema_invalid", "root must define budgets and io_schema schemas"
            )
            return None
        budgets_schema_raw = cast(dict[str, Any], budgets_schema_obj)
        io_schema_raw = cast(dict[str, Any], io_schema_obj)

        budget_keys = _schema_keys(budgets_schema_raw, "budgets")
        io_keys = _schema_keys(io_schema_raw, "io_schema")
        if budget_keys is None or io_keys is None:
            return None
        budget_req, budget_allowed = budget_keys
        io_req, io_allowed = io_keys

        # S.CT5: Alias normalize
        if "final_schema" in data:
            io_val = data.get("io_schema")
            if isinstance(io_val, dict):
                cast(dict[str, Any], io_val).setdefault("final_schema", data.pop("final_schema"))
            else:
                # If io_schema missing or wrong type, we'll catch it in REQ check
                data.setdefault("io_schema", {})["final_schema"] = data.pop("final_schema")

        # S.CT1: Contract required keys and strict additional properties
        REQ = root_req
        actual_keys = set(data.keys())
        miss = REQ - actual_keys
        extra_keys = actual_keys - root_allowed
        if miss:
            self.add_error("contract_missing_keys", f"Missing required keys: {sorted(list(miss))}")
        if extra_keys:
            self.add_error(
                "contract_extra_keys", f"Unexpected keys in contract: {sorted(list(extra_keys))}"
            )

        # If missing critical keys, we can't continue deep validation safely
        if miss:
            return None

        # S.CT2: Budget validation (total)
        b = data["budgets"]
        if not isinstance(b, dict):
            self.add_error("invalid_budget_shape", "budgets must be an object")
        else:
            b_dict = cast(dict[str, Any], b)
            b_keys = set(b_dict.keys())
            b_miss = budget_req - b_keys
            b_extra = b_keys - budget_allowed
            if b_miss:
                self.add_error("invalid_budget", f"Missing budget keys: {sorted(list(b_miss))}")
            if b_extra:
                self.add_error("invalid_budget", f"Unexpected budget keys: {sorted(list(b_extra))}")

            for k in budget_req:
                if k in b_dict:
                    val = b_dict[k]
                    if not isinstance(val, int) or val <= 0:
                        self.add_error(
                            "invalid_budget", f"Budget {k} must be positive int", symbol=k
                        )

        # S.CT3: tool_deps subset
        deps = data["tool_deps"]
        if not isinstance(deps, list):
            self.add_error("invalid_tool_deps", "tool_deps must be a list")
        else:
            deps_list = cast(list[str], deps)
            unknown = set(deps_list) - self.allowed_tools
            if unknown:
                self.add_error("unknown_tool_deps", f"Unknown tools: {sorted(list(unknown))}")

        # S.CT4: io schema fields (total)
        io = data["io_schema"]
        if not isinstance(io, dict):
            self.add_error("invalid_io_schema_shape", "io_schema must be an object")
        else:
            io_dict = cast(dict[str, Any], io)
            io_keys = set(io_dict.keys())
            io_miss = io_req - io_keys
            io_extra = io_keys - io_allowed
            if io_miss:
                self.add_error(
                    "invalid_io_schema", f"Missing io_schema keys: {sorted(list(io_miss))}"
                )
            if io_extra:
                self.add_error(
                    "invalid_io_schema", f"Unexpected io_schema keys: {sorted(list(io_extra))}"
                )

            if "trace_ptr" in io_dict and not isinstance(io_dict["trace_ptr"], str):
                self.add_error("invalid_io_schema", "trace_ptr must be str")
            if "final_schema" in io_dict and not isinstance(io_dict["final_schema"], dict):
                self.add_error("invalid_io_schema", "final_schema must be an object")
            if "citations_schema" in io_dict and not isinstance(io_dict["citations_schema"], dict):
                self.add_error("invalid_io_schema", "citations_schema must be an object")

        # Assertions
        assertions = data["assertions"]
        if not isinstance(assertions, list):
            self.add_error("invalid_assertions", "assertions must be a list")

        declared_tools: set[str] | None = None
        if isinstance(deps, list):
            declared_tools = set()
            for item in cast(list[Any], deps):
                if isinstance(item, str):
                    declared_tools.add(item)
        budget_max_bytes_out: int | None = None
        if isinstance(b, dict):
            b_dict = cast(dict[str, Any], b)
            mbo = b_dict.get("max_bytes_out")
            if isinstance(mbo, int) and mbo > 0:
                budget_max_bytes_out = mbo

        _policy, policy_issues = parse_runtime_policy_set(
            data,
            declared_tools=declared_tools,
            budget_max_bytes_out=budget_max_bytes_out,
        )
        for issue in policy_issues:
            self.add_error(
                str(issue.get("code", "invalid_policy")),
                str(issue.get("msg", "invalid policy")),
                symbol=issue.get("symbol"),
            )

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
        parent_map = self._build_parent_map(tree)
        gather_aliases = self._collect_asyncio_gather_aliases(tree)

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

        # C2.T7: Extract TOOL_* deps and enforce awaited call shape (S.AST5)
        ast_deps: set[str] = set()
        awaited_calls: list[dict[str, Any]] = []

        for n in ast.walk(tree):
            if (
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id.startswith("TOOL_")
            ):
                tool_id = n.func.id
                ast_deps.add(tool_id[5:])
                await_node = self._find_enclosing_await(n, parent_map)
                if await_node is None:
                    self.add_error(
                        "unawaited_tool_call",
                        f"TOOL call {tool_id} must be awaited",
                        line=n.lineno,
                        symbol=tool_id,
                    )
                    continue

                assigned_target: str | None = None
                await_parent = parent_map.get(await_node)
                if (
                    isinstance(await_parent, ast.Assign)
                    and len(await_parent.targets) == 1
                    and isinstance(await_parent.targets[0], ast.Name)
                ):
                    assigned_target = await_parent.targets[0].id

                awaited_calls.append(
                    {
                        "tool": tool_id,
                        "target": assigned_target,
                        "args": n.args,
                        "keywords": n.keywords,
                        "lineno": n.lineno,
                    }
                )

        awaited_calls.sort(key=lambda row: cast(int, row["lineno"]))

        contract_tool_deps = contract.get("tool_deps") or []
        contract_deps = {t.replace(".", "_") for t in contract_tool_deps}
        if ast_deps != contract_deps:
            missing = contract_deps - ast_deps
            extra_ast = ast_deps - contract_deps
            msg: list[str] = []
            if missing:
                msg.append(f"missing in AST: {sorted(list(missing))}")
            if extra_ast:
                msg.append(f"missing in contract: {sorted(list(extra_ast))}")
            self.add_error("tool_dep_mismatch", "; ".join(msg))

        # C2.T8: Parallelism policy (S.AST6, S.AST7)
        uses_gather = any(
            isinstance(n, ast.Call) and self._is_asyncio_gather_call(n, gather_aliases)
            for n in ast.walk(tree)
        )

        def is_dependent_on_previous(
            call_b: dict[str, Any], previous_calls: list[dict[str, Any]]
        ) -> bool:
            for call_a in previous_calls:
                target_name = call_a["target"]
                if not isinstance(target_name, str):
                    continue

                for arg in call_b["args"]:
                    for sub in ast.walk(arg):
                        if isinstance(sub, ast.Name) and sub.id == target_name:
                            return True
                for kw in call_b["keywords"]:
                    for sub in ast.walk(kw.value):
                        if isinstance(sub, ast.Name) and sub.id == target_name:
                            return True
            return False

        independent_serial_calls: list[dict[str, Any]] = []
        for idx, call in enumerate(awaited_calls):
            if idx == 0:
                continue
            if not is_dependent_on_previous(call, awaited_calls[:idx]):
                independent_serial_calls.append(call)

        if len(awaited_calls) > 1 and not uses_gather and independent_serial_calls:
            # Check for SERIAL_OK (S.AST7)
            serial_reason = self._extract_serial_reason(prog_src)
            found_valid_reason = serial_reason in ALLOW_SERIAL_REASONS

            if not found_valid_reason:
                if serial_reason is not None:
                    self.add_error(
                        "invalid_serial_reason", "SERIAL_OK: found but reason is not in allowlist"
                    )
                else:
                    self.add_error(
                        "missing_gather",
                        "Independent tool calls found without asyncio.gather() or SERIAL_OK: escape",
                    )

    def _build_parent_map(self, tree: ast.AST) -> dict[ast.AST, ast.AST]:
        parent_map: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent_map[child] = node
        return parent_map

    def _find_enclosing_await(
        self, node: ast.AST, parent_map: dict[ast.AST, ast.AST]
    ) -> ast.Await | None:
        current: ast.AST | None = node
        while current is not None:
            if isinstance(current, ast.Await):
                return current
            current = parent_map.get(current)
        return None

    def _collect_asyncio_gather_aliases(self, tree: ast.AST) -> set[str]:
        aliases: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "asyncio":
                for alias in node.names:
                    if alias.name == "gather":
                        aliases.add(alias.asname or alias.name)
        return aliases

    def _is_asyncio_gather_call(self, node: ast.Call, gather_aliases: set[str]) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute):
            return (
                isinstance(func.value, ast.Name)
                and func.value.id == "asyncio"
                and func.attr == "gather"
            )
        if isinstance(func, ast.Name):
            return func.id in gather_aliases
        return False

    def _extract_serial_reason(self, prog_src: str) -> str | None:
        for line in prog_src.splitlines():
            if "SERIAL_OK:" in line:
                parts = line.split("SERIAL_OK:", 1)
                if len(parts) < 2:
                    return ""
                reason_tokens = parts[1].strip().split()
                if not reason_tokens:
                    return ""
                return reason_tokens[0]
        return None


def verify_compile_output(
    prog_src: str, contract_src: str, allowed_tools: list[str]
) -> tuple[CompileContract | None, list[VerificationError]]:
    v = CompileVerifier(allowed_tools)
    contract = v.verify_contract(contract_src)
    if contract:
        v.verify_ast(prog_src, contract)
    return contract, v.errors
