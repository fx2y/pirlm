from __future__ import annotations

FAIL_TAGS: tuple[str, ...] = (
    "SEARCH_BAD",
    "FETCH_BLOCKED",
    "ETL_BAD",
    "TOOL_MISUSE",
    "HALLUCINATION",
    "TIMEOUT",
    "OUTPUT_INVALID",
    "REPLAY_MISMATCH",
    "CTX_BLOAT",
)


def classify_fail_tag(
    *, timed_out: bool, replay_match: bool, invalid_output: bool, no_cite: bool
) -> str:
    if timed_out:
        return "TIMEOUT"
    if not replay_match:
        return "REPLAY_MISMATCH"
    if no_cite:
        return "HALLUCINATION"
    if invalid_output:
        return "OUTPUT_INVALID"
    return ""


__all__ = ["FAIL_TAGS", "classify_fail_tag"]
