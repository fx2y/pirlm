# ADR 005: Architectural Bets & Winner Lock

| Axis | Bet | Description | Reason |
| :--- | :--- | :--- | :--- |
| **B1** | **B1a** | SearxJsonProvider | Stdlib `urllib` + async fanout; zero deps. |
| **B2** | **B2a** | SqliteCache | WAL mode, atomic by body-sha; stable cross-URL. |
| **B3** | **B3b** | FallbackExtract | Regex script/style kill + tag strip; bomb-proof. |
| **B4** | **B4b** | BM25Scorer | Term-overlap ranking; better mrr_chunk than regex. |
| **B5** | **B5a** | QuoteAnchor | Literal quote span + caps; high verifiability. |

## Rejected Variants (Purged)
- **B1b:** Vendor HTTP (L0 risk, API keys).
- **B2b:** FS blobs (Dir structure drift, NTFS/ext4 parity).
- **B3a:** HTMLParser_struct (Fragile on tag-soup).
- **B4a:** Keyword_regex (Low precision).
- **B5b:** Paraphrase (Hallucination risk, hard to verify).

## Winner Plan
`WebPlan(provider="searx_json", cache="sqlite", parser="fallback_extract", scorer="bm25", cite_mode="quote_anchor")`
