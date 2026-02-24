from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import tomllib
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args
from scripts.spec10_matrix import DEFAULT_MATRIX_PATH, get_matrix_rows

_REQUIRED_LANES = tuple(f"W{i}" for i in range(11))

_LANE_POINTER_CANDIDATES: dict[str, tuple[tuple[str, str], ...]] = {
    "W0": (("trace_ptr", "out/demo/trace.ndjson"), ("final_ptr", "out/demo/final.json")),
    "W1": (
        ("trace_ptr", "out/w1/live/trace.ndjson"),
        ("final_ptr", "out/w1/live/final.json"),
        ("artifact_ptr", "out/w1/replay/final.json"),
    ),
    "W2": (("artifact_ptr", "out/w2/tools/acme.lookup.json"),),
    "W3": (
        ("artifact_ptr", "out/w3/compile/prog.py"),
        ("artifact_ptr", "out/w3/compile/contract.json"),
        ("artifact_ptr", "out/w3/compile/compile_error.json"),
    ),
    "W4": (
        ("report_ptr", "out/web_smoke/web_output.json"),
        ("trace_ptr", "out/web_smoke/web_trace.ndjson"),
        ("details_ptr", "out/web_smoke/eval.ndjson"),
    ),
    "W5": (("trace_ptr", "out/ci/trace.ndjson"), ("final_ptr", "out/ci/final.json")),
    "W6": (("trace_ptr", "out/w6/trace.ndjson"), ("final_ptr", "out/w6/final.json")),
    "W7": (("report_ptr", "out/eval/full/report.json"),),
    "W8": (("trace_ptr", "out/ci/trace.ndjson"), ("final_ptr", "out/ci/final.json")),
    "W9": (
        ("report_ptr", "out/spec10_incident/incident.json"),
        ("details_ptr", "out/spec10_incident/incident.details.json"),
    ),
    "W10": (("trace_ptr", "out/ci/trace.ndjson"), ("final_ptr", "out/ci/final.json")),
    "W4b": (("report_ptr", "out/web_smoke/web_output.json"),),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec-10 proof-pack orchestrator")
    parser.add_argument(
        "--out",
        type=str,
        default="out/spec10_pack/index.jsonl",
        help="Output pack index path",
    )
    parser.add_argument(
        "--matrix",
        type=str,
        default=str(DEFAULT_MATRIX_PATH),
        help="Authority matrix JSONL path",
    )
    parser.add_argument(
        "--include-live",
        action="store_true",
        help="Include optional live lane W4b",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip command execution and emit index from existing artifacts",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=300.0,
        help="Per-subcommand timeout in seconds",
    )
    return parser


def _compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_mise_tasks(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CliFailure("integrity", f"missing mise task contract: {path}", 2, retryable=False)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise CliFailure("integrity", f"invalid mise contract: {exc}", 2, retryable=False) from exc
    tasks_raw = data.get("tasks")
    if not isinstance(tasks_raw, dict):
        raise CliFailure("integrity", "missing [tasks] in .mise.toml", 2, retryable=False)
    typed_tasks = cast(dict[object, Any], tasks_raw)
    return {str(k): v for k, v in typed_tasks.items()}


def _validate_eval_ingress(*, lane: str, command: str, tasks: dict[str, Any]) -> None:
    if lane != "W7":
        return
    normalized = command.strip()
    if "mise run eval-" in normalized:
        for task_name in ("eval-golden", "eval-full"):
            task = tasks.get(task_name, {})
            run = str(task.get("run", ""))
            if "--dataset" not in run:
                raise CliFailure(
                    "integrity",
                    f"task `{task_name}` missing explicit --dataset ingress",
                    2,
                    retryable=False,
                )
        report_task = tasks.get("eval-report", {})
        report_run = str(report_task.get("run", ""))
        if "pirml.report" not in report_run or "out/eval/full/runs/" not in report_run:
            raise CliFailure(
                "integrity",
                "task `eval-report` missing explicit report shard ingress",
                2,
                retryable=False,
            )
        return

    if "pirml.eval" in normalized and "--dataset" not in normalized:
        raise CliFailure("validation", "W7 eval command missing --dataset", 1, retryable=False)
    if "pirml.report" in normalized and " --out " not in normalized:
        raise CliFailure(
            "validation", "W7 report command missing explicit --out", 1, retryable=False
        )


def _split_chain(command: str) -> list[list[str]]:
    segments = [segment.strip() for segment in command.split("&&")]
    if not segments or any(not segment for segment in segments):
        raise CliFailure("validation", f"invalid command chain: {command}", 1, retryable=False)
    argv_segments: list[list[str]] = []
    for segment in segments:
        if "||" in segment or "|" in segment or ";" in segment:
            raise CliFailure(
                "unsupported",
                f"unsupported shell operator in lane command: {segment}",
                1,
                retryable=False,
            )
        argv = shlex.split(segment)
        if not argv:
            raise CliFailure("validation", f"empty command segment: {command}", 1, retryable=False)
        argv_segments.append(argv)
    return argv_segments


def _run_segments(
    argv_segments: list[list[str]],
    *,
    timeout_s: float,
) -> tuple[int, list[dict[str, Any]]]:
    if timeout_s <= 0:
        raise CliFailure("validation", "--timeout-s must be > 0", 1, retryable=False)
    runs: list[dict[str, Any]] = []
    for index, argv in enumerate(argv_segments, start=1):
        try:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            runs.append(
                {
                    "step": index,
                    "argv": argv,
                    "rc": 1,
                    "timeout_s": timeout_s,
                    "stdout": str(exc.stdout or ""),
                    "stderr": str(exc.stderr or ""),
                    "timed_out": True,
                }
            )
            return 1, runs
        runs.append(
            {
                "step": index,
                "argv": argv,
                "rc": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "timed_out": False,
            }
        )
        if proc.returncode != 0:
            return proc.returncode, runs
    return 0, runs


def _find_lane_pointers(lane: str, *, repo_root: Path) -> dict[str, str]:
    pointers: dict[str, str] = {}
    for key, relative in _LANE_POINTER_CANDIDATES.get(lane, ()):
        if key in pointers:
            continue
        candidate = (repo_root / relative).resolve()
        if candidate.is_file():
            pointers[key] = str(candidate)
    return pointers


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _validate_pointer_resolve(path_value: str) -> None:
    path = Path(path_value)
    if not path.is_file():
        raise CliFailure("integrity", f"unresolved pointer: {path}", 2, retryable=False)


def main() -> int:
    parser = _build_parser()
    try:
        args = strict_parse_args(parser)
        matrix_rows = get_matrix_rows(Path(args.matrix))
        mise_tasks = _load_mise_tasks(Path(".mise.toml"))
    except CliFailure as err:
        return emit_failure(err)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lane_dir = out_path.parent / "lanes"
    lane_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path.cwd().resolve()

    rows = [
        row
        for row in matrix_rows
        if row.get("k") == "row" and str(row.get("lane", "")) in _REQUIRED_LANES
    ]
    rows.sort(key=lambda row: int(str(row["lane"])[1:]))
    if args.include_live:
        rows.append(
            {
                "k": "row",
                "lane": "W4b",
                "name": "Live web smoke",
                "cmd": "python -m scripts.web_smoke",
                "authority": False,
                "deps": ["W4"],
                "deterministic": False,
                "optional": True,
            }
        )

    pack_rows: list[dict[str, Any]] = [
        {
            "k": "meta",
            "id": "spec10-proof-pack",
            "matrix_ptr": str(Path(args.matrix).resolve()),
            "out_ptr": str(out_path),
        }
    ]
    required_lane_failures: list[str] = []

    for row in rows:
        lane = str(row["lane"])
        name = str(row.get("name", ""))
        command = str(row.get("cmd", "")).strip()
        if not command:
            return emit_failure(
                CliFailure("integrity", f"lane missing cmd: {lane}", 2, retryable=False)
            )
        try:
            _validate_eval_ingress(lane=lane, command=command, tasks=mise_tasks)
            argv_segments = _split_chain(command)
        except CliFailure as err:
            return emit_failure(err)

        lane_artifacts = lane_dir / lane
        lane_artifacts.mkdir(parents=True, exist_ok=True)
        details_path = (lane_artifacts / "details.json").resolve()
        run_log: dict[str, Any]
        rc: int
        if args.skip_run:
            rc = 0
            run_log = {"skipped": True, "segments": argv_segments}
        else:
            rc, segment_logs = _run_segments(argv_segments, timeout_s=float(args.timeout_s))
            run_log = {"skipped": False, "segments": segment_logs}
            if rc != 0 and lane in _REQUIRED_LANES:
                required_lane_failures.append(lane)

        _write_json(
            details_path,
            {
                "lane": lane,
                "name": name,
                "authority": bool(row.get("authority", True)),
                "deterministic": bool(row.get("deterministic", True)),
                "optional": bool(row.get("optional", False)),
                "command": command,
                "run": run_log,
                "rc": rc,
            },
        )

        pointer_fields = _find_lane_pointers(lane, repo_root=repo_root)
        pointer_fields["details_ptr"] = str(details_path)
        for pointer in pointer_fields.values():
            _validate_pointer_resolve(pointer)

        primary_pointer = (
            pointer_fields.get("final_ptr")
            or pointer_fields.get("report_ptr")
            or pointer_fields.get("trace_ptr")
            or pointer_fields.get("artifact_ptr")
            or pointer_fields["details_ptr"]
        )
        pack_row: dict[str, Any] = {
            "k": "row",
            "lane": lane,
            "name": name,
            "cmd": command,
            "rc": rc,
            "authority": bool(row.get("authority", True)),
            "deterministic": bool(row.get("deterministic", True)),
            "optional": bool(row.get("optional", False)),
            "sha256": _compute_sha256(Path(primary_pointer)),
        }
        pack_row.update(pointer_fields)
        if lane in _REQUIRED_LANES and not any(
            key in pack_row for key in ("trace_ptr", "final_ptr", "report_ptr", "details_ptr")
        ):
            return emit_failure(
                CliFailure("integrity", f"lane missing pointers: {lane}", 2, retryable=False)
            )
        pack_rows.append(pack_row)

    _write_jsonl(out_path, pack_rows)

    if required_lane_failures:
        failed = ",".join(required_lane_failures)
        return emit_failure(
            CliFailure("validation", f"required lanes failed: {failed}", 1, retryable=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
