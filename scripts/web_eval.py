import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pirml.web.eval.metrics import metric_tuple
from pirml.web.pipeline import WebPlan


def resolve_plan(plan_str: str) -> WebPlan:
    # Example: (B1a,B2a,B3a,B4a,B5a)
    parts = plan_str.strip("()").split(",")
    # B1a -> searx_json, B1b -> vendor_http
    # B2a -> sqlite, B2b -> fs
    # B3a -> html_parser_primary, B3b -> dumb_text_primary
    # B4a -> keyword_regex, B4b -> bm25_chunk
    # B5a -> quote_anchor, B5b -> paraphrase_anchor

    mapping = {
        "B1a": "searx_json",
        "B1b": "vendor_http",
        "B2a": "sqlite",
        "B2b": "fs",
        "B3a": "html_parser_primary",
        "B3b": "dumb_text_primary",
        "B4a": "keyword_regex",
        "B4b": "bm25_chunk",
        "B5a": "quote_anchor",
        "B5b": "paraphrase_anchor",
    }

    return WebPlan(
        provider=mapping[parts[0]],
        cache=mapping[parts[1]],
        parser=mapping[parts[2]],
        scorer=mapping[parts[3]],
        cite_mode=mapping[parts[4]],
    )


def select_winner(all_results: list[dict[str, Any]]) -> str:
    if not all_results:
        raise ValueError("Empty run list")

    # Selection rule: lexicographic max on (acc, -bytes, -chunks, -fetches, cache_hit)
    # metric_tuple: (acc, -bytes, -chunks, -fetches, cache_hit)
    winner = max(
        all_results,
        key=lambda r: metric_tuple(
            {
                "qid": "",
                "plan": r["plan_id"],
                "acc": float(r["acc"]),
                "fetches": int(r["fetches"]),
                "bytes": int(r["bytes"]),
                "chunks": int(r["chunks"]),
                "cache_hit": float(r["cache_hit"]),
            }
        ),
    )

    return str(winner["plan_id"])


def main():
    bets_path = Path("spec-0/05/60-bets.jsonl")
    with bets_path.open("r") as f:
        matrix_def = [json.loads(line) for line in f if '"k":"matrix"' in line][0]

    plans = matrix_def["plans"]
    queries_path = Path("tests/fixtures/web/corpus.jsonl")
    responses_path = Path("tests/fixtures/web/responses.json")
    out_dir = Path("out/web_eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict[str, Any]] = []

    for plan_str in plans:
        plan = resolve_plan(plan_str)
        plan_json = json.dumps(plan.__dict__)

        output_file = out_dir / f"result_{plan_str}.jsonl"
        cache_dir = out_dir / f"cache_{plan_str}"
        cache_dir.mkdir(exist_ok=True)

        # Call browsecomp_shard.py
        cmd = [
            sys.executable,
            "-m",
            "pirml.web.eval.browsecomp_shard",
            "--queries",
            str(queries_path),
            "--plan",
            plan_json,
            "--output",
            str(output_file),
            "--responses",
            str(responses_path),
            "--cache-dir",
            str(cache_dir),
        ]

        print(f"Running eval for {plan_str}...")
        subprocess.run(cmd, check=True)

        # Load and aggregate results
        with output_file.open("r") as f:
            rows = [json.loads(line) for line in f]

        # Average metrics
        avg_acc = sum(r["acc"] for r in rows) / len(rows)
        avg_fetches = sum(r["fetches"] for r in rows) / len(rows)
        avg_bytes = sum(r["bytes"] for r in rows) / len(rows)
        avg_chunks = sum(r["chunks"] for r in rows) / len(rows)
        avg_cache_hit = sum(r["cache_hit"] for r in rows) / len(rows)

        summary = {
            "plan_id": plan_str,
            "plan": plan.__dict__,
            "acc": avg_acc,
            "fetches": avg_fetches,
            "bytes": avg_bytes,
            "chunks": avg_chunks,
            "cache_hit": avg_cache_hit,
        }
        all_results.append(summary)

    # Select winner
    winner_id = select_winner(all_results)
    winner = [r for r in all_results if r["plan_id"] == winner_id][0]

    final_output = {"results": all_results, "winner": winner}

    with open("out/web_eval.json", "w") as f:
        json.dump(final_output, f, indent=2)

    canonical_verdict = {
        "winner_id": winner["plan_id"],
        "winner_metrics": {
            "acc": round(float(winner["acc"]), 4),
            "bytes_q": int(winner["bytes"]),
            "chunks_q": int(winner["chunks"]),
            "fetches_q": int(winner["fetches"]),
            "cache_hit": round(float(winner["cache_hit"]), 4),
        },
    }

    with open("out/web_eval.canonical.json", "w") as f:
        json.dump(canonical_verdict, f, indent=2, sort_keys=True)

    print(f"Winner: {winner['plan_id']}")


if __name__ == "__main__":
    main()
