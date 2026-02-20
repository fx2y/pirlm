from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


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
    # PIRML_MODEL_RAW takes precedence for simple shell-based injection
    raw = os.environ.get("PIRML_MODEL_RAW")
    if raw is not None:
        return StubModelAdapter(raw)

    # PIRML_MODEL_FILE allows reading large/complex responses from disk
    model_file = os.environ.get("PIRML_MODEL_FILE")
    if model_file:
        file_path = Path(model_file)
        if file_path.exists():
            return StubModelAdapter(file_path.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"PIRML_MODEL_FILE not found: {model_file}")

    return StubModelAdapter("")
