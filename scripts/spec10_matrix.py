from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from pirml.cli_common import CliFailure, emit_failure, strict_parse_args


def main() -> int:
    parser = argparse.ArgumentParser(description="Spec-10 Command Matrix Resolver")
    parser.add_argument("--lane", type=str, help="Filter by lane (W0..W10)")
    parser.add_argument("--format", choices=["jsonl"], default="jsonl", help="Output format")

    try:
        args = strict_parse_args(parser)
    except CliFailure as err:
        return emit_failure(err)

    rows = get_matrix_rows()

    if args.lane:
        valid_lanes = {row["lane"] for row in rows if "lane" in row}
        if args.lane not in valid_lanes:
            return emit_failure(CliFailure("config", f"unknown lane: {args.lane}", 2))
        rows = [row for row in rows if row.get("lane") == args.lane]

    for row in rows:
        print(json.dumps(row))

    return 0


def get_matrix_rows() -> list[dict[str, Any]]:
    # Source: spec-0/10-spec.md section 3
    return [
        {"k": "meta", "id": "spec10-matrix", "asof": "2026-02-23"},
        # W0
        {
            "k": "row",
            "lane": "W0",
            "name": "Sales proof burst",
            "cmd": "mise run fast && python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/demo --project-root .",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W1
        {
            "k": "row",
            "lane": "W1",
            "name": "J1/J2 Trust + runtime integrity signoff",
            "cmd": "python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/w1/live && python -m scripts.tools.replay tests/prog_ok.py out/w1/live/trace.ndjson --out-dir out/w1/replay",
            "authority": True,
            "deps": ["W0"],
            "deterministic": True,
            "optional": False,
        },
        # W2
        {
            "k": "row",
            "lane": "W2",
            "name": "J3/J5 Tool authoring + context compression",
            "cmd": "rm -rf out/w2/tools && python -m pirml tool init acme.lookup --tools-dir out/w2/tools",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W3
        {
            "k": "row",
            "lane": "W3",
            "name": "J4 Compile safety loop",
            "cmd": "python -m scripts.compile --task 'echo alpha' --tools-dir tests/fixtures/toolsearch/catalog --out-dir out/w3/compile",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W4
        {
            "k": "row",
            "lane": "W4",
            "name": "J6 Web evidence lane",
            "cmd": "python -m scripts.web_fixture_smoke",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W5
        {
            "k": "row",
            "lane": "W5",
            "name": "J7 ArtifactFS + RLM lane",
            "cmd": "python -m scripts.artifact_rebuild --check",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W6
        {
            "k": "row",
            "lane": "W6",
            "name": "J8 Operator UX lane",
            "cmd": "python -m scripts.pirml_run --prog tests/prog_ok.py --out-dir out/w6",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W7
        {
            "k": "row",
            "lane": "W7",
            "name": "J9 Eval/report economics lane",
            "cmd": "mise run eval-golden && mise run eval-full && mise run eval-report",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W8
        {
            "k": "row",
            "lane": "W8",
            "name": "J10 Policy shell lane",
            "cmd": "python -m scripts.spec09_tool_smoke",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W9
        {
            "k": "row",
            "lane": "W9",
            "name": "J11 Incident triage lane",
            "cmd": "python -m scripts.replay_check",
            "authority": True,
            "deps": [],
            "deterministic": True,
            "optional": False,
        },
        # W10
        {
            "k": "row",
            "lane": "W10",
            "name": "J12 Governance lane",
            "cmd": "mise run ci",
            "authority": True,
            "deps": ["W0", "W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "W9"],
            "deterministic": True,
            "optional": False,
        },
        # Aliases (I03)
        {"k": "alias", "alias": "pirml_run", "ref": "W6", "authority": False, "risk": "low"},
        {"k": "alias", "alias": "pirml-replay", "ref": "W0", "authority": False, "risk": "low"},
        {"k": "alias", "alias": "mise ci", "ref": "W10", "authority": False, "risk": "low"},
        {"k": "alias", "alias": "python -m pirml", "ref": "W1", "authority": False, "risk": "high"},
    ]


if __name__ == "__main__":
    sys.exit(main())
