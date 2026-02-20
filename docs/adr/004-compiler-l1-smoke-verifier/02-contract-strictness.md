# Cycle 4: Contract Strictness (C2)

## Schema-Backed Verifier
The verifier is **fail-closed** against `pirml/contracts/compile_contract.schema.json`.
- **Constraint**: `additionalProperties: false` is enforced for all objects.
- **Normalization**: Fields such as `final_schema` and `io_schema` are normalized before hashing or writing.
- **Typed Errors**: Validation failures emit a list of `{code, msg, line, symbol}`.

## AST Verification
The verifier performs structural analysis of the generated code via `ast.NodeVisitor`:
- **Imports**: Rejects any import not in `ALLOWED_IMPORTS` (e.g., `os`, `sys`, `requests`).
- **Calls**:
  - `send_final` must be called exactly once.
  - `TOOL_*` calls must be wrapped in `await`.
  - `print()` is forbidden (stdout-chatter rule).
- **Structure**: Program must define `async def main()` and be executed via `asyncio.run(main())`.
- **Parallelism**: Mandatory `asyncio.gather` for independent tool calls. Serial calls are only permitted with a valid `SERIAL_OK` reason (e.g., `dependency_chain`).

## Repair Policy
Repair is restricted to **syntax-preserving** actions:
- Fixing sentinel whitespace.
- Canonicalizing `io_schema.final_schema` alias.
- Injecting missing optional fields (e.g., empty `assertions`).
- **Rejection**: Semantic synthesis (e.g., inventing `tool_deps` or `budgets`) is strictly forbidden and results in `repair_declined`.
