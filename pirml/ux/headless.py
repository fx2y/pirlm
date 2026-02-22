from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from .errors import NotImplementedError, UnsupportedError
from .layout import derive_summary
from .runtime_bridge import run_once


def process_event(event: dict[str, Any], project_root: Path = Path(".")) -> dict[str, Any] | None:
    """C5.T01, C5.T02: Deterministic event parser + shim trigger."""
    event_type = event.get("type", "")

    # C5.T01: Deterministic parser for known events
    if event_type == "tool_execution_start":
        tool = event.get("tool")
        if tool == "pirml_run":
            args = event.get("args", {})
            prog = args.get("prog")
            out_dir = args.get("out-dir")

            if not prog or not out_dir:
                return {
                    "type": "pirml_error",
                    "error": {
                        "type": "integrity",
                        "msg": "Missing prog or out-dir in tool args",
                        "retryable": False,
                    },
                }

            try:
                res = run_once(
                    prog_path=Path(prog),
                    out_dir=Path(out_dir),
                    project_root=project_root,
                )

                # C5.T03: Emit machine-readable summary rows
                summary = {
                    "type": "pirml_summary",
                    "runId": res["runId"],
                    "ok": res["ok"],
                    "summary": derive_summary(Path(out_dir)),
                    "pointer": res["pointer"],
                }
                if not res["ok"]:
                    summary["error"] = res["error"]
                return summary
            except Exception as e:
                return {
                    "type": "pirml_error",
                    "error": {"type": "integrity", "msg": str(e), "retryable": False},
                }
        else:
            # AC: ignored explicitly with reason
            print(f"DEBUG: Ignoring tool execution for unknown tool {tool}", file=sys.stderr)
            return None

    if event_type.startswith("turn_"):
        # Explicitly ignore turn events as they don't trigger runs
        return None

    # C5.T04: Reinjection path stub
    if event_type == "pirml_reinject_request":
        err = NotImplementedError("Reinjection path via SDK/RPC is postponed.")
        return {"type": "pirml_error", "error": err.to_row()}

    # AC: unknown event types ignored explicitly with reason
    if event_type:
        print(f"DEBUG: Ignoring unknown event type {event_type}", file=sys.stderr)
    return None


def run_headless(stream: Any = sys.stdin, project_root: Path = Path(".")) -> None:
    """C5.T00: Feature-gated headless runner."""
    if os.environ.get("PIRML_ENABLE_JSON_HEADLESS") != "1":
        err = UnsupportedError(
            "JSON headless mode disabled. Set PIRML_ENABLE_JSON_HEADLESS=1 to enable."
        )
        print(json.dumps({"type": "pirml_error", "error": err.to_row()}))
        sys.exit(1)

    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            result = process_event(event, project_root=project_root)
            if result:
                print(json.dumps(result))
                sys.stdout.flush()
        except json.JSONDecodeError:
            # AC: unknown event types ignored explicitly with reason (if we wanted to be loud)
            # but for now we just skip non-json lines as noise
            continue
        except Exception as e:
            print(
                json.dumps(
                    {
                        "type": "pirml_error",
                        "error": {"type": "integrity", "msg": str(e), "retryable": False},
                    }
                ),
                file=sys.stderr,
            )


if __name__ == "__main__":
    run_headless()
