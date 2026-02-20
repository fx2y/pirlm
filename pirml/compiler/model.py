from __future__ import annotations

import os
from abc import ABC, abstractmethod


class ModelAdapter(ABC):
    @abstractmethod
    def compile_once(self, prompt: str) -> str:
        """Single model invocation returning raw text."""
        pass


class StubModelAdapter(ModelAdapter):
    """Stub adapter for testing and CI."""

    def __init__(self, raw_text: str = ""):
        self.raw_text = raw_text

    def compile_once(self, prompt: str) -> str:
        return self.raw_text


def get_model_adapter() -> ModelAdapter:
    """Factory for model adapter based on environment."""
    # For now, return stub. In real use, this might return an OpenAI or Anthropic adapter.
    # PIRML_MODEL_RAW can be used to inject static responses for testing
    raw = os.environ.get("PIRML_MODEL_RAW", "")
    return StubModelAdapter(raw)
