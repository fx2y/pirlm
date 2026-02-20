# Cycle 4: Smoke Determinism & Budgets (C3)

## Deterministic Harness
The smoke harness enforces **sequence-based determinism** to satisfy `trace_lint` without relying on the system clock:
- **Clock**: `seq_ms` starts at `1000`, increments by `100` per op.
- **IDs**: `c00001`, `c00002`, ... monotonic per run.
- **Trace**: Every run (including fails) emits `smoke_trace.ndjson` to `out/<run>/`.
- **Validation**: Smoke traces must pass `trace_lint` and `proto_lint` (closed algebra: `call|result|final`).

## Budget Probes
The harness monitors runtime behavior and enforces constraints from `contract.json`:
- **`max_calls`**: Total count of `TOOL_*` calls.
- **`max_parallel`**: Concurrent `TOOL_*` calls (using `asyncio.gather`).
- **`max_bytes_in`**: Total JSON bytes of `TOOL_*` arguments.
- **`max_bytes_out`**: Total JSON bytes of `TOOL_*` results.
- **`timeout_s`**: Subprocess timeout via `subprocess.run(..., timeout=...)`.

## Error Mapping
Smoke failures are mapped to stable `FAIL_B3_*` codes in `compile_error.json`:
- `FAIL_B3_CALL_BUDGET`
- `FAIL_B3_PARALLEL_BUDGET`
- `FAIL_B3_BYTES_BUDGET`
- `FAIL_B3_TIMEOUT`
- `FAIL_B3_STDOUT_CHATTER` (non-proto chatter detection)
- `FAIL_B3_NO_FINAL` (missing `send_final`)
- `FAIL_B3_MULTI_FINAL` (multiple `send_final`)

## Deterministic x3 Proof
Any change to the smoke harness requires a **Deterministic x3 proof**:
- Running the same program + contract 3 times results in byte-identical `smoke_trace.ndjson`.
- Verified via `tests.test_compile_smoke.TestCompileSmokeManifest.test_smoke_trace_deterministic_x3`.
