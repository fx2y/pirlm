# PiRLM CLI Toolpack

Composable CLI wrappers for interacting with PiRLM artifacts and replaying traces.

## 1. pirml-open

**Purpose:** Open artifacts or views by ID (AID or VID).

**Usage:**
```bash
python -m scripts.tools.open <id> [--mode {meta,bytes,text}] [--art-root <path>]
```

**Modes:**
- `bytes` (default): Output raw artifact bytes to stdout.
- `meta`: Output artifact metadata as JSON.
- `text`: Concatenate and output text content (views only).

**Examples:**
```bash
# Display metadata for an artifact
python -m scripts.tools.open a1 --mode meta

# Display text content of a view
python -m scripts.tools.open v1 --mode text

# Pipe raw bytes to a file
python -m scripts.tools.open a1 --mode bytes > out.pdf
```

**Failure Modes:**
- Exit 1: ID not found, artifact root missing, or binary data in text mode.
- Exit 2: Unexpected system error or integrity failure.

---

## 2. pirml-slice

**Purpose:** Create artifact slices (views) for RLM recursion or inspection.

**Usage:**
```bash
python -m scripts.tools.slice <aid> <spec_json> [--art-root <path>]
```

**Examples:**
```bash
# Slice first 10 lines of an artifact
python -m scripts.tools.slice a1 '{"op":"lines","a":0,"b":9}'

# Slice using regex and limit results
python -m scripts.tools.slice a1 '{"op":"regex","pat":"ERROR","max_hits":5}'

# Complex slice with post-processing
python -m scripts.tools.slice a1 '{"op":"lines","a":0,"b":100,"post":[{"op":"score","params":{"query":"database"}},{"op":"limit","params":{"n":5}}]}'
```

**Failure Modes:**
- Exit 1: Invalid JSON spec or AID not found.
- Exit 2: Unsupported view op or materialization failure.

---

## 3. pirml-replay

**Purpose:** Deterministically rerun a program from an existing trace.

**Usage:**
```bash
python -m scripts.tools.replay <prog.py> <trace.ndjson> [--out-dir <path>] [--timeout <seconds>]
```

**Examples:**
```bash
python -m scripts.tools.replay my_prog.py out/run1/trace.ndjson --out-dir out/replay_test
```

**Failure Modes:**
- Exit 0: Success.
- Exit 1: Program logic failure during replay.
- Exit 2: Protocol error, ID/hash drift, or tool execution attempt during replay.

---

## 4. pirml-search

**Purpose:** Search artifacts by metadata/content without manual NDJSON grep.

**Usage:**
```bash
python -m scripts.tools.search [--kind <kind>] [--url <substr>] [--contains <substr>] [--limit <n>] [--json] [--art-root <path>]
```

**Examples:**
```bash
# Find raw artifacts from a specific site
python -m scripts.tools.search --kind raw --url example.com --json

# Find artifacts whose UTF-8 payload contains a snippet
python -m scripts.tools.search --contains "deterministic evidence" --limit 10
```

**Failure Modes:**
- Exit 1: Invalid filter values or missing artifact root.
- Exit 2: Integrity/internal failures while scanning artifacts.

---

## Non-Goals
- These tools are NOT for live runtime execution (use `python -m pirml`).
- These tools do NOT edit artifacts (immutable CAS).
- These tools do NOT support network fetch (replay-only/local-only).
