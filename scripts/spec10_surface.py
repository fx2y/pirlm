from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args
from pirml.protocol import ProtocolError, load_jsonl, validate_strict_trace


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec-10 surface resolver views")
    subparsers = parser.add_subparsers(dest="surface", required=True)

    console = subparsers.add_parser("console", help="S1 command console view")
    console.add_argument(
        "--run", default="out/ci", help="Run directory containing trace/final artifacts"
    )

    evidence = subparsers.add_parser("evidence", help="S2 evidence timeline view")
    evidence.add_argument("--trace", required=True, help="Trace NDJSON path")

    eval_parser = subparsers.add_parser("eval", help="S4 eval board view")
    eval_parser.add_argument("--report", required=True, help="Report JSON path")
    eval_parser.add_argument("--delta", help="Compare delta JSON path")
    eval_parser.add_argument("--pareto", help="Pareto JSON path")

    policy = subparsers.add_parser("policy", help="S5 policy center view")
    policy.add_argument("--log", required=True, help="NDJSON/JSON policy log path")

    return parser


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CliFailure("integrity", f"missing artifact: {path}", 2, retryable=False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliFailure("integrity", f"invalid json: {path}: {exc}", 2, retryable=False) from exc
    if not isinstance(payload, dict):
        raise CliFailure("integrity", f"json root must be object: {path}", 2, retryable=False)
    raw_payload = cast(dict[object, Any], payload)
    return {str(key): value for key, value in raw_payload.items()}


def _load_trace(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CliFailure("integrity", f"missing trace: {path}", 2, retryable=False)
    try:
        frames = load_jsonl(path)
        validate_strict_trace(frames)
    except (OSError, ProtocolError, ValueError) as exc:
        raise CliFailure(
            "integrity", f"strict trace validation failed: {exc}", 2, retryable=False
        ) from exc
    if not frames:
        raise CliFailure("integrity", f"empty trace: {path}", 2, retryable=False)
    return [dict(frame) for frame in frames]


def _sha256_path(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _final_root_compact(final_doc: dict[str, Any]) -> bool:
    allowed = {"ok", "results", "output", "meta"}
    keys = set(final_doc.keys())
    return "ok" in keys and "results" in keys and keys.issubset(allowed)


def _console_view(run_dir: Path) -> dict[str, Any]:
    trace_path = run_dir / "trace.ndjson"
    final_path = run_dir / "final.json"
    frames = _load_trace(trace_path)
    final_doc = _read_json(final_path)
    final_frame = frames[-1]
    meta = final_frame.get("meta")
    meta_obj: dict[str, Any] = {}
    if isinstance(meta, dict):
        raw_meta = cast(dict[object, Any], meta)
        meta_obj = {str(key): value for key, value in raw_meta.items()}
    replay_match: bool | None = None
    if "replay_match" in meta_obj:
        replay_match = bool(meta_obj.get("replay_match"))
    rc = 0 if bool(final_doc.get("ok")) else 1
    return {
        "surface": "console",
        "run_id": run_dir.name,
        "rc": rc,
        "parity": {
            "replay_match": replay_match,
            "final_sha256": _sha256_path(final_path),
            "trace_sha256": _sha256_path(trace_path),
        },
        "gate": {
            "trace_strict": True,
            "final_root_compact": _final_root_compact(final_doc),
            "final_last": frames[-1].get("op") == "final",
        },
        "pointers": {"trace_ptr": str(trace_path), "final_ptr": str(final_path)},
    }


def _evidence_view(trace_path: Path) -> dict[str, Any]:
    frames = _load_trace(trace_path)
    timeline: list[dict[str, Any]] = []
    for idx, frame in enumerate(frames, start=1):
        op = str(frame.get("op"))
        hash_key = (
            "sha256_args"
            if op == "call"
            else "sha256_output"
            if op in {"result", "final"}
            else "sha256_data"
        )
        timeline.append(
            {
                "line": idx,
                "op": op,
                "id": frame.get("id"),
                "seq": int(frame.get("seq", 0)),
                "dir": frame.get("dir"),
                "hash": frame.get(hash_key),
            }
        )
    return {
        "surface": "evidence",
        "trace_ptr": str(trace_path),
        "summary": {
            "count": len(timeline),
            "final_last": timeline[-1]["op"] == "final",
            "first_seq": timeline[0]["seq"],
            "last_seq": timeline[-1]["seq"],
        },
        "timeline": timeline,
    }


def _eval_view(
    report_path: Path, delta_path: Path | None, pareto_path: Path | None
) -> dict[str, Any]:
    report = _read_json(report_path)
    required = ["acc", "acc_per_$", "acc_per_min", "median_latency", "median_cost"]
    missing = [key for key in required if key not in report]
    if missing:
        joined = ",".join(sorted(missing))
        raise CliFailure("validation", f"missing report metrics: {joined}", 1, retryable=False)

    fail_pareto = report.get("fail_pareto")
    if pareto_path is not None:
        pareto = _read_json(pareto_path)
        fail_pareto = pareto.get("fail_pareto", fail_pareto)

    delta_obj: dict[str, Any] | None = None
    if delta_path is not None:
        delta_obj = _read_json(delta_path)

    return {
        "surface": "eval",
        "report_ptr": str(report_path),
        "delta_ptr": str(delta_path) if delta_path is not None else None,
        "kpi_tuple": [
            float(report["acc"]),
            float(report["acc_per_$"]),
            float(report["acc_per_min"]),
            float(report["median_latency"]),
            float(report["median_cost"]),
        ],
        "fail_pareto": fail_pareto if isinstance(fail_pareto, list) else [],
        "delta": delta_obj,
    }


def _policy_view(log_path: Path) -> dict[str, Any]:
    if not log_path.is_file():
        raise CliFailure("integrity", f"missing policy log: {log_path}", 2, retryable=False)

    raw = log_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    stripped = raw.strip()
    if not stripped:
        raise CliFailure(
            "unsupported", f"policy log has no typed rows: {log_path}", 1, retryable=False
        )

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                raw_row = cast(dict[object, Any], data)
                rows = [{str(key): value for key, value in raw_row.items()}]
            elif isinstance(data, list):
                parsed_rows: list[dict[str, Any]] = []
                data_rows = cast(list[Any], data)
                for item in data_rows:
                    if not isinstance(item, dict):
                        continue
                    raw_item = cast(dict[object, Any], item)
                    parsed_rows.append({str(key): value for key, value in raw_item.items()})
                rows = parsed_rows
        except json.JSONDecodeError:
            # Fallback for NDJSON payloads that begin with '{'.
            rows = []

    if not rows:
        for line in raw.splitlines():
            if not line.strip():
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                raw_parsed = cast(dict[object, Any], parsed)
                rows.append({str(key): value for key, value in raw_parsed.items()})

    typed_rows: list[dict[str, Any]] = []
    for row in rows:
        if "error" in row and isinstance(row.get("error"), dict):
            err = dict(row["error"])
            typed_rows.append(
                {
                    "type": err.get("type"),
                    "msg": err.get("msg"),
                    "retryable": bool(err.get("retryable", False)),
                    "rc": int(err.get("rc", 1) or 1),
                    "decision": "deny",
                }
            )
            continue
        if "type" in row and "msg" in row:
            typed_rows.append(
                {
                    "type": row.get("type"),
                    "msg": row.get("msg"),
                    "retryable": bool(row.get("retryable", False)),
                    "rc": int(row.get("rc", 1) or 1),
                    "decision": row.get("decision", "deny"),
                }
            )
            continue
        if "decision" in row and row.get("decision") in {"allow", "deny"}:
            typed_rows.append(
                {
                    "type": row.get("type", "policy_decision"),
                    "msg": row.get("msg", ""),
                    "retryable": bool(row.get("retryable", False)),
                    "rc": int(row.get("rc", 0) or 0),
                    "decision": row.get("decision"),
                }
            )

    if not typed_rows:
        raise CliFailure(
            "unsupported", f"policy log has no typed rows: {log_path}", 1, retryable=False
        )

    return {"surface": "policy", "log_ptr": str(log_path), "rows": typed_rows}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = strict_parse_args(parser, argv)
        if args.surface == "console":
            payload = _console_view(Path(args.run))
        elif args.surface == "evidence":
            payload = _evidence_view(Path(args.trace))
        elif args.surface == "eval":
            delta = Path(args.delta) if args.delta else None
            pareto = Path(args.pareto) if args.pareto else None
            payload = _eval_view(Path(args.report), delta, pareto)
        elif args.surface == "policy":
            payload = _policy_view(Path(args.log))
        else:
            raise CliFailure("config", f"unknown subcommand: {args.surface}", 2, retryable=False)
    except CliFailure as err:
        return emit_failure(err)
    except json.JSONDecodeError as exc:
        return emit_failure(CliFailure("integrity", f"invalid json: {exc}", 2, retryable=False))

    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
