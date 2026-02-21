from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import cache as cache
    from . import cite as cite
    from . import contracts as contracts
    from . import etl as etl
    from . import etl_join as etl_join
    from . import etl_score as etl_score
    from . import eval as eval
    from . import eval_shard as eval_shard
    from . import fetch as fetch
    from . import pipeline as pipeline
    from . import search as search
    from . import trace as trace
    from . import types as types
    from . import urlnorm as urlnorm

__all__ = [
    "cache",
    "cite",
    "contracts",
    "etl",
    "etl_join",
    "etl_score",
    "eval",
    "eval_shard",
    "fetch",
    "pipeline",
    "search",
    "trace",
    "types",
    "urlnorm",
]


def __getattr__(name: str):
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
