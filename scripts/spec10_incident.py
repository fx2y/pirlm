from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args
from pirml.protocol import ProtocolError, load_jsonl, validate_strict_trace
from pirml.web.taxonomy import FAIL_TAGS, classify_fail_tag


@dataclass(frozen=True)
class IncidentResult:
    report: dict[str, Any]
    details: dict[str, Any]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec-10 incident one-command bundle")
    parser.add_argument("--trace", required=True, help="Path to source trace.ndjson")
    parser.add_argument("--out-dir", required=True, help="Output directory for incident artifacts")
    parser.add_argument("--prog", default="tests/prog_ok.py", help="Program path for replay")
    parser.add_argument("--timeout", type=float, default=30.0, help="Replay timeout in seconds")
    return parser


def _run_command(
    cmd: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _extract_fail_tag(frames: list[dict[str, Any]]) -> str:
    # Prefer explicit fail_tag from the final frame, then from final.result, then from any frame.
    sources: list[Any] = []
    if frames:
        final = frames[-1]
        if isinstance(final.get("fail_tag"), str):
            sources.append(final.get("fail_tag"))
        result = final.get("result")
        if isinstance(result, dict):
            result_obj = cast(dict[str, Any], result)
            if isinstance(result_obj.get("fail_tag"), str):
                sources.append(result_obj.get("fail_tag"))
    for frame in frames:
        if isinstance(frame.get("fail_tag"), str):
            sources.append(frame.get("fail_tag"))

    for raw in sources:
        value = str(raw).strip()
        if not value:
            continue
        if any(ch in value for ch in ("|", ",", ";")):
            raise CliFailure(
                "validation", f"fail_tag must be single-label: {value}", 1, retryable=False
            )
        return value
    return ""


def _class_name(*, fail_tag: str, final_ok: bool, replay_match: bool, artifact_parity: bool) -> str:
    if fail_tag:
        if fail_tag not in FAIL_TAGS:
            raise CliFailure("unsupported", f"unknown fail_tag: {fail_tag}", 1, retryable=False)
        return fail_tag

    inferred = classify_fail_tag(
        timed_out=False,
        replay_match=replay_match,
        invalid_output=(not final_ok or not artifact_parity),
        no_cite=False,
    )
    if inferred:
        return inferred
    return "OK"


def _hint(class_name: str, replay_match: bool, artifact_parity: bool, trace_path: Path) -> str:
    text = (
        f"class={class_name} replay_match={str(replay_match).lower()} "
        f"artifact_parity={str(artifact_parity).lower()} trace={trace_path.name}"
    )
    if len(text) <= 120:
        return text
    return text[:117] + "..."


def run_incident(
    *, trace_path: Path, out_dir: Path, prog_path: Path, timeout_s: float
) -> IncidentResult:
    if timeout_s <= 0:
        raise CliFailure("validation", "--timeout must be > 0", 1, retryable=False)
    if not trace_path.is_file():
        raise CliFailure("config", f"trace path not found: {trace_path}", 2, retryable=False)

    out_dir.mkdir(parents=True, exist_ok=True)
    details_path = out_dir / "incident.details.json"
    report_path = out_dir / "incident.json"
    replay_out = out_dir / "replay"

    try:
        frames = load_jsonl(trace_path)
        validate_strict_trace(frames)
    except (OSError, ProtocolError, ValueError) as exc:
        raise CliFailure("integrity", f"trace load failed: {exc}", 2, retryable=False) from exc
    if not frames:
        raise CliFailure("integrity", "trace is empty", 2, retryable=False)

    final_frame = frames[-1]
    final_result = final_frame.get("result")
    if not isinstance(final_result, dict):
        final_result = {}
    final_result_obj = cast(dict[str, Any], final_result)

    source_final = trace_path.parent / "final.json"
    if not source_final.is_file():
        raise CliFailure("integrity", f"missing source final.json near trace: {source_final}", 2)

    replay_cmd = [
        sys.executable,
        "-m",
        "scripts.tools.replay",
        str(prog_path),
        str(trace_path),
        "--out-dir",
        str(replay_out),
        "--timeout",
        str(timeout_s),
    ]
    replay_proc = _run_command(replay_cmd)
    replay_final = replay_out / "final.json"
    replay_match = replay_proc.returncode == 0 and replay_final.is_file()
    source_final_sha = _sha256_path(source_final)
    replay_final_sha = _sha256_path(replay_final) if replay_final.is_file() else ""
    replay_match = replay_match and source_final_sha == replay_final_sha

    artifact_cmd = [sys.executable, "-m", "scripts.artifact_rebuild", "--check"]
    artifact_proc = _run_command(artifact_cmd)
    artifact_parity = artifact_proc.returncode == 0

    fail_tag = _extract_fail_tag(frames)
    final_ok = bool(final_frame.get("ok", False))
    class_name = _class_name(
        fail_tag=fail_tag,
        final_ok=final_ok,
        replay_match=replay_match,
        artifact_parity=artifact_parity,
    )

    failure_reasons: list[str] = []
    if not replay_match:
        failure_reasons.append("replay parity mismatch")
    if not artifact_parity:
        failure_reasons.append("artifact parity check failed")

    report = {
        "class": class_name,
        "rc": 2 if failure_reasons else 0,
        "replay_match": replay_match,
        "artifact_parity": artifact_parity,
        "trace_ptr": str(trace_path),
        "notes": _hint(class_name, replay_match, artifact_parity, trace_path),
        "details_ptr": str(details_path),
    }
    details = {
        "source_final_sha256": source_final_sha,
        "replay_final_sha256": replay_final_sha,
        "replay": {
            "cmd": replay_cmd,
            "rc": replay_proc.returncode,
            "stdout": replay_proc.stdout,
            "stderr": replay_proc.stderr,
        },
        "artifact": {
            "cmd": artifact_cmd,
            "rc": artifact_proc.returncode,
            "stdout": artifact_proc.stdout,
            "stderr": artifact_proc.stderr,
        },
        "final": {
            "ok": final_ok,
            "has_results": isinstance(final_result_obj.get("results"), list),
            "fail_tag": fail_tag,
        },
    }

    _write_json(details_path, details)
    _write_json(report_path, report)

    if len(str(report["notes"])) > 120:
        raise CliFailure("integrity", "incident hint exceeds 120 chars", 2, retryable=False)
    if failure_reasons:
        raise CliFailure("integrity", "; ".join(failure_reasons), 2, retryable=False)

    return IncidentResult(report=report, details=details)


def main() -> int:
    parser = _build_parser()
    try:
        args = strict_parse_args(parser)
        result = run_incident(
            trace_path=Path(args.trace),
            out_dir=Path(args.out_dir),
            prog_path=Path(args.prog),
            timeout_s=float(args.timeout),
        )
    except CliFailure as err:
        return emit_failure(err)

    print(json.dumps(result.report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
