# ADR 005: Pipeline Tracing & Observability

## Trace Frame (`web_trace.ndjson`)
- **seq:** Monotonic increment per frame.
- **op:** `search` | `fetch` | `extract` | `cite`.
- **dir:** `>` (call) | `<` (result).
- **ts/ms:** `SequenceClock` ticks.

## Example Frame: Fetch Result
```json
{
  "seq": 4,
  "dir": "<",
  "op": "fetch",
  "id": "f0001",
  "ok": true,
  "ms": 150,
  "p": {
    "url": "https://example.com/a",
    "status": 200,
    "body_sha256": "e3b0c442...",
    "cached": true,
    "truncated": false
  }
}
```

## Trace Pointer (`web_output.json`)
```json
{
  "answer": "Concise fact-based answer.",
  "citations": [...],
  "trace_ptr": "web_trace_20260221_120000.ndjson"
}
```
- Pointer must be relative to output or resolvable via `schema_lint --web-trace`.
- Frame parity: every `citation.doc_sha` must appear in a `fetch` result frame.
