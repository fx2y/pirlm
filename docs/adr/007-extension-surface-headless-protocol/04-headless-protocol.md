# Headless Protocol & JSON Event Stream (Bet C)

**Goal:** Enable reproducible, headless PiRLM runs (CI/headless) via a standardized JSON event stream.

## Headless JSON Orchestrator (C5)

### Command Pattern (Bet C)
```bash
PIRML_ENABLE_JSON_HEADLESS=1 python -m pirml.ux.headless --out-dir out/headless1
```
The orchestrator consumes JSON rows from stdin and executes `run_once()`.

### Event Parser: Input Events (C5)
-   `tool_execution_start`: Ignored (runtime already handles L0 tool calls).
-   `tool_execution_end`: Ignored.
-   `turn_start`: Triggers a new PiRLM execution cycle.
-   `turn_end`: Terminates the orchestrator.

### Protocol Purity: Stdout Summary Rows (C5)
The orchestrator emits exactly ONE `pirml_summary` row per `turn_start` to stdout.
-   **Law:** Stdout remains a machine-readable protocol stream.
-   **Diagnostic:** Errors and exceptions are emitted to stderr as typed JSON rows.

## RE-Injection Stub (L10)
-   PiRLM results (answer/citations/trace_ptr) can be re-injected into the session via the `SDK` or `RPC` mode.
-   Current implementation (C5) stubs the re-injection path with a typed `not_implemented` error to maintain fail-closed integrity.

## Fail-Closed Integration (L9)
If `PIRML_ENABLE_JSON_HEADLESS=0` (default):
-   The orchestrator emits a `feature_disabled` row.
-   Exit code is `1` (business/tool failure).
-   Prevents accidental, non-reproducible runs in CI.

### Headless Error Envelope (L9)
```json
{
  "k": "err",
  "type": "feature_disabled",
  "msg": "Headless mode requires PIRML_ENABLE_JSON_HEADLESS=1",
  "retryable": false
}
```
