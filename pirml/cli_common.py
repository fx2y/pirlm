from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class SuiteConfig:
    suite: str
    dataset: Path
    require_citations: bool = True


@dataclass(frozen=True)
class RunnerConfig:
    jobs: int = 1
    shards: int = 1
    shard: int = 0
    timeout_s: float = 180.0
    ctx_byte_cap: int = 120_000
    seed: int = 0
    out_dir: Path = Path("out/eval")


@dataclass(frozen=True)
class ThresholdConfig:
    acc_min_delta: float = 0.0
    cost_max_delta: float = 0.0
    latency_max_delta: float = 0.0
    acc_per_dollar_min_delta: float = 0.0
    acc_per_min_min_delta: float = 0.0


class CliFailure(Exception):
    def __init__(self, err_type: str, msg: str, code: int, retryable: bool = False) -> None:
        super().__init__(msg)
        self.err_type = err_type
        self.msg = msg
        self.code = code
        self.retryable = retryable


def _typed_error(err_type: str, msg: str, retryable: bool = False) -> dict[str, object]:
    return {"type": err_type, "msg": msg, "retryable": retryable}


def strict_parse_args(
    parser: argparse.ArgumentParser, argv: list[str] | None = None
) -> argparse.Namespace:
    parser.exit_on_error = False
    try:
        args, unknown = parser.parse_known_args(argv)
    except argparse.ArgumentError as exc:
        raise CliFailure("config", str(exc), 2, retryable=False) from exc
    if unknown:
        unknown_joined = " ".join(unknown)
        raise CliFailure("config", f"unknown args: {unknown_joined}", 2, retryable=False)
    return args


def fail_closed_suite(suite: str) -> str:
    allowed = {"golden50", "browsecomp"}
    if suite not in allowed:
        raise CliFailure("unsupported", f"unsupported suite: {suite}", 1, retryable=False)
    return suite


def parse_suite_config(
    *, suite: str, dataset: str | None, require_citations: bool = True
) -> SuiteConfig:
    suite_checked = fail_closed_suite(suite)
    if dataset is None:
        raise CliFailure("unsupported", "--dataset is required", 1, retryable=False)
    dataset_path = Path(dataset)
    if not dataset_path.is_file():
        raise CliFailure(
            "unsupported", f"dataset path not found: {dataset_path}", 1, retryable=False
        )
    return SuiteConfig(
        suite=suite_checked,
        dataset=dataset_path,
        require_citations=require_citations,
    )


def parse_runner_config(
    *,
    jobs: int,
    shards: int,
    shard: int,
    timeout_s: float,
    ctx_byte_cap: int,
    seed: int,
    out_dir: str,
) -> RunnerConfig:
    if jobs <= 0:
        raise CliFailure("validation", "--jobs must be > 0", 1, retryable=False)
    if shards <= 0:
        raise CliFailure("validation", "--shards must be > 0", 1, retryable=False)
    if shard < 0 or shard >= shards:
        raise CliFailure(
            "validation", "--shard must satisfy 0 <= shard < shards", 1, retryable=False
        )
    if timeout_s <= 0:
        raise CliFailure("validation", "--timeout-s must be > 0", 1, retryable=False)
    if ctx_byte_cap <= 0:
        raise CliFailure("validation", "--ctx-byte-cap must be > 0", 1, retryable=False)
    return RunnerConfig(
        jobs=jobs,
        shards=shards,
        shard=shard,
        timeout_s=timeout_s,
        ctx_byte_cap=ctx_byte_cap,
        seed=seed,
        out_dir=Path(out_dir),
    )


def load_eval_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_file():
        raise CliFailure("config", f"config path not found: {config_path}", 2, retryable=False)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliFailure("config", f"invalid JSON config: {exc}", 2, retryable=False) from exc
    if not isinstance(payload, dict):
        raise CliFailure("config", "config root must be object", 2, retryable=False)
    payload_map = cast(dict[str, Any], payload)
    allowed = {
        "suite",
        "dataset",
        "require_citations",
        "jobs",
        "shards",
        "shard",
        "timeout_s",
        "ctx_byte_cap",
        "seed",
        "out_dir",
    }
    unknown = sorted(set(payload_map.keys()) - allowed)
    if unknown:
        raise CliFailure("config", f"unknown config keys: {','.join(unknown)}", 2, retryable=False)
    _validate_eval_config_types(payload_map)
    return payload_map


def _validate_eval_config_types(payload_map: dict[str, Any]) -> None:
    scalar_types: dict[str, type[Any]] = {
        "suite": str,
        "dataset": str,
        "require_citations": bool,
        "jobs": int,
        "shards": int,
        "shard": int,
        "ctx_byte_cap": int,
        "seed": int,
        "out_dir": str,
    }
    for key, value in payload_map.items():
        if key == "timeout_s":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise CliFailure("config", "config.timeout_s must be number", 2, retryable=False)
            continue
        expected = scalar_types[key]
        if expected is int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise CliFailure("config", f"config.{key} must be int", 2, retryable=False)
            continue
        if expected is bool:
            if not isinstance(value, bool):
                raise CliFailure("config", f"config.{key} must be bool", 2, retryable=False)
            continue
        if expected is str and not isinstance(value, str):
            raise CliFailure("config", f"config.{key} must be str", 2, retryable=False)


def emit_failure(err: CliFailure) -> int:
    print(json.dumps(_typed_error(err.err_type, err.msg, err.retryable)), file=sys.stderr)
    return err.code
