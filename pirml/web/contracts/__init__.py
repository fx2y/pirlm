from __future__ import annotations

from pathlib import Path

_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"

WEB_TRACE_OPS: tuple[str, ...] = (
    "search_call",
    "search_result",
    "fetch_call",
    "fetch_result",
    "etl_result",
    "score_result",
    "metrics",
)

WEB_EVAL_REQUIRED_FIELDS: tuple[str, ...] = (
    "qid",
    "plan",
    "acc",
    "fetches",
    "bytes",
    "chunks",
    "cache_hit",
    "fail_tag",
    "timeout_s",
    "latency_ms",
    "cost_usd",
    "tokens_in",
    "tokens_out",
    "bytes_into_model",
    "tool_calls",
    "fanout_peak",
    "invalid_output",
    "no_cite",
    "replay_match",
)

WEB_SCHEMA_PATHS = {
    "serp": _CONTRACTS_DIR / "web_serp.schema.json",
    "doc": _CONTRACTS_DIR / "web_doc.schema.json",
    "extract": _CONTRACTS_DIR / "web_extract.schema.json",
    "citation": _CONTRACTS_DIR / "web_citation.schema.json",
    "web_eval": _CONTRACTS_DIR / "web_eval.schema.json",
    "web_trace": _CONTRACTS_DIR / "web_trace_frame.schema.json",
}

__all__ = ["WEB_EVAL_REQUIRED_FIELDS", "WEB_SCHEMA_PATHS", "WEB_TRACE_OPS"]
