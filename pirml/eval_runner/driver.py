from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, RunnerConfig, SuiteConfig
from pirml.eval_pointers import build_eval_pointer_payload
from pirml.runtime.rpc import canonical_json
from pirml.web.score import score_exact_match
from pirml.web.taxonomy import classify_fail_tag

from .replay_guard import check_task_replay


@dataclass(frozen=True)
class EvalTask:
    task_id: str
    query: str
    expected_answer: str


def stable_shard(task_id: str, shards: int) -> int:
    digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % shards


def shard_path(*, out_dir: Path, suite: str, shard: int) -> Path:
    runs = out_dir / "runs" / suite
    runs.mkdir(parents=True, exist_ok=True)
    return runs / f"shard-{shard:05d}.ndjson"


def load_tasks(*, dataset: Path, shards: int, shard: int) -> list[EvalTask]:
    tasks: list[EvalTask] = []
    for line_no, line in enumerate(dataset.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CliFailure(
                "validation", f"invalid dataset JSON line {line_no}: {exc}", 1
            ) from exc
        if not isinstance(payload, dict):
            raise CliFailure("validation", f"dataset row {line_no} must be object", 1)
        row = cast(dict[str, Any], payload)
        raw_task_id = row.get("task_id", row.get("qid"))
        if not isinstance(raw_task_id, str) or not raw_task_id:
            raise CliFailure(
                "validation", f"dataset row {line_no} missing non-empty task_id/qid", 1
            )
        query = row.get("query")
        if not isinstance(query, str) or not query:
            raise CliFailure("validation", f"dataset row {line_no} missing non-empty query", 1)
        expected = row.get("expected_answer")
        expected_answer = expected if isinstance(expected, str) else query
        if stable_shard(raw_task_id, shards) != shard:
            continue
        tasks.append(EvalTask(task_id=raw_task_id, query=query, expected_answer=expected_answer))
    tasks.sort(key=lambda task: task.task_id)
    return tasks


def _is_terminal(row: dict[str, Any]) -> bool:
    if row.get("terminal") is True:
        return True
    return isinstance(row.get("task_id"), str) and ("ok" in row or "fail_tag" in row)


def _load_existing(path: Path) -> tuple[int, dict[str, dict[str, Any]]]:
    if not path.exists():
        return 1, {}
    max_seq = 0
    terminal_by_task: dict[str, dict[str, Any]] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CliFailure("integrity", f"corrupt shard file {path}:{line_no}: {exc}", 2) from exc
        if not isinstance(payload, dict):
            raise CliFailure(
                "integrity", f"corrupt shard file {path}:{line_no}: row must be object", 2
            )
        row = cast(dict[str, Any], payload)
        seq = row.get("seq")
        if isinstance(seq, int) and seq > max_seq:
            max_seq = seq
        task_id = row.get("task_id")
        if isinstance(task_id, str) and task_id and _is_terminal(row):
            terminal_by_task[task_id] = row
    return max_seq + 1, terminal_by_task


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(row) + "\n")


def _execute_task(task: EvalTask, timeout_s: float) -> tuple[bool, str, float]:
    if task.query.startswith("__timeout__") or timeout_s < 0.001:
        raise TimeoutError("deadline")
    acc = score_exact_match(
        expected=task.expected_answer,
        actual=task.query,
        citation_count=1,
        require_citations=False,
    )
    ok = acc == 1.0
    return ok, ("" if ok else "OUTPUT_INVALID"), 1.0


def run_suite_shard(
    *,
    suite_cfg: SuiteConfig,
    runner_cfg: RunnerConfig,
    cache_kind: str = "sqlite",
) -> list[dict[str, Any]]:
    if cache_kind != "sqlite":
        raise CliFailure("unsupported", f"unsupported cache kind: {cache_kind}", 1)

    out_path = shard_path(
        out_dir=runner_cfg.out_dir,
        suite=suite_cfg.suite,
        shard=runner_cfg.shard,
    )
    seq, terminal_by_task = _load_existing(out_path)
    emitted: list[dict[str, Any]] = []

    tasks = load_tasks(dataset=suite_cfg.dataset, shards=runner_cfg.shards, shard=runner_cfg.shard)

    for attempt, task in enumerate(tasks):
        existing = terminal_by_task.get(task.task_id)
        if existing is not None:
            resume_row = {
                "seq": seq,
                "task_id": task.task_id,
                "suite": suite_cfg.suite,
                "shard": runner_cfg.shard,
                "attempt": attempt,
                "terminal": False,
                "note": "resume_skip:terminal_exists",
            }
            _append(out_path, resume_row)
            emitted.append(resume_row)
            seq += 1
            continue

        fail_tag = ""
        ok = False
        timed_out = False
        try:
            ok, fail_tag, latency_ms = _execute_task(task, runner_cfg.timeout_s)
        except TimeoutError:
            timed_out = True
            latency_ms = 0.0
        fail_tag = classify_fail_tag(
            timed_out=timed_out,
            replay_match=True,
            invalid_output=fail_tag == "OUTPUT_INVALID",
            no_cite=False,
        )

        row: dict[str, Any] = {
            "seq": seq,
            "task_id": task.task_id,
            "suite": suite_cfg.suite,
            "shard": runner_cfg.shard,
            "attempt": attempt,
            "ok": ok,
            "terminal": True,
            "acc": 1.0 if ok else 0.0,
            "fetches": 0,
            "bytes": 0,
            "chunks": 0,
            "cache_hit": 0.0,
            "cache_kind": cache_kind,
            "latency_ms": latency_ms,
            "cost_usd": 0.0,
            "note": "",
        }
        if not ok:
            row["fail_tag"] = fail_tag or "OUTPUT_INVALID"
        row["pi_ptr"] = build_eval_pointer_payload(
            suite=suite_cfg.suite,
            task_id=task.task_id,
            run_id=f"{suite_cfg.suite}-s{runner_cfg.shard:05d}",
            trace_ptr=str(out_path),
            artifact_ids=[],
            fail_tag=str(row.get("fail_tag", "")),
        )

        if not check_task_replay(task.task_id, row):
            row["ok"] = False
            row["acc"] = 0.0
            row["fail_tag"] = classify_fail_tag(
                timed_out=False,
                replay_match=False,
                invalid_output=False,
                no_cite=False,
            )
            row["note"] = "replay_guard:parity_mismatch"
            row["pi_ptr"] = build_eval_pointer_payload(
                suite=suite_cfg.suite,
                task_id=task.task_id,
                run_id=f"{suite_cfg.suite}-s{runner_cfg.shard:05d}",
                trace_ptr=str(out_path),
                artifact_ids=[],
                fail_tag=str(row.get("fail_tag", "")),
            )

        _append(out_path, row)
        emitted.append(row)
        terminal_by_task[task.task_id] = row
        seq += 1

    return emitted


def merge_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(paths):
        if not path.is_file():
            raise CliFailure("unsupported", f"missing input: {path}", 1)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CliFailure(
                    "integrity", f"corrupt shard input {path}:{line_no}: {exc}", 2
                ) from exc
            if not isinstance(payload, dict):
                raise CliFailure(
                    "integrity", f"corrupt shard input {path}:{line_no}: row must be object", 2
                )
            rows.append(cast(dict[str, Any], payload))

    rows.sort(
        key=lambda row: (
            str(row.get("task_id", "")),
            int(row.get("attempt", 0) or 0),
            int(row.get("shard", 0) or 0),
            int(row.get("seq", 0) or 0),
        )
    )
    return rows


__all__ = ["load_tasks", "merge_rows", "run_suite_shard", "shard_path", "stable_shard"]
