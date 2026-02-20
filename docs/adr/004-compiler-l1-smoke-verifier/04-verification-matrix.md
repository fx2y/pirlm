# Cycle 4: Verification Matrix

| Invariant | Test | Gate Locus | Artifact Proof |
| :--- | :--- | :--- | :--- |
| **B0**: Sentinel framing / Cardinality=5 | `tests.test_compile_extract` | `compile.py#extract` | `out/raw.txt` vs `prog.py` |
| **B1**: Contract strictness / Schema-backed | `tests.test_compile_verify` | `verify.py#verify_contract` | `out/contract.json` vs `schema` |
| **B2**: AST / Imports / Tool discipline | `tests.test_compile_verify` | `verify.py#verify_ast` | `out/compile_error.json` [FAIL_B2_*] |
| **B3**: Smoke budgets / Timeout / Final | `tests.test_compile_smoke` | `smoke.py#harness` | `out/smoke_trace.ndjson` |
| **Compile Golden Parity** | `tests.test_compile_golden` | `unit` stage | `tests/golden/compile/*` bytes |
| **Runtime Protocol Algebra/ID/Order** | `tests.test_protocol` | `proto` stage | `scripts.proto_lint` |
| **Runtime Trace Envelope/Hash** | `tests.test_c4_observability` | `trace` stage | `scripts.trace_lint` |
| **Replay Parity / No-Tools** | `tests.test_replay` | `replay` stage | `scripts.replay_check` |
| **Schema Boundary Strictness** | `tests.test_schema_lint` | `schemas` stage | `scripts.schema_lint` (explicit args) |
| **Repair Policy (Syntax-only)** | `tests.test_compile_verify` | `repair.py` | `out/contract.json` (fixed whitespace) |
| **Deterministic x3 (Smoke Trace)** | `tests.test_compile_smoke` | `unit` stage | `sha256(smoke_trace)` parity |
