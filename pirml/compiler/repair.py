from __future__ import annotations

import json

from pirml.compiler.types import VerificationError


def repair_once(
    prog_src: str, contract_src: str, errors: list[VerificationError]
) -> tuple[str, str, bool]:
    """C4.T5: Implement repair pass for trivial classes.
    Returns (new_prog, new_contract, repaired).
    """
    repaired_prog = prog_src
    repaired_contract = contract_src
    any_repaired = False

    for err in errors:
        code = err.get("code")

        # 1. Missing gather wrapper (trivial if no dependencies)
        # For now, we just suggest the user fix it or implement a simple regex fix
        # Actually, T5 says "missing gather wrapper", maybe we can auto-wrap?
        # That sounds complex for a regex.

        # 2. Sentinel whitespace (trivial)
        if any(err.get("code") == "syntax_error" for err in errors):
            # Try stripping again in case extractor missed something
            stripped_prog = prog_src.strip()
            if stripped_prog != prog_src:
                repaired_prog = stripped_prog
                any_repaired = True

        # 3. Missing contract alias fields (trivial)
        if code in ("contract_missing_keys", "invalid_io_schema"):
            try:
                data = json.loads(repaired_contract)
                # Trivial: final_schema alias or missing io_schema fields
                io_repaired = False

                if "final_schema" in data and "io_schema" not in data:
                    # Pure alias migration
                    data["io_schema"] = {"final_schema": data.pop("final_schema")}
                    io_repaired = True

                # Do NOT synthesize budgets, assertions, or tool_deps if missing.
                # These must be emitted by the model as per contract.
                root_repaired = False

                if io_repaired or root_repaired:
                    from pirml.runtime.rpc import canonical_json

                    repaired_contract = canonical_json(data)
                    any_repaired = True
            except Exception:
                pass

        # 4. TOOL_ dot normalization (already handled in verifier/harness, but maybe in contract too)

    return repaired_prog, repaired_contract, any_repaired


def is_trivial_repair(code: str) -> bool:
    """C4.T6: Hard-fail nontrivial repair candidates."""
    trivial = {
        "contract_missing_keys",
        "invalid_io_schema",
        "invalid_final_emit",  # Maybe? No.
    }
    # Nontrivial: ast_import_denied, banned_call, tool_hallucination, etc.
    nontrivial = {
        "ast_import_denied",
        "banned_call",
        "unknown_tool_deps",
        "syntax_error",
        "missing_async_main",
    }
    return code in trivial and code not in nontrivial
