# ADR 007: Extension Surface & Headless Protocol

**Status:** Accepted (2026-02-22)  
**Scope:** Spec-07 (L1 UX + Observability + Toolpack)  
**Constitutional Priority:** H0, H4, H7, H16, H22 (L0 freeze; single owner; protocol purity)

## Context
L0 (runtime/replay/tool/channel) is frozen. Spec-07 must deliver "PiRLM-Fabric" UX (pi extension + pointers-only observability + toolpack) as additive L1 adapters. Any substrate mutation is a defect.

## Decision: The L1 "Bridge" Architecture

### 1. Single Execution Owner (H22)
**Law:** `scripts.pirml_run` (Shim) -> `pirml.ux.runtime_bridge` -> `python -m pirml`.  
- **Rationale:** Prevents path/env/timeout drift across extension, toolpack, and CLI.
- **Enforcement:** `tests/test_spec07_c1_runtime_shim.py`.

### 2. .pirml Projection Facade (H23)
**Law:** `.pirml/` is a non-destructive symlink projection of `out/<run>/` + `art/`.  
- **Safety:** Never `rmtree` pre-existing non-projection dirs.
- **Fallback:** Use absolute path symlinks if project root != cwd.

### 3. Pointer Payload Law (L7, X2)
**Law:** Rich metadata (runId, trace, final, artifactsDir, runSha) MUST live in `CustomEntry.data`.  
- **Constraint:** `CustomMessage.content` (context-visible) is hard-capped at 120 chars (human hint only).
- **Goal:** Zero context pollution; lineage survives branch/compaction.

### 4. CLI Toolpack (L0, G15)
**Law:** `pirml-{open,slice,replay}` are external scripts; zero runtime tool growth.
- **Shared Kernel:** `scripts.tools.common` handles typed JSON failures + artifact-root resolution.

### 5. Headless JSON Orchestrator (Bet C)
**Law:** `pirml.ux.headless` consumes JSON events (stdin), emits `pirml_summary` rows (stdout).
- **Fail-Closed:** Feature-gated by `PIRML_ENABLE_JSON_HEADLESS=1`.

## Logic Flow
```text
[Operator/LLM]
      |
  [pi Command / Tool]
      |
  [.pi/extensions/pirml/spawn.ts]
      |
  [scripts.pirml_run] (C1 Shim)
      |
  [pirml.ux.runtime_bridge] (Protocol Guard)
      |
  [python -m pirml] (L0 Runtime)
      |
  [out/<run>/ + art/] (Storage Truth)
      |
  [.pirml/] (Facade) -> [Session Entry] (Pointer)
```

## Walkthroughs

### W1: Run + Observe (Bet A)
```bash
/pirml run tests/prog_ok.py --out-dir out/run1
# 1. Scripts.pirml_run executes
# 2. .pirml facade links to out/run1
# 3. CustomEntry(data={trace:"out/run1/trace.ndjson", ...}) appended
# 4. Operator uses /tree to jump; pointers resolve via .pirml/ artifacts link
```

### W2: Toolpack Triage (C3)
```bash
python -m scripts.tools.replay tests/prog_ok.py .pirml/trace.ndjson --out-dir out/replay1
# 1. Resolves .pirml/trace.ndjson -> out/run1/trace.ndjson
# 2. Runs --replay contract with PIRML_BLOCK_TOOLS=1
# 3. Emits typed JSON failure if trace missing
```

## Invariant Ledger
| ID | Constraint | Locus | Proof |
|:---|:---|:---|:---|
| I02 | Shim delegates to `python -m pirml` | `pirml/ux/runtime_bridge.py` | `tests.test_spec07_c1_runtime_shim` |
| I04 | Projection is non-destructive | `pirml/ux/pointers.py` | `tests.test_spec07_c1_runtime_shim` |
| I06 | Payload in CustomEntry data | `extension/pointers.ts` | `npx tsx tests/test_spec07_c2_extension_contract.ts` |
| I19 | Stdout protocol purity | `pirml/ux/headless.py` | `tests.test_spec07_c5_headless` |

## Consequences
- **Positive:** Full replayability of UX actions; clean LLM context; zero substrate risk.
- **Neutral:** Operator must use `scripts.pirml_run` instead of direct `pirml.runtime.exec`.
- **Negative:** Dual-language (TS/Python) maintenance for extension bridge.
