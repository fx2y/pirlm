# Cycle 4: Compiler L1 Module Map

| Module | Responsibility | Invariants |
| :--- | :--- | :--- |
| `pirml.compiler.compile` | Orchestrator / CLI API | Exactly one branch: `{prog,contract}` or `{error}` |
| `pirml.compiler.extract` | Sentinel / Prose stripping | Cardinality=5; leading/trailing prose hard-fail |
| `pirml.compiler.verify` | Schema + AST enforcement | Import allowlist; awaited `TOOL_*`; `send_final` exactly 1 |
| `pirml.compiler.smoke` | Deterministic budget harness | Sequence clock; `max_calls/parallel/bytes/timeout` |
| `pirml.compiler.repair` | Syntax-preserving fix-up | Sentinel whitespace; missing optional fields; no semantics |
| `pirml.compiler.model` | Model adapter factory | `StubModelAdapter` for CI/unit parity |
| `scripts.compile` | CLI entrypoint | RC 0/1/2 mapping; status to stderr |
| `scripts.schema_lint` | Multi-artifact validation | Explicit input args only; missing required = fail |
