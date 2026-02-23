from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from pirml.clock import SequenceClock
from pirml.runtime.rpc import canonical_json
from pirml.web.cache import cache_factory
from pirml.web.eval import evidence_accuracy
from pirml.web.fetch import CachedDocFetcher, FixtureDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import provider_factory
from pirml.web.taxonomy import classify_fail_tag
from pirml.web.trace import WebTracer
from pirml.web.types import EvalRow, SerpRow


async def run_shard(
    *,
    queries: list[dict[str, str]],
    plan: WebPlan,
    responses_path: Path,
    cache_path: Path,
    seed: int = 0,
) -> list[EvalRow]:
    clock = SequenceClock.from_env()
    tracer = WebTracer()

    # provider_factory expects dict[str, list[SerpRow]]
    provider_responses: dict[str, list[SerpRow]] = {}
    for q in queries:
        query_text = q["query"].lower()
        if "pirml" in query_text:
            url = "https://example.com/docs/page?a=1&b=2"
            title = "PIRML Documentation"
        elif "deterministic" in query_text:
            url = "https://example.com/docs/page2"
            title = "Deterministic Testing Guide"
        else:
            url = "https://example.com/docs/unknown"
            title = "Unknown Page"

        provider_responses[q["query"]] = [
            {
                "url": url,
                "title": title,
                "snippet": f"This is a relevant snippet for {q['query']}",
                "rank": 1,
                "source": "mock",
            },
        ]

    provider = provider_factory(plan.provider, provider_responses)

    cache_path.mkdir(parents=True, exist_ok=True)
    cache_file = cache_path / "web_cache.sqlite"

    cache = cache_factory(plan.cache, cache_file)
    base_fetcher = FixtureDocFetcher(responses_path)
    fetcher = CachedDocFetcher(base_fetcher, cache=cache)

    pipeline = WebPipeline(
        provider=provider,
        fetcher=fetcher,
        clock=clock,
        tracer=tracer,
        trace_dir=cache_path,
    )

    results: list[EvalRow] = []
    for q_row in queries:
        qid = q_row["qid"]
        query = q_row["query"]

        # Start fresh tracer per query for clean metrics
        query_tracer = WebTracer()
        pipeline.tracer = query_tracer

        # Run pipeline
        final = await pipeline.run(query, plan, trace_filename=f"web_trace_{qid}.ndjson")

        # Calculate metrics from tracer
        frames = query_tracer.get_frames()
        # Filter for web-specific frames
        fetch_results = [f for f in frames if cast(Any, f).get("op") == "fetch_result"]
        fetches = len(fetch_results)
        total_bytes = sum(cast(Any, f).get("bytes", 0) for f in fetch_results)
        cache_hits = sum(1 for f in fetch_results if cast(Any, f).get("cache_hit"))
        cache_hit_rate = cache_hits / len(fetch_results) if fetch_results else 0.0

        acc = evidence_accuracy(query=query, citations=final["citations"])

        tokens_in = len(query.split())
        tokens_out = len(final["answer"].split())
        bytes_into_model = len(query.encode("utf-8")) + total_bytes
        no_cite = len(final["citations"]) == 0
        invalid_output = acc <= 0.0 and not no_cite
        fail_tag = classify_fail_tag(
            timed_out=False,
            replay_match=True,
            invalid_output=invalid_output,
            no_cite=no_cite,
        )
        fanout_peak = min(plan.max_parallel_fetch, max(fetches, 1))

        eval_row: EvalRow = {
            "qid": qid,
            "plan": canonical_json(asdict(plan)),
            "acc": acc,
            "fetches": fetches,
            "bytes": total_bytes,
            "chunks": len(final["citations"]),
            "cache_hit": cache_hit_rate,
            "fail_tag": fail_tag,
            "timeout_s": 0.0,
            "latency_ms": float(len(frames)),
            "cost_usd": round((tokens_in + tokens_out) * 0.000001, 8),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "bytes_into_model": bytes_into_model,
            "tool_calls": fetches,
            "fanout_peak": fanout_peak,
            "invalid_output": invalid_output,
            "no_cite": no_cite,
            "replay_match": True,
        }
        results.append(eval_row)

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=str)  # JSON string
    parser.add_argument("--seed", default=0, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--responses", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    args = parser.parse_args()

    with args.queries.open("r") as f:
        queries = [json.loads(line) for line in f]

    plan_dict = json.loads(args.plan)
    plan = WebPlan(**plan_dict)

    results = asyncio.run(
        run_shard(
            queries=queries,
            plan=plan,
            responses_path=args.responses,
            cache_path=args.cache_dir,
            seed=args.seed,
        )
    )

    with args.output.open("w", encoding="utf-8") as f:
        for row in results:
            f.write(canonical_json(row) + "\n")


if __name__ == "__main__":
    main()
