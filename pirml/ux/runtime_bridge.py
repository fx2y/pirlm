from __future__ import annotations

import csv
import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from pirml.clock import SequenceClock

from .errors import ArtifactError, IntegrityError, TimeoutError
from .pointers import create_pointer_payload, project_last_run
from .types import RunResult


def _drain(stream: Any, q: queue.Queue[str]) -> None:
    try:
        for line in stream:
            q.put(line)
    finally:
        stream.close()


def _load_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            return rows[0] if rows else {}
    except Exception:
        return {}


def run_once(
    prog_path: Path,
    out_dir: Path,
    replay_path: Path | None = None,
    timeout: float = 30.0,
    project_root: Path | None = None,
    art_root: Path = Path("art"),
) -> RunResult:
    """C1.T01, C1.T02: Shim executor delegating to authoritative CLI."""
    cmd = [
        sys.executable,
        "-m",
        "pirml",
        "--prog",
        str(prog_path),
        "--out-dir",
        str(out_dir),
        "--timeout",
        str(timeout),
    ]
    if replay_path:
        cmd.extend(["--replay", str(replay_path)])

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        stdout_q: queue.Queue[str] = queue.Queue()
        stderr_q: queue.Queue[str] = queue.Queue()

        t_stdout = threading.Thread(
            target=_drain, args=(proc.stdout, stdout_q), daemon=True
        )
        t_stderr = threading.Thread(
            target=_drain, args=(proc.stderr, stderr_q), daemon=True
        )

        t_stdout.start()
        t_stderr.start()

        try:
            exit_code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()  # Reaper
            t_stdout.join(timeout=1.0)
            t_stderr.join(timeout=1.0)
            raise TimeoutError(f"Run timed out after {timeout}s") from None

        t_stdout.join(timeout=1.0)
        t_stderr.join(timeout=1.0)

        stdout_lines: list[str] = []
        while not stdout_q.empty():
            stdout_lines.append(stdout_q.get())

        stderr_lines: list[str] = []
        while not stderr_q.empty():
            stderr_lines.append(stderr_q.get())
        stderr_content = "".join(stderr_lines)

        # C1.T03: Parse runtime outputs from explicit out-dir only
        final_path = out_dir / "final.json"
        if not final_path.exists():
            if exit_code == 0:
                raise ArtifactError("final.json missing despite exit 0")

            return {
                "ok": False,
                "runId": out_dir.name,
                "pointer": None,
                "error": {
                    "type": "runtime",
                    "msg": stderr_content.strip() or f"Process exited with {exit_code}",
                    "retryable": False,
                },
                "output": None,
                "meta": {"exit_code": exit_code, "stderr": stderr_content},
            }

        try:
            final_data = json.loads(final_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise IntegrityError(f"Failed to parse final.json: {e}") from e

        run_id = out_dir.name
        ts = SequenceClock.from_env().now()

        pointer = create_pointer_payload(run_id, out_dir, art_root, ts)

        if project_root:
            project_last_run(out_dir, art_root, project_root)

        ok = final_data.get("ok", False)
        error = final_data.get("error")
        if not ok and error is None:
            error = {
                "type": "runtime",
                "msg": stderr_content.strip() or "Process failed without error payload",
                "retryable": False,
            }

        return {
            "ok": ok,
            "runId": run_id,
            "pointer": pointer,
            "error": error,
            "output": final_data.get("output"),
            "meta": {
                "exit_code": exit_code,
                "stderr": stderr_content,
                "metrics": _load_metrics(out_dir / "metrics.csv"),
            },
        }

    except Exception as e:
        if isinstance(e, (TimeoutError, ArtifactError, IntegrityError)):
            raise
        raise IntegrityError(f"Shim failure: {str(e)}") from e


def replay(
    prog_path: Path,
    trace_path: Path,
    out_dir: Path,
    timeout: float = 30.0,
    project_root: Path | None = None,
    art_root: Path = Path("art"),
) -> RunResult:
    """C1.T07: Replay wrapper command."""
    return run_once(
        prog_path=prog_path,
        out_dir=out_dir,
        replay_path=trace_path,
        timeout=timeout,
        project_root=project_root,
        art_root=art_root,
    )
