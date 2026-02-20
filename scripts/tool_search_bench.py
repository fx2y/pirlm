import json
import os
import time

from pirml.contracts.schemas import ToolManifest
from pirml.toolsearch.index import BM25Index
from pirml.toolsearch.render import render_selected_tools
from pirml.toolsearch.search import search_tools


def generate_dummy_catalog(n: int) -> dict[str, ToolManifest]:
    catalog: dict[str, ToolManifest] = {}
    for i in range(n):
        name = f"svc.tool_{i}"
        catalog[name] = {
            "name": name,
            "description": f"Tool {i} description. This is a dummy tool for benchmarking. It does something useful. Do not use for anything else.",
            "input_schema": {
                "type": "object",
                "properties": {
                    f"arg_{j}": {"type": "string", "description": f"Argument {j} for tool {i}"}
                    for j in range(3)
                },
            },
            "defer_loading": i >= 5,  # 5 hot tools
            "tags": [f"tag_{i % 10}", "dummy"],
            "verbs": [f"verb_{i % 20}"],
            "nouns": [f"noun_{i % 20}"],
        }
    return catalog


def main() -> None:
    n_tools = 1000
    catalog = generate_dummy_catalog(n_tools)

    # Warm up caches
    search_tools(catalog, "warmup", k=5)

    # 1. Benchmark Index Build
    start = time.perf_counter()
    BM25Index(catalog)
    idx_ms = (time.perf_counter() - start) * 1000

    # 2. Benchmark Query
    queries = ["tool 500", "verb_5", "noun_10", "tag_1 dummy", "arg_2"]
    latencies: list[float] = []
    for q in queries:
        start = time.perf_counter()
        search_tools(catalog, q, k=5)
        latencies.append((time.perf_counter() - start) * 1000)

    # Repeat for more stability
    for _ in range(10):
        for q in queries:
            start = time.perf_counter()
            search_tools(catalog, q, k=5)
            latencies.append((time.perf_counter() - start) * 1000)

    p50: float = sorted(latencies)[len(latencies) // 2]
    p95: float = sorted(latencies)[-1]

    bench_result = {
        "n_tools": n_tools,
        "index_ms": round(idx_ms, 2),
        "query_ms_p50": round(p50, 2),
        "query_ms_p95": round(p95, 2),
        "context": {"os": os.name, "timestamp": time.time()},
    }

    # G.P2.3: Canonical output for stable CI diffs
    canonical_bench = {
        "n_tools": n_tools,
        "status": "PASS" if p50 < 15 and idx_ms < 50 else "FAIL",
        "perf_budget_ms": {"p50": 15, "index": 50},
    }

    os.makedirs("out", exist_ok=True)
    with open("out/toolsearch_bench.json", "w") as f:
        json.dump(bench_result, f, indent=2)

    with open("out/toolsearch_bench.canonical.json", "w") as f:
        json.dump(canonical_bench, f, indent=2, sort_keys=True)

    print(f"Index built in {idx_ms:.2f}ms")
    print(f"Query p50: {p50:.2f}ms")

    # 3. Token Context Delta
    full_tools = list(catalog.values())
    selected_names = search_tools(catalog, "tool 500", k=5)
    selected_tools = [catalog[name] for name in selected_names]

    # Simple byte-based "token" approximation
    def canonical_json_bytes(obj: object) -> int:
        return len(json.dumps(obj, sort_keys=True).encode("utf-8"))

    full_bytes = canonical_json_bytes(render_selected_tools(full_tools))
    selected_bytes = canonical_json_bytes(render_selected_tools(selected_tools))

    token_delta = {
        "full_bytes": full_bytes,
        "selected_bytes": selected_bytes,
        "reduction_pct": round((1 - selected_bytes / full_bytes) * 100, 2),
    }

    with open("out/toolsearch_tokens.json", "w") as f:
        json.dump(token_delta, f, indent=2)

    print(
        f"Context reduction: {token_delta['reduction_pct']}% ({full_bytes} -> {selected_bytes} bytes)"
    )


if __name__ == "__main__":
    main()
