# Observability Pointers & Context Hygiene (C2)

**Goal:** Provide operator-grade observability into PiRLM runs (pi extension) without polluting LLM context (H8, L7).

## Pointer Payload Law (L7, X2)
The **CustomEntry** `data` field is the source of truth for observability. It is NOT visible to the LLM during normal operation.

### CustomEntry Schema (Bet A/B)
```json
{
  "type": "custom",
  "customType": "pirml",
  "data": {
    "runId": "r1771731868288",
    "trace": "out/r1771731868288/trace.ndjson",
    "final": "out/r1771731868288/final.json",
    "artifactsDir": "art",
    "roots": ["out/r1771731868288/final.json", ".pirml/final.json"],
    "runSha": "sha256(final_bytes)",
    "ts": "SequenceClock:177173..."
  },
  "parentId": "p123" 
}
```

### Context-Visible: CustomMessage (X2)
The **CustomMessage** `content` is visible to the LLM. It is strictly limited to human hints.

**Bad (Context-Polluting):**
`content: "PIRML run r1 complete. Result: { 'answer': 'Paris', 'citations': [...] }"`

**Good (Clean Context):**
`content: "PIRML r1 OK (1.2s)"`

### Branch Safety (F7)
-   `parentId` in `CustomEntry` ensures that the run state rewinds correctly with pi's `/tree` or `/fork`.
-   Avoid global mutable singletons for "active run" state.
-   The `.pirml/` facade is a **convenience projection only** (H23).

## Resolvability: The Artifacts Link
The `artifactsDir` pointer (e.g., `art`) is resolvable via the project root or the `.pirml/artifacts` symlink.
-   `scripts.tools.open` resolves paths via `ArtifactStore.from_root(project_root)`.
-   `schema_lint` verifies `trace_ptr` resolvability (I14).
