# ADR 010 Assets: Integrity & Evidence

## Contents
- `SUMMARY.md`: High-level executive summary.
- `DIAGRAMS.md`: Mermaid source and descriptions.
- `MATRIX_REF.md`: Mapping of walkthroughs to command matrix.

## Core Mandates (Spec10)
- **H22 (Single Owner):** All paths must route through the `runtime_bridge`.
- **H16 (Replay > Live):** Parity drift is a hard failure, not a warning.
- **H8 (Evidence Law):** Every run must emit resolvable pointers.

## Lifecycle
1. **Reconcile (C0):** Resolve status contradictions.
2. **Matrix (C1):** Collapse aliases into authority rows.
3. **Pack (C2):** Orchestrate evidence.
4. **Surface (C4):** Project read-only views.
5. **Close (C7):** Hard-lock winners.
