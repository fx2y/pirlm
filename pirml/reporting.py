from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from .cli_common import CliFailure
from .eval_runner import merge_rows


def _task_sort_key(row: dict[str, Any]) -> tuple[str, int, int, int]:
    return (
        str(row.get("task_id", "")),
        int(row.get("attempt", 0) or 0),
        int(row.get("shard", 0) or 0),
        int(row.get("seq", 0) or 0),
    )


def read_eval_rows(paths: list[str]) -> list[dict[str, Any]]:
    rows = merge_rows([Path(p) for p in paths])
    return [cast(dict[str, Any], row) for row in rows]


def _terminal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terminal = [
        row for row in rows if bool(row.get("terminal")) and isinstance(row.get("task_id"), str)
    ]
    terminal.sort(key=_task_sort_key)
    seen: set[tuple[str, str]] = set()
    for row in terminal:
        key = (str(row.get("suite", "")), str(row.get("task_id", "")))
        if key in seen:
            raise CliFailure(
                "integrity",
                f"duplicate terminal row for suite/task_id: {key[0]}/{key[1]}",
                2,
                retryable=False,
            )
        seen.add(key)
    return terminal


def _fail_tag(row: dict[str, Any]) -> str:
    raw = row.get("fail_tag", "")
    if isinstance(raw, str):
        value = raw.strip()
    else:
        raise CliFailure("validation", "fail_tag must be string when present", 1, retryable=False)
    if value and any(ch in value for ch in ("|", ",", ";")):
        raise CliFailure(
            "validation", f"fail_tag must be single-label: {value}", 1, retryable=False
        )
    return value


def _safe_ratio(numerator: float, denominator: float, note: str) -> tuple[float, str | None]:
    if denominator <= 0.0:
        return 0.0, note
    return numerator / denominator, None


def aggregate_report(
    rows: list[dict[str, Any]], *, inputs: list[str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    terminal_rows = _terminal_rows(rows)
    if not terminal_rows:
        raise CliFailure("unsupported", "no terminal rows to aggregate", 1, retryable=False)

    total = len(terminal_rows)
    ok_rows = [row for row in terminal_rows if bool(row.get("ok"))]
    fail_rows = [row for row in terminal_rows if not bool(row.get("ok"))]
    failed_tags: Counter[str] = Counter()
    failed_ids_by_tag: dict[str, Counter[str]] = defaultdict(Counter)
    for row in fail_rows:
        tag = _fail_tag(row) or "UNKNOWN_FAIL"
        task_id = str(row.get("task_id", ""))
        failed_tags[tag] += 1
        failed_ids_by_tag[tag][task_id] += 1

    acc = len(ok_rows) / total
    latencies = [float(row.get("latency_ms", 0.0) or 0.0) for row in terminal_rows]
    costs = [float(row.get("cost_usd", 0.0) or 0.0) for row in terminal_rows]
    total_cost = sum(costs)
    total_latency_ms = sum(latencies)

    acc_per_dollar, note_dollar = _safe_ratio(
        float(len(ok_rows)),
        total_cost,
        "acc_per_$ denominator=0 => 0.0",
    )
    acc_per_min, note_min = _safe_ratio(
        float(len(ok_rows)),
        total_latency_ms / 60000.0,
        "acc_per_min denominator=0 => 0.0",
    )
    notes = [note for note in [note_dollar, note_min] if note is not None]

    ordered_tags = sorted(failed_tags.items(), key=lambda item: (-item[1], item[0]))
    fail_pareto: list[dict[str, Any]] = []
    for tag, count in ordered_tags:
        top_ids = sorted(failed_ids_by_tag[tag].items(), key=lambda item: (-item[1], item[0]))
        fail_pareto.append(
            {
                "fail_tag": tag,
                "count": count,
                "top_task_ids": [
                    {"task_id": task_id, "count": task_count}
                    for task_id, task_count in top_ids[:10]
                ],
            }
        )

    fail_tag_map = dict(failed_tags)
    timeout_rate = fail_tag_map.get("TIMEOUT", 0) / total
    invalid_rate = fail_tag_map.get("OUTPUT_INVALID", 0) / total
    no_cite_rate = fail_tag_map.get("NO_CITE", 0) / total
    replay_mismatch_rate = fail_tag_map.get("REPLAY_MISMATCH", 0) / total

    suite_values = sorted(
        {str(row.get("suite", "")) for row in terminal_rows if str(row.get("suite", ""))}
    )
    report = {
        "ok": True,
        "suite": suite_values[0] if len(suite_values) == 1 else "mixed",
        "suites": suite_values,
        "input_paths": sorted(inputs),
        "total_tasks": total,
        "acc": round(acc, 6),
        "acc_per_$": round(acc_per_dollar, 6),
        "acc_per_min": round(acc_per_min, 6),
        "median_latency": round(statistics.median(latencies), 6),
        "median_cost": round(statistics.median(costs), 6),
        "timeout_rate": round(timeout_rate, 6),
        "invalid_output_rate": round(invalid_rate, 6),
        "no_cite_rate": round(no_cite_rate, 6),
        "replay_mismatch_rate": round(replay_mismatch_rate, 6),
        "fail_pareto": fail_pareto,
        "kpi_wall": {
            "acc": round(acc, 6),
            "acc_per_$": round(acc_per_dollar, 6),
            "acc_per_min": round(acc_per_min, 6),
            "median_latency": round(statistics.median(latencies), 6),
            "median_cost": round(statistics.median(costs), 6),
            "timeout_rate": round(timeout_rate, 6),
            "invalid_output_rate": round(invalid_rate, 6),
            "no_cite_rate": round(no_cite_rate, 6),
            "replay_mismatch_rate": round(replay_mismatch_rate, 6),
        },
        "meta": {
            "notes": sorted(notes),
            "formulas": {
                "acc_per_$": "ok_count / sum(cost_usd)",
                "acc_per_min": "ok_count / (sum(latency_ms)/60000)",
                "median_latency": "median(latency_ms)",
                "median_cost": "median(cost_usd)",
            },
        },
    }
    pareto = {"ok": True, "total_failures": len(fail_rows), "fail_pareto": fail_pareto}
    return report, pareto
