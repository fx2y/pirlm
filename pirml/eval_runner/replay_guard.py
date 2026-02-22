from __future__ import annotations

import os
from typing import Any


def replay_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PIRML_BLOCK_TOOLS"] = "1"
    return env


def check_task_replay(task_id: str, row: dict[str, Any]) -> bool:
    forced = os.environ.get("PIRML_REPLAY_FORCE_MISMATCH", "").strip()
    if not forced:
        return True
    if forced == "1":
        return False
    blocked = {token.strip() for token in forced.split(",") if token.strip()}
    return task_id not in blocked


__all__ = ["check_task_replay", "replay_env"]
