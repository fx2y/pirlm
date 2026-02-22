from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, RunnerConfig, SuiteConfig
from pirml.eval_pointers import build_eval_pointer_payload
from pirml.runtime.rpc import canonical_json
from pirml.web.score import score_exact_match
from pirml.web.taxonomy import classify_fail_tag

from .replay_guard import ReplaySnapshot, check_task_replay
from .timeouts import classify_timeout


@dataclass(frozen=True)
class EvalTask:
    task_id: str
    query: str
    expected_answer: str


@dataclass(frozen=True)
class TaskOutcome:
    ok: bool
    fail_tag: str
    latency_ms: float


def stable_shard(task_id: str, shards: int) -> int:
    digest = hashlib.sha1(task_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % shards


def shard_path(*, out_dir: Path, suite: str, shard: int) -> Path:
    runs = out_dir / "runs" / suite
    runs.mkdir(parents=True, exist_ok=True)
    return runs / f"shard-{shard:05d}.ndjson"


def _first_nonempty_str(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def load_tasks(*, dataset: Path, shards: int, shard: int) -> list[EvalTask]:
    tasks: list[EvalTask] = []
    seen_task_ids: set[str] = set()
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
        if raw_task_id in seen_task_ids:
            raise CliFailure("validation", f"duplicate task_id in dataset: {raw_task_id}", 1)
        seen_task_ids.add(raw_task_id)
        query = _first_nonempty_str(row, "query", "question", "prompt")
        if query is None:
            raise CliFailure(
                "validation",
                f"dataset row {line_no} missing non-empty query/question/prompt",
                1,
            )
        expected_answer = _first_nonempty_str(row, "expected_answer", "answer", "query") or query
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
    expected_seq = 1
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
        if not isinstance(seq, int):
            raise CliFailure(
                "integrity", f"corrupt shard file {path}:{line_no}: seq must be int", 2
            )
        if seq != expected_seq:
            raise CliFailure(
                "integrity",
                f"corrupt shard file {path}:{line_no}: seq drift expected {expected_seq} got {seq}",
                2,
            )
        expected_seq += 1
        task_id = row.get("task_id")
        if isinstance(task_id, str) and task_id and _is_terminal(row):
            if task_id in terminal_by_task:
                raise CliFailure(
                    "integrity",
                    f"corrupt shard file {path}:{line_no}: duplicate terminal task_id {task_id}",
                    2,
                )
            terminal_by_task[task_id] = row
    return expected_seq, terminal_by_task


def _append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(row) + "\n")


def _run_id(*, suite: str, shard: int) -> str:
    return f"{suite}-s{shard:05d}"


def _with_pi_ptr(
    *,
    row: dict[str, Any],
    suite: str,
    task_id: str,
    trace_path_str: str,
    shard: int,
) -> dict[str, Any]:
    row["pi_ptr"] = build_eval_pointer_payload(
        suite=suite,
        task_id=task_id,
        run_id=_run_id(suite=suite, shard=shard),
        trace_ptr=trace_path_str,
        artifact_ids=[],
        fail_tag=str(row.get("fail_tag", "")),
    )
    return row


def _task_trace_path(*, out_dir: Path, suite: str, shard: int, task_id: str) -> Path:
    trace_dir = out_dir / "traces" / suite / f"shard-{shard:05d}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir / f"{task_id}.ndjson"


def _write_task_trace_stub(path: Path, *, task: EvalTask, seq: int) -> None:
    frame = {"seq": seq, "task_id": task.task_id, "query": task.query}
    path.write_text(canonical_json(frame) + "\n", encoding="utf-8")


def _resume_skip_row(
    *, seq: int, task: EvalTask, suite: str, shard: int, attempt: int
) -> dict[str, Any]:
    return {
        "seq": seq,
        "task_id": task.task_id,
        "suite": suite,
        "shard": shard,
        "attempt": attempt,
        "terminal": False,
        "note": "resume_skip:terminal_exists",
    }


def _execute_task(
    task: EvalTask, timeout_s: float, *, ctx_byte_cap: int, seed: int
) -> tuple[bool, str, float]:
    if task.query.startswith("__timeout__") or timeout_s < 0.001:
        raise TimeoutError("deadline")
    _ = seed  # deterministic seam owner; stub runner has no RNG path yet.
    if len(task.query.encode("utf-8")) > ctx_byte_cap:
        return False, "CTX_BLOAT", 1.0
    acc = score_exact_match(
        expected=task.expected_answer,
        actual=task.query,
        citation_count=1,
        require_citations=False,
    )
    ok = acc == 1.0
    return ok, ("" if ok else "OUTPUT_INVALID"), 1.0


def _evaluate_task(
    *,
    task: EvalTask,
    timeout_s: float,
    ctx_byte_cap: int,
    seed: int,
) -> TaskOutcome:
    fail_tag = ""
    ok = False
    timed_out = False
    try:
        ok, fail_tag, latency_ms = _execute_task(
            task,
            timeout_s,
            ctx_byte_cap=ctx_byte_cap,
            seed=seed,
        )
    except TimeoutError:
        timed_out = True
        latency_ms = 0.0
    base_fail_tag = classify_timeout(timed_out=timed_out, base_fail_tag=fail_tag)
    mapped_fail_tag = classify_fail_tag(
        timed_out=timed_out,
        replay_match=True,
        invalid_output=base_fail_tag == "OUTPUT_INVALID",
        no_cite=False,
    )
    if not ok and base_fail_tag == "CTX_BLOAT":
        row_fail_tag = "CTX_BLOAT"
    else:
        row_fail_tag = mapped_fail_tag or ("OUTPUT_INVALID" if not ok else "")
    return TaskOutcome(ok=ok, fail_tag=row_fail_tag, latency_ms=latency_ms)


def _replay_snapshot(*, task: EvalTask, runner_cfg: RunnerConfig) -> ReplaySnapshot:
    replay_outcome = _evaluate_task(
        task=task,
        timeout_s=runner_cfg.timeout_s,
        ctx_byte_cap=runner_cfg.ctx_byte_cap,
        seed=runner_cfg.seed,
    )
    return ReplaySnapshot(
        ok=replay_outcome.ok,
        fail_tag=replay_outcome.fail_tag,
        latency_ms=replay_outcome.latency_ms,
    )


def run_suite_shard(
    *,
    suite_cfg: SuiteConfig,
    runner_cfg: RunnerConfig,
    cache_kind: str = "sqlite",
) -> list[dict[str, Any]]:
    if cache_kind != "sqlite":
        raise CliFailure("unsupported", f"unsupported cache kind: {cache_kind}", 1)
    if runner_cfg.jobs != 1:
        raise CliFailure("unsupported", "--jobs > 1 not implemented for single-shard runner", 1)

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
            resume_row = _resume_skip_row(
                seq=seq,
                task=task,
                suite=suite_cfg.suite,
                shard=runner_cfg.shard,
                attempt=attempt,
            )
            _append(out_path, resume_row)
            emitted.append(resume_row)
            seq += 1
            continue

        outcome = _evaluate_task(
            task=task,
            timeout_s=runner_cfg.timeout_s,
            ctx_byte_cap=runner_cfg.ctx_byte_cap,
            seed=runner_cfg.seed,
        )

        trace_path = _task_trace_path(
            out_dir=runner_cfg.out_dir,
            suite=suite_cfg.suite,
            shard=runner_cfg.shard,
            task_id=task.task_id,
        )
        _write_task_trace_stub(trace_path, task=task, seq=seq)

        row: dict[str, Any] = {
            "seq": seq,
            "task_id": task.task_id,
            "suite": suite_cfg.suite,
            "shard": runner_cfg.shard,
            "attempt": attempt,
            "ok": outcome.ok,
            "terminal": True,
            "acc": 1.0 if outcome.ok else 0.0,
            "fetches": 0,
            "bytes": 0,
            "chunks": 0,
            "cache_hit": 0.0,
            "cache_kind": cache_kind,
            "latency_ms": outcome.latency_ms,
            "cost_usd": 0.0,
            "note": "",
            "replay_match": True,
        }
        if not outcome.ok:
            row["fail_tag"] = outcome.fail_tag
        _with_pi_ptr(
            row=row,
            suite=suite_cfg.suite,
            task_id=task.task_id,
            trace_path_str=os.path.relpath(trace_path, out_path.parent),
            shard=runner_cfg.shard,
        )

        replay_task = task
        replay = check_task_replay(
            task_id=task.task_id,
            live=ReplaySnapshot(
                ok=outcome.ok,
                fail_tag=outcome.fail_tag,
                latency_ms=outcome.latency_ms,
            ),
            replay_run=lambda task_for_replay=replay_task: _replay_snapshot(
                task=task_for_replay,
                runner_cfg=runner_cfg,
            ),
        )
        if not replay.match:
            row["ok"] = False
            row["acc"] = 0.0
            row["replay_match"] = False
            row["fail_tag"] = classify_fail_tag(
                timed_out=False,
                replay_match=False,
                invalid_output=False,
                no_cite=False,
            )
            row["note"] = replay.note or "replay_guard:parity_mismatch"
            _with_pi_ptr(
                row=row,
                suite=suite_cfg.suite,
                task_id=task.task_id,
                trace_path_str=os.path.relpath(trace_path, out_path.parent),
                shard=runner_cfg.shard,
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
            row = cast(dict[str, Any], payload)
            row["_source_path"] = str(path)
            rows.append(row)

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
