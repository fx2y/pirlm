# RLM: Recursive Language Models Walkthrough

Problem: Input is 100MB of log files. LLM context is 128KB.

## 1. Slice
The runtime exposes an `ArtifactFS` with slicing primitives.
```python
# prog.py logic
logs = ArtifactFS.open("huge.log")
chunks = logs.slice(overlap=100, chunk_size=50000) # 50KB chunks
```

## 2. Map (Parallel Summarization)
Model-generated `prog.py` spawns N parallel sub-calls to the LLM (or a smaller local model) to summarize each slice.
```python
summaries = await asyncio.gather(*[
    call_tool("rlm.summarize", text=c, question="Find errors") 
    for c in chunks
])
```

## 3. Reduce
The `prog.py` then aggregates these summaries. If the aggregate is still too large, it recurses.
```python
final_distill = await call_tool("rlm.reduce", summaries=summaries)
```

## 4. Why RLM > Compaction
Compaction (simple summarization) loses precision. RLM recursion maintains a tree of evidence, allowing the model to "dive" back into a specific slice if needed by referencing artifact IDs.
