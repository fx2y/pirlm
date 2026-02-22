from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pirml.ux.layout import derive_summary
from pirml.ux.runtime_bridge import run_once


def main() -> None:
    parser = argparse.ArgumentParser(prog="pirml_run")
    parser.add_argument("--prog", required=True, help="Path to Python program")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--replay", help="Replay from trace NDJSON")
    parser.add_argument("--timeout", type=float, default=60.0, help="Run timeout")
    parser.add_argument("--project-root", default=".", help="Project root for .pirml facade")

    args = parser.parse_args()

    try:
        res = run_once(
            prog_path=Path(args.prog),
            out_dir=Path(args.out_dir),
            replay_path=Path(args.replay) if args.replay else None,
            timeout=args.timeout,
            project_root=Path(args.project_root),
        )

        # S30: Headless summary row
        summary = {
            "runId": res["runId"],
            "ok": res["ok"],
            "summary": derive_summary(Path(args.out_dir)),
            "pointer": res["pointer"],
        }
        if not res["ok"]:
            summary["error"] = res["error"]

        print(json.dumps(summary, indent=2))
        sys.exit(0 if res["ok"] else 1)

    except Exception as e:
        err_data = {
            "ok": False,
            "error": {"type": "integrity", "msg": str(e), "retryable": False},
        }
        print(json.dumps(err_data, indent=2), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
