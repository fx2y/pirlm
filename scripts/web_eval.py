import json
import re
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypedDict, cast

from pirml.runtime.rpc import canonical_json
from pirml.web.eval import metric_tuple
from pirml.web.pipeline import WebPlan


class TypedError(TypedDict):
    type: str
    msg: str
    retryable: bool


class EvalPlanSummary(TypedDict):
    plan_id: str
    plan: dict[str, Any] | None
    ok: bool
    acc: float
    fetches: float
    bytes: float
    chunks: float
    cache_hit: float
    error: TypedError | None


_PLAN_RE = re.compile(r"^\((B1[ab]),(B2[ab]),(B3[ab]),(B4[ab]),(B5[ab])\)$")

_B1_PROVIDER = {"B1a": "searx_json", "B1b": "vendor_http"}
_B2_CACHE = {"B2a": "sqlite", "B2b": "fs"}
_WINNER_ONLY = {
    "B2": {"B2a"},
    "B3": {"B3b"},
    "B4": {"B4b"},
    "B5": {"B5a"},
}


def _typed_error(err_type: str, msg: str, *, retryable: bool = False) -> TypedError:
    return {"type": err_type, "msg": msg, "retryable": retryable}


def resolve_plan(plan_str: str) -> WebPlan:
    match = _PLAN_RE.fullmatch(plan_str)
    if match is None:
        raise ValueError(f"invalid matrix plan syntax: {plan_str}")
    b1, b2, b3, b4, b5 = match.groups()
    unsupported: list[str] = []
    if b2 not in _WINNER_ONLY["B2"]:
        unsupported.append(b2)
    if b3 not in _WINNER_ONLY["B3"]:
        unsupported.append(b3)
    if b4 not in _WINNER_ONLY["B4"]:
        unsupported.append(b4)
    if b5 not in _WINNER_ONLY["B5"]:
        unsupported.append(b5)
    if unsupported:
        joined = ",".join(unsupported)
        raise ValueError(f"unsupported winner-purged variants: {joined}")
    return WebPlan(provider=_B1_PROVIDER[b1], cache=_B2_CACHE[b2])


def select_winner(all_results: list[dict[str, Any]]) -> str:
    if not all_results:
        raise ValueError("Empty run list")

    # Selection rule: lexicographic max on (acc, -bytes, -chunks, -fetches, cache_hit)
    winner = max(
        all_results,
        key=lambda r: metric_tuple(
            {
                "acc": float(r["acc"]),
                "fetches": int(r["fetches"]),
                "bytes": int(r["bytes"]),
                "chunks": int(r["chunks"]),
                "cache_hit": float(r["cache_hit"]),
            }
        ),
    )

    return str(winner["plan_id"])


def _run_eval_plan(
    *,
    plan_str: str,
    plan: WebPlan,
    queries_path: Path,
    responses_path: Path,
    out_dir: Path,
) -> EvalPlanSummary:
    plan_json = canonical_json(asdict(plan))
    output_file = out_dir / f"result_{plan_str}.jsonl"
    cache_dir = out_dir / f"cache_{plan_str}"
    cache_dir.mkdir(exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pirml.web.eval_shard",
        "--queries",
        str(queries_path),
        "--plan",
        plan_json,
        "--output",
        str(output_file),
        "--responses",
        str(responses_path),
        "--cache-dir",
        str(cache_dir),
    ]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        err = _typed_error(
            "eval_runner_failed",
            f"eval_shard failed for {plan_str}: rc={proc.returncode}",
            retryable=False,
        )
        return {
            "plan_id": plan_str,
            "plan": asdict(plan),
            "ok": False,
            "acc": 0.0,
            "fetches": 0.0,
            "bytes": 0.0,
            "chunks": 0.0,
            "cache_hit": 0.0,
            "error": err,
        }
    rows = [
        cast(dict[str, Any], json.loads(line))
        for line in output_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        err = _typed_error("eval_rows_empty", f"eval_shard emitted no rows for {plan_str}")
        return {
            "plan_id": plan_str,
            "plan": asdict(plan),
            "ok": False,
            "acc": 0.0,
            "fetches": 0.0,
            "bytes": 0.0,
            "chunks": 0.0,
            "cache_hit": 0.0,
            "error": err,
        }
    return {
        "plan_id": plan_str,
        "plan": asdict(plan),
        "ok": True,
        "acc": sum(float(r["acc"]) for r in rows) / len(rows),
        "fetches": sum(float(r["fetches"]) for r in rows) / len(rows),
        "bytes": sum(float(r["bytes"]) for r in rows) / len(rows),
        "chunks": sum(float(r["chunks"]) for r in rows) / len(rows),
        "cache_hit": sum(float(r["cache_hit"]) for r in rows) / len(rows),
        "error": None,
    }


def main() -> int:
    bets_path = Path("spec-0/05/60-bets.jsonl")
    with bets_path.open("r") as f:
        matrix_def = [json.loads(line) for line in f if '"k":"matrix"' in line][0]

    plans = matrix_def["plans"]
    queries_path = Path("tests/fixtures/web/corpus.jsonl")
    responses_path = Path("tests/fixtures/web/responses.json")
    out_dir = Path("out/web_eval")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[EvalPlanSummary] = []

    for plan_str in plans:
        try:
            plan = resolve_plan(plan_str)
        except ValueError as exc:
            all_results.append(
                {
                    "plan_id": plan_str,
                    "plan": None,
                    "ok": False,
                    "acc": 0.0,
                    "fetches": 0.0,
                    "bytes": 0.0,
                    "chunks": 0.0,
                    "cache_hit": 0.0,
                    "error": _typed_error("unsupported_plan", str(exc), retryable=False),
                }
            )
            continue
        all_results.append(
            _run_eval_plan(
                plan_str=plan_str,
                plan=plan,
                queries_path=queries_path,
                responses_path=responses_path,
                out_dir=out_dir,
            )
        )

    winners_pool = [r for r in all_results if r["ok"]]
    if not winners_pool:
        final_output = {"results": all_results, "winner": None}
        Path("out/web_eval.json").write_text(canonical_json(final_output), encoding="utf-8")
        Path("out/web_eval.canonical.json").write_text(
            canonical_json(
                {
                    "winner_id": None,
                    "winner_metrics": None,
                    "error": _typed_error("no_runnable_plans", "all matrix plans failed"),
                }
            ),
            encoding="utf-8",
        )
        return 1

    winner_id = select_winner(cast(list[dict[str, Any]], winners_pool))
    winner = [r for r in winners_pool if r["plan_id"] == winner_id][0]

    final_output = {"results": all_results, "winner": winner}
    Path("out/web_eval.json").write_text(canonical_json(final_output), encoding="utf-8")

    canonical_verdict = {
        "winner_id": winner["plan_id"],
        "winner_metrics": {
            "acc": round(float(winner["acc"]), 4),
            "bytes_q": int(winner["bytes"]),
            "chunks_q": int(winner["chunks"]),
            "fetches_q": int(winner["fetches"]),
            "cache_hit": round(float(winner["cache_hit"]), 4),
        },
    }
    Path("out/web_eval.canonical.json").write_text(
        canonical_json(canonical_verdict), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
