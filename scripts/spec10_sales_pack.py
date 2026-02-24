from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CliFailure("config", f"missing input: {path}", 2, retryable=False)
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CliFailure(
                "integrity",
                f"invalid jsonl row: {path}:{lineno}: {exc}",
                2,
                retryable=False,
            ) from exc
        if not isinstance(row, dict):
            raise CliFailure(
                "integrity", f"jsonl row must be object: {path}:{lineno}", 2, retryable=False
            )
        raw_row = cast(dict[object, Any], row)
        typed_row: dict[str, Any] = {str(key): value for key, value in raw_row.items()}
        rows.append(typed_row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    persona_rows = [row for row in rows if row.get("k") == "persona"]
    lines = [
        "# Spec10 Persona Pack",
        "",
        "| Buyer | Lane | Hook | Proof Command | Artifact Pointer | Objection Kill |",
        "|---|---|---|---|---|---|",
    ]
    for row in persona_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["buyer"]),
                    str(row["proof_ref"]),
                    str(row["hook"]),
                    f"`{row['proof_cmd']}`",
                    f"`{row['artifact_ptr']}`",
                    str(row["objection_kill"]),
                ]
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass(frozen=True)
class BuyerPlan:
    buyer: str
    hook: str
    objection: str
    objection_kill: str
    invariants: tuple[str, ...]
    proof_lanes: tuple[str, ...]


BUYER_PLANS: tuple[BuyerPlan, ...] = (
    BuyerPlan(
        buyer="Head AI Platform",
        hook="You can gate agent releases like infra releases.",
        objection="Not another eval dashboard",
        objection_kill="Show owner path + typed fail lanes.",
        invariants=("I05", "I18"),
        proof_lanes=("W0", "W1"),
    ),
    BuyerPlan(
        buyer="Security/Policy",
        hook="Unknown inputs fail closed with typed evidence.",
        objection="Model can bypass policy",
        objection_kill="Show policy chokepoint typed envelopes.",
        invariants=("I17", "I19"),
        proof_lanes=("W8", "W1"),
    ),
    BuyerPlan(
        buyer="QA/RelEng",
        hook="Protocol invariants are executable, not aspirational.",
        objection="Flaky",
        objection_kill="Show replay block + deterministic rerun lanes.",
        invariants=("I15", "I22"),
        proof_lanes=("W1", "W3"),
    ),
    BuyerPlan(
        buyer="PM/ML lead",
        hook="Accuracy debates collapse into comparator deltas.",
        objection="Metrics can be gamed",
        objection_kill="Show fail_tag/NO_CITE/replay-guard coupling.",
        invariants=("I16", "I20"),
        proof_lanes=("W7", "W4"),
    ),
    BuyerPlan(
        buyer="FDE",
        hook="Incident to root class in <15m.",
        objection="Need full payload",
        objection_kill="Show compact root + details sidecar pointers.",
        invariants=("I12", "I10"),
        proof_lanes=("W9", "W5"),
    ),
)

PRIORITY_LANES: tuple[str, ...] = ("W0", "W1", "W8", "W9")

HARD_DISQUALIFIERS: tuple[str, ...] = (
    "Wants permissive fallback behavior for unknown flags/providers/tools.",
    "Wants free-form dashboard claims without artifact-level proof.",
    "Wants to mutate runtime surface casually for convenience.",
    "Rejects explicit dataset/path ingress discipline.",
)

LANE_POINTER_FALLBACKS: dict[str, str] = {
    "W9": "out/spec10_incident/incident.json",
}


def _load_authority_commands(matrix_rows: list[dict[str, Any]]) -> dict[str, str]:
    lanes: dict[str, str] = {}
    for row in matrix_rows:
        if row.get("k") != "row":
            continue
        lane = str(row.get("lane", ""))
        if not lane.startswith("W"):
            continue
        if not bool(row.get("authority", False)):
            continue
        cmd = str(row.get("cmd", "")).strip()
        if not cmd:
            raise CliFailure("validation", f"matrix lane has empty cmd: {lane}", 1, retryable=False)
        if lane in lanes:
            raise CliFailure("integrity", f"duplicate authority lane: {lane}", 2, retryable=False)
        lanes[lane] = cmd
    return lanes


def _load_artifact_pointers(
    pack_rows: list[dict[str, Any]], *, pack_index_path: Path
) -> dict[str, str]:
    pointers: dict[str, str] = {}
    for row in pack_rows:
        if row.get("k") != "row":
            continue
        lane = str(row.get("lane", ""))
        if not lane:
            continue
        pointer_candidates = [
            row.get("final_ptr"),
            row.get("trace_ptr"),
            row.get("report_ptr"),
            row.get("details_ptr"),
        ]
        pointer = ""
        for candidate in pointer_candidates:
            if isinstance(candidate, str) and candidate.strip():
                pointer = candidate
                break
        if pointer:
            pointers[lane] = pointer
    return pointers


def _resolve_pointer(pointer: str, *, pack_index_path: Path) -> str:
    raw = pointer.strip()
    if not raw:
        raise CliFailure("validation", "empty proof pointer", 1, retryable=False)

    candidates = [Path(raw)]
    if not Path(raw).is_absolute():
        candidates.append(pack_index_path.parent / raw)
        candidates.append(Path.cwd() / raw)

    checked: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in checked:
            continue
        checked.add(resolved)
        if resolved.is_file():
            return str(resolved)
    raise CliFailure("validation", f"unresolved proof pointer: {raw}", 1, retryable=False)


def _verification_index(verification_rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("id"))
        for row in verification_rows
        if row.get("k") == "inv" and isinstance(row.get("id"), str) and str(row["id"]).strip()
    }


def build_persona_pack(
    *,
    matrix_rows: list[dict[str, Any]],
    pack_rows: list[dict[str, Any]],
    verification_rows: list[dict[str, Any]],
    pack_index_path: Path,
) -> list[dict[str, Any]]:
    authority_cmds = _load_authority_commands(matrix_rows)
    pointers = _load_artifact_pointers(pack_rows, pack_index_path=pack_index_path)
    verification_ids = _verification_index(verification_rows)

    output: list[dict[str, Any]] = [
        {
            "k": "meta",
            "id": "spec10-sales-pack",
            "asof": "2026-02-24",
            "mode": "ultra-terse/opinionated",
        },
    ]

    persona_rows: list[dict[str, Any]] = []
    objection_rows: list[dict[str, Any]] = []

    for buyer_idx, plan in enumerate(BUYER_PLANS):
        if len(plan.proof_lanes) < 2:
            raise CliFailure(
                "integrity", f"buyer proof lane budget invalid: {plan.buyer}", 2, retryable=False
            )

        for lane in plan.proof_lanes:
            if lane not in authority_cmds:
                raise CliFailure(
                    "integrity", f"missing authority lane in matrix: {lane}", 2, retryable=False
                )
            if lane not in pointers:
                if lane in LANE_POINTER_FALLBACKS:
                    pointers[lane] = LANE_POINTER_FALLBACKS[lane]
                else:
                    raise CliFailure(
                        "validation", f"missing proof pointer for lane: {lane}", 1, retryable=False
                    )
            artifact_ptr = _resolve_pointer(str(pointers[lane]), pack_index_path=pack_index_path)

            persona_rows.append(
                {
                    "k": "persona",
                    "buyer": plan.buyer,
                    "hook": plan.hook,
                    "proof_ref": lane,
                    "proof_cmd": authority_cmds[lane],
                    "artifact_ptr": artifact_ptr,
                    "objection": plan.objection,
                    "objection_kill": plan.objection_kill,
                    "invariants": list(plan.invariants),
                    "lane_truth": "authority",
                    "buyer_rank": buyer_idx,
                }
            )

        for inv in plan.invariants:
            if inv not in verification_ids:
                raise CliFailure("integrity", f"unknown invariant ref: {inv}", 2, retryable=False)
        objection_rows.append(
            {
                "k": "objection",
                "buyer": plan.buyer,
                "objection": plan.objection,
                "kill": plan.objection_kill,
                "invariants": list(plan.invariants),
            }
        )

    persona_rows.sort(
        key=lambda row: (
            PRIORITY_LANES.index(str(row["proof_ref"]))
            if str(row["proof_ref"]) in PRIORITY_LANES
            else len(PRIORITY_LANES),
            int(row["buyer_rank"]),
            str(row["proof_ref"]),
            str(row["buyer"]),
        )
    )

    output.extend(persona_rows)
    output.extend(
        {
            "k": "lane_truth",
            "lane": "W4b",
            "truth": "informational",
            "status": "unsupported",
            "note": "live web lane is non-authority by policy",
        }
        for _ in [0]
    )
    output.extend(
        {
            "k": "disqualifier",
            "label": "hard_disqualifier",
            "text": text,
            "status": "reject",
        }
        for text in HARD_DISQUALIFIERS
    )
    output.extend(objection_rows)
    output.extend(
        {
            "k": "coverage",
            "spec": "spec-0/10-spec.md:171-180",
            "by": ["C5.T00", "C5.T01", "C5.T02"],
        }
        for _ in [0]
    )
    output.extend(
        {
            "k": "coverage",
            "spec": "spec-0/10-spec.md:201-206",
            "by": ["C5.T03"],
        }
        for _ in [0]
    )
    return output


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Spec-10 persona packaging resolver")
    parser.add_argument("--out", required=True, help="Output directory for persona pack artifacts")
    parser.add_argument(
        "--matrix",
        default="spec-0/10/21-command-matrix.jsonl",
        help="Authority command matrix JSONL",
    )
    parser.add_argument(
        "--pack-index",
        default="out/spec10_pack/index.jsonl",
        help="Proof-pack index JSONL (explicit ingress)",
    )
    parser.add_argument(
        "--verification-matrix",
        default="spec-0/10/81-verification-matrix.jsonl",
        help="Verification matrix JSONL for invariant refs",
    )
    parser.add_argument(
        "--emit-md",
        action="store_true",
        help="Also emit markdown projection (non-authoritative)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = strict_parse_args(parser, argv)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)

        matrix_rows = _read_jsonl(Path(args.matrix))
        pack_rows = _read_jsonl(Path(args.pack_index))
        verification_rows = _read_jsonl(Path(args.verification_matrix))

        rows = build_persona_pack(
            matrix_rows=matrix_rows,
            pack_rows=pack_rows,
            verification_rows=verification_rows,
            pack_index_path=Path(args.pack_index),
        )
        jsonl_path = out_dir / "persona_pack.jsonl"
        _write_jsonl(jsonl_path, rows)

        md_path: Path | None = None
        if args.emit_md:
            md_path = out_dir / "persona_pack.md"
            _write_markdown(md_path, rows)
    except CliFailure as err:
        return emit_failure(err)

    payload: dict[str, Any] = {
        "ok": True,
        "persona_pack_ptr": str(Path(args.out) / "persona_pack.jsonl"),
    }
    if md_path is not None:
        payload["persona_pack_md_ptr"] = str(md_path)
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
