# ADR 006: ArtifactFS + RLM Substrate (L1)

## Context
Bulk context (10MB+ hostile data) crashes standard LLM windows. Linear context growth leads to "lost in the middle" and quadratic cost. **Recursive Language Models (RLM)** and **ArtifactFS** enable 100x context reach by moving intermediate reasoning off-context into immutable handles.

## Decisions

### 1. Plane Split (L0/L1/G)
- **L0 (Substrate):** Frozen tool surface `{echo,readfile,bash}` and protocol `{call,result,final,custom}`.
- **L1 (Additive):** `ArtifactStore` (CAS), `ViewMaterializer` (DSL), `RlmKernel` (Recursion).
- **G (Gates):** Authority is `mise run ci`; `fast` is <3s reject signal.

### 2. ArtifactFS (Content-Addressable Storage)
- **Storage Law:** ID = `sha256(bytes)`; Path = `obj/aa/bb/<id>`. Immutable; no in-place mutation.
- **Index (SQLite):** Metadata-only cache (id, kind, mime, size, parents, src). Disposable/Forensic.
- **Trace (NDJSON):** Append-only durable ledger of all `put/view` events. Source of truth for index rebuild.

### 3. View Engine (Deterministic Slicing)
- **View ID:** `sha256(artifact_id | canonical_json(spec))`. Stable across runs.
- **Materialization:** Iterative stream feeding (max 10MB/s) to `art/views/<vid>.ndjson`.
- **Slice Ops:** `lines`, `bytes`, `regex`, `html_text` (stdlib-only; no BS4).

### 4. RLM Kernel (No-Ctx-Bloat Recursion)
- **History Law:** REPL iter appends only `Metadata(stdout)` (prefix+len). Forces reliance on state vars/artifacts.
- **Stop Condition:** Exactly one `Final` sentinel in state. Missing => typed fail.
- **Budget Governor:** Warning >20 subcalls, Hard-fail >200. Token estimation = `(len+2)//3` (upper bound).

### 5. Context Governor (K-Cap Selection)
- **Hard Cap K:** Context builder never exceeds K tokens.
- **Selection Policy:** Maximize `(relevance / cost)` + mandatory `Prompt/P` anchors.
- **Cohesion Rule:** Never cut between `call` and `result`; atomicity or omission.

### 6. Protocol Evolution (Algebra C6)
- **Ratified Ops:** `{call, result, final, custom}`.
- **Custom Op:** Persists pi-pointers (lineage, replay) without context injection. Redacted and hashed like L0 ops.

## Consequences
- **Zero Ctx Bloat:** Model handles 10MB+ inputs while seeing constant-size metadata.
- **Deterministic Replay:** Rebuild index from trace; vid stability ensures replay-parity.
- **Fail-Closed:** Unknown ops/specs/configs => typed failures (`type, msg, retryable`).

## Walkthroughs

### ArtifactFS Layout
```text
out/
└── run/
    ├── obj/aa/bb/<sha256>   (CAS Blobs)
    ├── views/<vid>.ndjson   (Slices)
    ├── trace.ndjson         (Ledger)
    └── index.sqlite         (Metadata Cache)
```

### RLM Loop Logic
```python
while not state["Final"]:
    code = model(hist)
    stdout = repl(state, code)
    hist.append({"code": code, "stdout": {"len": len(stdout), "prefix": stdout[:200]}})
```

### Invariant Proof Matrix
| Invariant | Proof Command |
| :--- | :--- |
| **CAS Dedupe** | `tests.test_artifact_fs::test_same_bytes_same_id` |
| **Budget Fail** | `tests.test_rlm_kernel::test_rlm_subcall_budget` |
| **K-Cap Bound** | `tests.test_spec06_c5_governor::test_governor_hard_cap_enforcement` |
| **Replay Parity** | `python -m scripts.replay_check` |
| **Schema Gate** | `python -m scripts.schema_lint --artifact ...` |

## Status
**Ratified** (2026-02-21)
