# Manifest Authoring Guide (Spec-03)

## Quality Constraints
- **Self-Correction**: Description must include when NOT to use the tool.
- **Hot-Tools**: Do not mark tools as `defer_loading: false` unless they are essential for the first-turn resolution of most queries.
- **Examples**: Must be schema-valid. LLMs use these to infer parameter types over raw JSON schema.

## Example Manifest
```json
{
  "name": "fs.read_file",
  "description": "Reads raw content of a local file. Only use when full content is needed for analysis. Do not use for large logs (>1MB); use log.tail instead.",
  "input_schema": {
    "type": "object",
    "properties": {
      "path": { "type": "string", "description": "Absolute path to the file." }
    },
    "required": ["path"],
    "additionalProperties": false
  },
  "input_examples": [
    { "path": "/etc/hosts" }
  ],
  "defer_loading": false,
  "tags": ["filesystem", "read", "io"]
}
```
