from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, NamedTuple, cast

if TYPE_CHECKING:
    from pirml.contracts.schemas import ToolManifest

# G.P1.7: vendored k-cap constant; all public APIs enforce this ceiling
K_CAP: int = 5

# G.P1.6: field weights applied by token repetition (cheap, stdlib-only)
_FIELD_WEIGHTS: dict[str, int] = {
    "name": 3,
    "aliases": 2,
    "verbs": 2,
    "nouns": 2,
    "tags": 2,
    "description": 1,
    "schema_props": 1,
}


def tokenize(text: str) -> list[str]:
    """C2.T1: Simple whitespace + punctuation tokenizer.
    Lowercases and filters out empty tokens.
    """
    return [t.lower() for t in re.findall(r"\w+", text) if t]


def tool_doc_fields(m: ToolManifest) -> str:
    """S.IDX1: Extract searchable text fields from manifest (unweighted, for regex search)."""
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


def _weighted_tokens(m: ToolManifest) -> list[str]:
    """G.P1.6: Produce weighted token stream by repeating segments per weight."""
    schema: dict[str, Any] = m.get("input_schema") or {}
    props: dict[str, Any] = schema.get("properties") or {}

    schema_prop_text = " ".join(
        k + " " + (cast(dict[str, Any], props.get(k) or {})).get("description", "")
        for k in sorted(props)
    )

    segments: list[tuple[str, int]] = [
        (m.get("name") or "", _FIELD_WEIGHTS["name"]),
        (" ".join(m.get("aliases") or []), _FIELD_WEIGHTS["aliases"]),
        (" ".join(m.get("verbs") or []), _FIELD_WEIGHTS["verbs"]),
        (" ".join(m.get("nouns") or []), _FIELD_WEIGHTS["nouns"]),
        (" ".join(m.get("tags") or []), _FIELD_WEIGHTS["tags"]),
        (m.get("description") or "", _FIELD_WEIGHTS["description"]),
        (schema_prop_text, _FIELD_WEIGHTS["schema_props"]),
    ]
    tokens: list[str] = []
    for text, weight in segments:
        seg_toks = tokenize(text)
        tokens.extend(seg_toks * weight)
    return tokens


class SearchHit(NamedTuple):
    name: str
    score: float
    hot_rank: int  # 0 if hot tool, 1 if deferred
    arg_count: int
    raw_name: str  # for final stable sort


class BM25Index:
    """C2.T2: Deterministic BM25 scorer using stdlib with field weighting (G.P1.6)."""

    def __init__(self, catalog: Mapping[str, ToolManifest], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.catalog = catalog
        # Canonical order regardless of mapping insertion order
        self.doc_names = sorted(catalog.keys())
        self.N = len(self.doc_names)

        self.doc_term_freqs: list[dict[str, int]] = []
        self.doc_lengths: list[int] = []
        self.df: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.postings: dict[str, list[int]] = {}
        self.doc_hot_ranks: list[int] = []
        self.doc_arg_counts: list[int] = []

        for i, name in enumerate(self.doc_names):
            manifest = catalog[name]
            # G.P1.6: use weighted token stream for TF/DF computation
            tokens = _weighted_tokens(manifest)
            self.doc_lengths.append(len(tokens))
            self.doc_hot_ranks.append(0 if not manifest.get("defer_loading", True) else 1)
            schema_m: dict[str, Any] = manifest.get("input_schema") or {}
            self.doc_arg_counts.append(len(schema_m.get("properties") or {}))

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

        for token, df in self.df.items():
            self.idf[token] = math.log(1 + (self.N - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[SearchHit]:
        """Rank all docs. Docs with no matching tokens get 0.0 score."""
        q_tokens = tokenize(query)
        score_by_doc: dict[int, float] = {}
        candidate_docs: set[int] = set()
        for token in q_tokens:
            candidate_docs.update(self.postings.get(token, ()))

        for i in candidate_docs:
            tf_map = self.doc_term_freqs[i]
            dl = self.doc_lengths[i]
            score = 0.0
            for token in q_tokens:
                if token not in self.idf:
                    continue
                tf = tf_map.get(token, 0)
                if tf == 0:
                    continue
                idf = self.idf[token]
                score += idf * (
                    (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avdl))
                )
            score_by_doc[i] = score

        return [
            SearchHit(
                self.doc_names[i],
                score_by_doc.get(i, 0.0),
                self.doc_hot_ranks[i],
                self.doc_arg_counts[i],
                self.doc_names[i],
            )
            for i in range(self.N)
        ]
