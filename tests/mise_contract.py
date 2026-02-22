from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

CI_RUN_EXPECTED = (
    "mise run fmt && mise run lint && mise run types && mise run unit && "
    "mise run proto && mise run trace && mise run schemas && mise run replay"
)


def load_mise() -> dict[str, Any]:
    return tomllib.loads(Path(".mise.toml").read_text(encoding="utf-8"))


def assert_ci_order_unchanged(data: dict[str, Any]) -> None:
    ci_run = data["tasks"]["ci"]["run"]
    if ci_run != CI_RUN_EXPECTED:
        raise AssertionError(f"CI ladder drifted: {ci_run!r}")


def mutated_with_ci_run(data: dict[str, Any], ci_run: str) -> dict[str, Any]:
    mutated = copy.deepcopy(data)
    mutated["tasks"]["ci"]["run"] = ci_run
    return mutated


def assert_helper_tasks_additive_only(data: dict[str, Any], *, helpers: tuple[str, ...]) -> None:
    tasks = data["tasks"]
    for name in helpers:
        if name not in tasks:
            raise AssertionError(f"missing helper task: {name}")
    assert_ci_order_unchanged(data)
    fast_run = str(tasks["fast"]["run"])
    for helper in helpers:
        token = f"run {helper}"
        if token in fast_run:
            raise AssertionError(f"fast widened with helper task: {helper}")
        if token in str(tasks["ci"]["run"]):
            raise AssertionError(f"ci widened with helper task: {helper}")
