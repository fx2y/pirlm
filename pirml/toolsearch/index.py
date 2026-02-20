from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, NamedTuple, cast

if TYPE_CHECKING:
    from pirml.contracts.schemas import ToolManifest


def tokenize(text: str) -> list[str]:
    """C2.T1: Simple whitespace + punctuation tokenizer.
    Lowercases and filters out empty tokens.
    """
    return [t.lower() for t in re.findall(r"\w+", text) if t]


def tool_doc_fields(m: ToolManifest) -> str:
    """S.IDX1: Extract searchable text fields from manifest."""
    # Use .get() safely for TypedDict
    schema: dict[str, Any] = m.get("input_schema") or {}
    props: dict[str, Any] = schema.get("properties") or {}
    fields = [
        m.get("name") or "",
        " ".join(m.get("tags") or []),
        " ".join(m.get("aliases") or []),
        " ".join(m.get("verbs") or []),
        " ".join(m.get("nouns") or []),
        m.get("description") or "",
        " ".join(
            k + " " + (cast(dict[str, Any], props.get(k) or {})).get("description", "")
            for k in sorted(props)
        ),
    ]
    return " ".join(fields)


class SearchHit(NamedTuple):
    name: str
    score: float
    hot_rank: int  # 0 if hot tool, 1 if deferred
    arg_count: int
    raw_name: str  # for final stable sort


class BM25Index:
    """C2.T2: Deterministic BM25 scorer using stdlib."""

    def __init__(self, catalog: Mapping[str, ToolManifest], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.catalog = catalog
        self.doc_names = list(catalog.keys())
        self.N = len(self.doc_names)

        self.doc_term_freqs: list[dict[str, int]] = []
        self.doc_lengths: list[int] = []
        self.df: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.postings: dict[str, list[int]] = {}

        for i, name in enumerate(self.doc_names):
            manifest = catalog[name]
            text = tool_doc_fields(manifest)
            tokens = tokenize(text)
            self.doc_lengths.append(len(tokens))

            tf: dict[str, int] = {}
            seen_tokens_in_doc: set[str] = set()
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
                if token not in seen_tokens_in_doc:
                    self.postings.setdefault(token, []).append(i)
                    seen_tokens_in_doc.add(token)

            for token in tf:
                self.df[token] = self.df.get(token, 0) + 1

            self.doc_term_freqs.append(tf)

        self.avdl = sum(self.doc_lengths) / self.N if self.N > 0 else 0

        # Precompute IDF
        for token, df in self.df.items():
            self.idf[token] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[SearchHit]:
        """Rank all docs in catalog. Docs with no matching tokens get 0.0 score."""
        q_tokens = tokenize(query)

        hits: list[SearchHit] = []
        for i in range(self.N):
            name = self.doc_names[i]
            score = 0.0
            tf_map = self.doc_term_freqs[i]
            dl = self.doc_lengths[i]

            for token in q_tokens:
                if token not in self.idf:
                    continue

                tf = tf_map.get(token, 0)
                if tf == 0:
                    continue

                # S.IDX2: BM25 score formula
                idf = self.idf[token]
                score += idf * (
                    (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avdl))
                )

            m = self.catalog[name]
            hot_rank: int = 0 if not m.get("defer_loading", True) else 1
            schema_m: dict[str, Any] = m.get("input_schema") or {}
            arg_count: int = len(schema_m.get("properties") or {})
            hits.append(SearchHit(name, score, hot_rank, arg_count, name))

        return hits
