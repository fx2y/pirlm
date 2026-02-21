# ADR 005: Schema Validation & Gate Ladder

## `schema_lint` Protocol
```sh
# Explicit paths only (H14 enforcement)
python -m scripts.schema_lint 
  --web-output out/web_smoke/web_output.json 
  --web-trace out/web_smoke/web_trace.ndjson 
  --citation out/web_smoke/citation.ndjson
```

## Validation Layers
1. **JSON Schema:** Strict field types, no `additionalProperties`.
2. **Pointer Parity:** `web_output.trace_ptr` exists and contains valid frames.
3. **Evidence Parity:** Citations link to fetched docs in trace.
4. **Budget Parity:** `N_chunks <= 40`, `chunk <= 800c`.

## Exit Codes
- `0`: Success / Pass.
- `1`: Business / Validation Failure (e.g. schema drift, budget breach).
- `2`: Integrity / Internal Failure (e.g. corrupted cache, config crash).
