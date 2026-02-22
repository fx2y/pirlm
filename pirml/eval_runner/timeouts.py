from __future__ import annotations


def classify_timeout(*, timed_out: bool, base_fail_tag: str) -> str:
    if timed_out:
        return "TIMEOUT"
    return base_fail_tag


__all__ = ["classify_timeout"]
