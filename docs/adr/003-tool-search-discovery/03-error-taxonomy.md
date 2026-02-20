# ToolSearch Error Taxonomy

| Error Type | rc | Retryable | Meaning |
| :--- | :--- | :--- | :--- |
| `invalid_pattern` | 1 | No | Regex syntax error in query. |
| `pattern_too_long` | 1 | No | Regex length > 200 chars (DoS protection). |
| `missing_tool_definition` | 1 | No | Hydration requested for symbol not in catalog. |
| `all_deferred` | 1 | Yes | Catalog has no entrypoint tools; invalid setup. |
| `load_failed` | 2 | No | JSON corruption in manifest files. |
| `duplicate_name` | 2 | No | Strict loader found name collision. |
| `toolsearch_examples_incompatible` | 2 | No | Guardrail: server-search + examples requested. |

## Flow
1. **Linter** catches `load_failed` and `duplicate_name`.
2. **Search** returns `invalid_pattern` or empty results (never silent null).
3. **Hydration** catches `missing_tool_definition`.
