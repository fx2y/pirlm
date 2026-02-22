# Execution Owner & Bridge (C1 Shim)

**Policy:** `scripts.pirml_run` is the single point of entry for ALL extension/toolpack/headless runs. It wraps the `pirml.ux.runtime_bridge` module.

## Flow: Single-Path Execution
1.  **Input:** User/Extension calls `python -m scripts.pirml_run --prog <prog.py> --out-dir <out_dir> ...`.
2.  **Shim (scripts.pirml_run):**
    -   Handles arg parsing (`--project-root`, `--out-dir`, `--mode`).
    -   Invokes `runtime_bridge.run_once()`.
3.  **Bridge (pirml.ux.runtime_bridge):**
    -   Generates unique `run_id` (e.g., `r177173...`).
    -   Configures `pirml.clock.SequenceClock`.
    -   Spawns `python -m pirml` as a subprocess with `PIRML_BLOCK_TOOLS=0` (unless replay).
    -   Captures `trace.ndjson` and `final.json` from `out_dir`.
    -   Emits **Exactly One** `pirml_summary` row to stdout.
4.  **Facade (pirml.ux.pointers):**
    -   `project_last_run(out_dir, project_root)` creates `.pirml/` symlinks.
    -   Ensures `.pirml/trace.ndjson`, `.pirml/final.json`, and `.pirml/artifacts` are resolvable.

## Bridge Invariant: Stdout Purity (L2)
-   `pirml` runtime (L0) stdout ONLY contains protocol rows.
-   `runtime_bridge` (L1) stdout ONLY contains the `pirml_summary` row.
-   Any diagnostics/logs MUST go to stderr.

## Failure Case: Non-Zero Exit
-   If `python -m pirml` fails (rc != 0), the bridge:
    -   Ensures `final.json` exists (even with `ok:false`).
    -   Emits a `pirml_summary` row with `ok:false`.
    -   Preserves artifacts for forensics.
