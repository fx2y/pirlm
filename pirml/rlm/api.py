from __future__ import annotations

from typing import Any

from pirml.artifacts.store import ArtifactStore
from pirml.compiler.model import ModelAdapter

from .kernel import RlmBudget, RlmKernel


def run_rlm(
    prompt: str, store: ArtifactStore, model: ModelAdapter, budget: RlmBudget | None = None
) -> Any:
    kernel = RlmKernel(store, model, budget)
    return kernel.run(prompt)
