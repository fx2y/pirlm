from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args

DEFAULT_MATRIX_PATH = Path("spec-0/10/21-command-matrix.jsonl")

VALID_OWNERS = [
    "scripts.pirml_run",
    "scripts.compile",
    "scripts.tools.replay",
    "scripts.spec10_matrix",
    "scripts.replay_check",
    "scripts.spec10_incident",
    "scripts.artifact_rebuild",
    "scripts.web_fixture_smoke",
    "scripts.spec09_tool_smoke",
    "python -m pirml",
    "mise run",
]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CliFailure("config", f"missing matrix artifact: {path}", 2, retryable=False)
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CliFailure(
                "integrity", f"invalid jsonl row: {path}:{lineno}: {exc}", 2, retryable=False
            ) from exc
        if not isinstance(payload, dict):
            raise CliFailure(
                "integrity", f"jsonl row must be object: {path}:{lineno}", 2, retryable=False
            )
        raw = cast(dict[object, Any], payload)
        rows.append({str(k): v for k, v in raw.items()})
    return rows


def _validate_rows(rows: list[dict[str, Any]], *, source: Path) -> None:
    if not rows:
        raise CliFailure("integrity", f"empty matrix: {source}", 2, retryable=False)
    if rows[0].get("k") != "meta":
        raise CliFailure("integrity", f"missing meta first row: {source}", 2, retryable=False)

    authority_lanes: dict[str, str] = {}
    alias_refs: list[str] = []
    for row in rows:
        kind = str(row.get("k", ""))
        if kind == "row" and bool(row.get("authority", False)):
            lane = str(row.get("lane", "")).strip()
            cmd = str(row.get("cmd", "")).strip()
            if not lane:
                raise CliFailure(
                    "integrity", f"authority lane missing id: {source}", 2, retryable=False
                )
            if not cmd:
                raise CliFailure(
                    "integrity", f"authority lane missing cmd: {lane}", 2, retryable=False
                )
            if not any(owner in cmd for owner in VALID_OWNERS):
                raise CliFailure(
                    "integrity",
                    f"authority command must route through owner path: {cmd}",
                    2,
                    retryable=False,
                )
            if lane in authority_lanes:
                raise CliFailure(
                    "integrity", f"duplicate authority lane: {lane}", 2, retryable=False
                )
            authority_lanes[lane] = cmd
            continue
        if kind == "alias":
            if bool(row.get("authority", False)):
                alias = str(row.get("alias", "<unknown>"))
                raise CliFailure(
                    "integrity", f"alias row cannot be authority: {alias}", 2, retryable=False
                )
            alias_refs.append(str(row.get("ref", "")).strip())

    required_lanes = {f"W{i}" for i in range(11)}
    missing = sorted(required_lanes.difference(authority_lanes.keys()))
    if missing:
        raise CliFailure(
            "integrity", f"missing authority lanes: {','.join(missing)}", 2, retryable=False
        )
    for ref in alias_refs:
        if ref and ref not in authority_lanes:
            raise CliFailure("integrity", f"alias ref missing lane: {ref}", 2, retryable=False)


def get_matrix_rows(matrix_path: Path | None = None) -> list[dict[str, Any]]:
    path = matrix_path or DEFAULT_MATRIX_PATH
    rows = _read_jsonl(path)
    _validate_rows(rows, source=path)
    return rows


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec-10 command matrix resolver")
    parser.add_argument("--lane", type=str, help="Filter by lane (W0..W10)")
    parser.add_argument(
        "--matrix", default=str(DEFAULT_MATRIX_PATH), help="Matrix JSONL artifact path"
    )
    parser.add_argument("--format", choices=["jsonl"], default="jsonl", help="Output format")
    return parser


def main() -> int:
    parser = _build_parser()
    try:
        args = strict_parse_args(parser)
        rows = get_matrix_rows(Path(args.matrix))
        lane_filter = str(args.lane).strip() if args.lane else ""
        if lane_filter:
            valid_lanes = {
                str(row["lane"]) for row in rows if row.get("k") == "row" and "lane" in row
            }
            if lane_filter not in valid_lanes:
                raise CliFailure("config", f"unknown lane: {lane_filter}", 2, retryable=False)
            rows = [row for row in rows if row.get("lane") == lane_filter or row.get("k") == "meta"]
    except CliFailure as err:
        return emit_failure(err)

    for row in rows:
        print(json.dumps(row, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
