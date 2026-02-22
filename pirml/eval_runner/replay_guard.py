from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass


def replay_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PIRML_BLOCK_TOOLS"] = "1"
    return env


@dataclass(frozen=True)
class ReplaySnapshot:
    ok: bool
    fail_tag: str
    latency_ms: float


@dataclass(frozen=True)
class ReplayCheck:
    match: bool
    note: str = ""


def _forced_mismatch(task_id: str) -> bool:
    # Deterministic test seam: used only by tests to force explicit mismatch lanes.
    forced = os.environ.get("PIRML_REPLAY_FORCE_MISMATCH", "").strip()
    if not forced:
        return False
    if forced == "1":
        return True
    blocked = {token.strip() for token in forced.split(",") if token.strip()}
    return task_id in blocked


def _run_with_replay_env(fn: Callable[[], ReplaySnapshot]) -> ReplaySnapshot:
    replay = replay_env()
    previous = os.environ.get("PIRML_BLOCK_TOOLS")
    os.environ["PIRML_BLOCK_TOOLS"] = replay["PIRML_BLOCK_TOOLS"]
    try:
        return fn()
    finally:
        if previous is None:
            os.environ.pop("PIRML_BLOCK_TOOLS", None)
        else:
            os.environ["PIRML_BLOCK_TOOLS"] = previous


def check_task_replay(
    *, task_id: str, live: ReplaySnapshot, replay_run: Callable[[], ReplaySnapshot]
) -> ReplayCheck:
    if _forced_mismatch(task_id):
        return ReplayCheck(match=False, note="replay_guard:forced_mismatch")
    try:
        replay = _run_with_replay_env(replay_run)
    except Exception as exc:
        return ReplayCheck(match=False, note=f"replay_guard:error:{exc.__class__.__name__}")
    if replay != live:
        return ReplayCheck(match=False, note="replay_guard:parity_mismatch")
    return ReplayCheck(match=True)


__all__ = ["ReplayCheck", "ReplaySnapshot", "check_task_replay", "replay_env"]
