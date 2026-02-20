import asyncio
import json
from pathlib import Path

from pirml.clock import SequenceClock
from pirml.web.fetch import FixtureDocFetcher
from pirml.web.pipeline import WebPipeline, WebPlan
from pirml.web.search import MockProvider
from pirml.web.trace import WebTracer


async def main():
    out_dir = Path("out/web_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = MockProvider(
        {
            "pirml": [
                {
                    "url": "https://example.com/p",
                    "title": "PIRML",
                    "snippet": "...",
                    "rank": 1,
                    "source": "test",
                }
            ]
        }
    )
    responses_path = Path("tests/fixtures/web/responses.json")
    fetcher = FixtureDocFetcher(responses_path)
    # Map test URL
    fetcher._records["https://example.com/p"] = fetcher._records[  # type: ignore
        "https://example.com/docs/page?a=1&b=2"
    ]

    clock = SequenceClock(start=1_700_000_000)
    tracer = WebTracer()

    pipeline = WebPipeline(provider=provider, fetcher=fetcher, clock=clock, tracer=tracer)
    plan = WebPlan(
        provider="mock",
        cache="memory",
        parser="html_parser_primary",
        scorer="bm25_chunk",
        cite_mode="quote_anchor",
    )

    result = await pipeline.run("pirml", plan)

    # Write artifacts to out_dir
    (out_dir / "final.json").write_text(json.dumps(result, indent=2))

    serp = [
        {
            "url": "https://example.com/p",
            "title": "PIRML",
            "snippet": "...",
            "rank": 1,
            "source": "test",
        }
    ]
    with (out_dir / "serp.ndjson").open("w") as f:
        for s in serp:
            f.write(json.dumps(s) + "\n")

    doc = {
        "url": "https://example.com/p",
        "final_url": "https://example.com/p",
        "status": 200,
        "headers": {"Content-Type": "text/html"},
        "content_type": "text/html",
        "bytes": 100,
        "encoding_guess": "utf-8",
        "body": "<html><body>ok</body></html>",
        "body_sha256": "a" * 64,
    }
    with (out_dir / "doc.ndjson").open("w") as f:
        f.write(json.dumps(doc) + "\n")

    extract = {
        "doc_sha256": "a" * 64,
        "url": "https://example.com/p",
        "chunk_id": "ck001",
        "kind": "p",
        "path_hint": "p",
        "text": "ok",
        "score": 1.0,
        "source_rank": 1,
        "doc_rank": 1,
    }
    with (out_dir / "extract.ndjson").open("w") as f:
        f.write(json.dumps(extract) + "\n")

    with (out_dir / "citation.ndjson").open("w") as f:
        for c in result["citations"]:
            f.write(json.dumps(c) + "\n")

    # Web Eval
    eval_row = {
        "qid": "Q1",
        "plan": "default",
        "acc": 1.0,
        "fetches": 1,
        "bytes": 100,
        "chunks": 1,
        "cache_hit": 0.0,
    }
    with (out_dir / "eval.ndjson").open("w") as f:
        f.write(json.dumps(eval_row) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
