from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args
from scripts.spec10_matrix import get_matrix_rows


def compute_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_command(cmd: str) -> tuple[int, str, str]:
    # H9: Channel split: stdout protocol-only; diagnostics/errors in stderr/artifacts.
    # We capture both for the pack report.
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def extract_out_dir(cmd: str) -> Path | None:
    parts = cmd.split()
    if "--out-dir" in parts:
        idx = parts.index("--out-dir")
        if idx + 1 < len(parts):
            return Path(parts[idx + 1])
    if "--out" in parts:
        idx = parts.index("--out")
        if idx + 1 < len(parts):
            return Path(parts[idx + 1])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Spec-10 Proof Pack Orchestrator")
    parser.add_argument(
        "--out", type=str, default="out/spec10_pack/index.jsonl", help="Output pack index path"
    )
    parser.add_argument(
        "--include-live", action="store_true", help="Include optional live lanes (e.g. W4b)"
    )
    parser.add_argument(
        "--skip-run", action="store_true", help="Only scan existing artifacts without rerunning"
    )

    try:
        args = strict_parse_args(parser)
    except CliFailure as err:
        return emit_failure(err)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = get_matrix_rows()

    # C2.T03: separate deterministic fixture lanes from optional live lane (W4b)
    # W4b is not in the matrix rows currently, let's add it if requested or if we should define it here
    if args.include_live:
        rows.append(
            {
                "k": "row",
                "lane": "W4b",
                "name": "Live web smoke",
                "cmd": "python -m scripts.web_smoke",
                "authority": False,
                "deps": [],
                "deterministic": False,
                "optional": True,
            }
        )

    pack_rows: list[dict[str, Any]] = []
    meta = {"k": "meta", "id": "spec10-proof-pack", "asof": "2026-02-23", "ts": int(time.time())}
    pack_rows.append(meta)

    for row in rows:
        if row.get("k") != "row":
            continue

        lane = str(row["lane"])
        # Only W0..W8 as per C2 goal, but we can include all if desired.
        # C2 says W0..W8.
        if (
            not (lane.startswith("W") and lane[1:].isdigit() and 0 <= int(lane[1:]) <= 8)
            and lane != "W4b"
        ):
            continue

        print(f"Executing {lane}: {row['name']}...", file=sys.stderr)

        rc = 0
        if not args.skip_run:
            rc, _stdout, _stderr = run_command(str(row["cmd"]))

        # C2.T02: emit canonical pack rows with sha256, rc, artifact pointers
        pack_row: dict[str, Any] = {
            "k": "row",
            "lane": lane,
            "name": str(row["name"]),
            "cmd": str(row["cmd"]),
            "rc": rc,
            "authority": bool(row.get("authority", True)),
            "deterministic": bool(row.get("deterministic", True)),
        }

        # Try to find artifacts
        out_dir = extract_out_dir(row["cmd"])
        if out_dir:
            trace_path = out_dir / "trace.ndjson"
            final_path = out_dir / "final.json"

            if trace_path.exists():
                pack_row["trace_ptr"] = str(trace_path)
            if final_path.exists():
                pack_row["final_ptr"] = str(final_path)
                pack_row["sha256"] = compute_sha256(final_path)

        if "sha256" not in pack_row:
            pack_row["sha256"] = ""

        pack_rows.append(pack_row)

    with open(out_path, "w") as f:
        for r in pack_rows:
            f.write(json.dumps(r) + "\n")

    print(f"Proof pack written to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
