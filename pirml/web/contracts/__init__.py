from __future__ import annotations

from pathlib import Path

_CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"

WEB_SCHEMA_PATHS = {
    "serp": _CONTRACTS_DIR / "web_serp.schema.json",
    "doc": _CONTRACTS_DIR / "web_doc.schema.json",
    "extract": _CONTRACTS_DIR / "web_extract.schema.json",
    "citation": _CONTRACTS_DIR / "web_citation.schema.json",
    "web_eval": _CONTRACTS_DIR / "web_eval.schema.json",
}

__all__ = ["WEB_SCHEMA_PATHS"]
