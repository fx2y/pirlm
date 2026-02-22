# ArtifactFS + RLM Workflow

```mermaid
graph TD
    A[Input Bytes] -->|sha256| B(ArtifactStore)
    B -->|aid| C{View Spec}
    C -->|vid| D[ViewMaterializer]
    D -->|streaming| E(art/views/vid.ndjson)
    E --> F[RlmKernel REPL]
    F -->|llm_query| G(Recursive Summary)
    G -->|put_art| B
    F -->|Final| H[Project Answer]
    H -->|pack_ctx| I[Governed Output]
    I --> J[Citation Map]
    
    subgraph "Substrate (L0)"
        K[Protocol Algebra]
        L[Tool Surface]
    end
    
    subgraph "Recursive Layer (L1)"
        B
        D
        F
    end
    
    subgraph "Gate Ladder (G)"
        M[fast] --> N[ci] --> O[replay]
    end
```

## View DSL Examples

### Lines Slice
```json
{
  "op": "lines",
  "a": 0,
  "b": 100
}
```

### Regex Slice
```json
{
  "op": "regex",
  "pat": "ERROR|FATAL",
  "max_hits": 50
}
```

### HTML to Text
```json
{
  "op": "html_text",
  "drop": ["script", "style", "noscript"],
  "max_chars": 200000
}
```
