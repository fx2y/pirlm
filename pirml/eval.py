from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .cli_common import (
    CliFailure,
    emit_failure,
    load_eval_config,
    parse_runner_config,
    parse_suite_config,
    strict_parse_args,
)


def _cfg_value(cli_value: Any, cfg: dict[str, Any], key: str) -> Any:
    return cli_value if cli_value is not None else cfg.get(key)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pirml.eval")
    parser.add_argument("--config", help="Path to eval config JSON")
    parser.add_argument("--suite", help="Suite id: golden50|browsecomp")
    parser.add_argument("--dataset", help="Path to explicit dataset jsonl")
    parser.add_argument("--jobs", type=int, help="Worker count")
    parser.add_argument("--shards", type=int, help="Total shard count")
    parser.add_argument("--shard", type=int, help="Shard index")
    parser.add_argument("--timeout-s", type=float, help="Per-task timeout seconds")
    parser.add_argument("--ctx-byte-cap", type=int, help="Context byte cap")
    parser.add_argument("--seed", type=int, help="Deterministic seed")
    parser.add_argument("--out-dir", help="Output root directory")
    return parser


def _run(args: argparse.Namespace) -> int:
    cfg = load_eval_config(args.config) if args.config else {}

    suite_cfg = parse_suite_config(
        suite=str(_cfg_value(args.suite, cfg, "suite") or ""),
        dataset=_cfg_value(args.dataset, cfg, "dataset"),
        require_citations=bool(
            _cfg_value(None, cfg, "require_citations") if "require_citations" in cfg else True
        ),
    )
    runner_cfg = parse_runner_config(
        jobs=int(_cfg_value(args.jobs, cfg, "jobs") or 1),
        shards=int(_cfg_value(args.shards, cfg, "shards") or 1),
        shard=int(_cfg_value(args.shard, cfg, "shard") or 0),
        timeout_s=float(_cfg_value(args.timeout_s, cfg, "timeout_s") or 180.0),
        ctx_byte_cap=int(_cfg_value(args.ctx_byte_cap, cfg, "ctx_byte_cap") or 120_000),
        seed=int(_cfg_value(args.seed, cfg, "seed") or 0),
        out_dir=str(_cfg_value(args.out_dir, cfg, "out_dir") or "out/eval"),
    )

    out_runs = runner_cfg.out_dir / "runs" / suite_cfg.suite
    out_runs.mkdir(parents=True, exist_ok=True)
    out_path = out_runs / f"shard-{runner_cfg.shard:05d}.ndjson"
    row = {
        "ok": False,
        "task_id": "CONFIG",
        "suite": suite_cfg.suite,
        "dataset": str(suite_cfg.dataset),
        "shard": runner_cfg.shard,
        "error": {
            "type": "unsupported",
            "msg": "C1 CLI scaffold only; runner ships in C2",
            "retryable": False,
        },
        "fail_tag": "UNSUPPORTED",
    }
    out_path.write_text(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    raise CliFailure("unsupported", "C1 CLI scaffold only; runner ships in C2", 1, retryable=False)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = strict_parse_args(parser, argv)
        return _run(args)
    except CliFailure as err:
        return emit_failure(err)
    except Exception as exc:
        print(
            json.dumps({"type": "integrity", "msg": str(exc), "retryable": False}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
