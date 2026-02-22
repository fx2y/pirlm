# CLI Toolpack Wrappers & Failure Modes (C3)

**Policy:** `pirml-open`, `pirml-slice`, and `pirml-replay` are L1 additive tools. They DO NOT modify the L0 runtime tool registry `{echo,readfile,bash}` (H7, L0).

## CLI Toolpack Contracts (L1)

### 1. `pirml-open <aid|vid|path>` (C3)
-   **Law:** Uses `ArtifactStore` to resolve IDs or file paths.
-   **Input:** Artifact ID, View ID, or filesystem path (e.g., `out/run1/final.json`).
-   **Output:** Canonical artifact/view bytes to stdout.
-   **Fail-Closed:** Emits typed `artifact_not_found` JSON error to stderr if missing.

### 2. `pirml-slice <aid|vid> <spec>` (C3)
-   **Law:** Extracts deterministic slices from ArtifactFS.
-   **Spec:** JSON `{ "op": "slice", "range": [0, 10] }`.
-   **Enforcement:** Deterministic View ID (VID) generation.
-   **Fail-Closed:** Emits typed `invalid_slice_spec` JSON error if spec malformed.

### 3. `pirml-replay <prog.py> <trace.ndjson> --out-dir <dir>` (C3)
-   **Law:** Re-executes `prog.py` using `trace.ndjson` events.
-   **Constraint:** Forces `PIRML_BLOCK_TOOLS=1` (H10, R10).
-   **Fail-Closed:** Emits typed `replay_drift` JSON error if substrate results differ.

## Shared Kernel: `scripts.tools.common` (B22)
All wrappers share a common kernel for:
-   `TypedExitException` mapping to exit codes (0/1/2).
-   `project_root` and `artifact_root` resolution (including `.pirml/artifacts` fallback).
-   Consistent `JSONL` failure envelopes to stderr.

### Typed Fail Lane Envelope (L9, RC0)
```json
{
  "k": "err",
  "type": "artifact_not_found",
  "msg": "AID 'abc' not found in art/",
  "retryable": false
}
```
-   **RC 1:** Validation/Business/Tool error.
-   **RC 2:** Integrity/Config/Internal failure.
