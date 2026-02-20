from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pirml.compiler.types import CompileContract, CompileErr
from pirml.runtime.rpc import canonical_json


@dataclass
class SmokeResult:
    ok: bool
    final: dict[str, Any] | None = None
    error: CompileErr | None = None
    stdout: str = ""
    stderr: str = ""


def generate_smoke_harness(prog_src: str, contract: CompileContract) -> str:
    """Generate a self-contained harness for smoke testing."""
    tool_deps = contract.get("tool_deps", [])
    budgets = contract.get("budgets", {})

    # S.SM1: Inject TOOL_* wrappers
    wrappers: list[str] = []
    for tool in tool_deps:
        safe_name = tool.replace(".", "_")
        wrappers.append(f"""
async def TOOL_{safe_name}(args):
    return await _harness_call_tool("{tool}", args)
""")
        # Also provide without underscore if tool name has no dots
        if "." not in tool:
            wrappers.append(f"""
async def TOOL_{tool}(args):
    return await _harness_call_tool("{tool}", args)
""")

    harness_code = f"""
import asyncio
import json
import sys
import os

# Internal state for tracking
_calls = 0
_parallel_max = 0
_parallel_current = 0
_bytes_in = 0
_bytes_out = 0
_clock = 0

BUDGETS = {json.dumps(budgets)}

def _get_ts():
    global _clock
    _clock += 100
    return _clock

def send_final(ok, result):
    # S.SM3: Single final JSON object, no chatter
    print(json.dumps({{"op": "final", "ok": ok, "result": result, "ts": _get_ts()}}))
    sys.exit(0)

async def _harness_call_tool(name, args):
    global _calls, _parallel_current, _parallel_max, _bytes_in, _bytes_out
    
    call_id = f"c{{_calls + 1:05d}}"
    
    # Emit call frame (S.RPC4 parity)
    print(json.dumps({{"op": "call", "id": call_id, "tool": name, "args": args, "ts": _get_ts()}}))

    # Track bytes in
    arg_bytes = len(json.dumps(args).encode("utf-8"))
    _bytes_in += arg_bytes
    if _bytes_in > BUDGETS.get("max_bytes_in", 0):
        send_final(False, {{"error": {{"type": "FAIL_B3_BYTES_BUDGET_OVERFLOW", "msg": "max_bytes_in exceeded"}}}})

    _calls += 1
    if _calls > BUDGETS.get("max_calls", 0):
        send_final(False, {{"error": {{"type": "FAIL_B3_CALL_BUDGET_OVERFLOW", "msg": "max_calls exceeded"}}}})

    _parallel_current += 1
    _parallel_max = max(_parallel_max, _parallel_current)
    if _parallel_max > BUDGETS.get("max_parallel", 0):
        send_final(False, {{"error": {{"type": "FAIL_B3_PARALLEL_BUDGET_OVERFLOW", "msg": "max_parallel exceeded"}}}})

    try:
        await asyncio.sleep(0.1)  # Simulate async work for parallel tracking
        # Deterministic output (S.SM1)
        short_name = name.split(".")[-1]
        if short_name == "echo":
            res = args.get("text", "")
        elif short_name == "readfile":
            res = f"content of {{args.get('path', 'unknown')}}"
        elif short_name == "bash":
            res = f"output of {{args.get('command', 'unknown')}}"
        else:
            res = {{"status": "ok", "tool": name, "echo_args": args}}
        
        # Track bytes out
        res_bytes = len(json.dumps(res).encode("utf-8"))
        _bytes_out += res_bytes
        if _bytes_out > BUDGETS.get("max_bytes_out", 0):
            send_final(False, {{"error": {{"type": "FAIL_B3_BYTES_BUDGET_OVERFLOW", "msg": "max_bytes_out exceeded"}}}})
        
        # Emit result frame
        print(json.dumps({{"op": "result", "id": call_id, "ok": True, "output": res, "ts": _get_ts()}}))
            
        return res
    finally:
        _parallel_current -= 1

# Inject TOOL_* into globals
{"".join(wrappers)}

# Mock send_final in pirml.runtime.rpc if it's imported
import pirml.runtime.rpc
pirml.runtime.rpc.send_final = send_final

# Original program source
{prog_src}
"""
    return harness_code


def _sha256(val: Any) -> str:
    return hashlib.sha256(canonical_json(val).encode("utf-8")).hexdigest()


def parse_smoke_output(stdout: str) -> SmokeResult:
    """Parse and post-process smoke harness stdout for trace_lint parity."""
    lines = [line_raw for line_raw in stdout.splitlines() if line_raw.strip()]
    if not lines:
        return SmokeResult(
            ok=False,
            error={
                "type": "smoke_no_output",
                "msg": "No output from smoke test",
                "retryable": False,
            },
            stdout=stdout,
        )

    try:
        # We look for all lines and validate they are part of the protocol
        # Also attach supervisor fields for trace_lint parity (C3.T4)
        final_found = 0
        processed_lines: list[str] = []
        seq = 0
        start_ts: int | None = None

        last_parsed_data: dict[str, Any] | None = None
        for line in lines:
            try:
                data = cast(dict[str, Any], json.loads(line))
                if "op" not in data:
                    continue
                op = data["op"]
                if op not in ("call", "result", "final"):
                    return SmokeResult(
                        ok=False,
                        error={
                            "type": "smoke_output_invalid",
                            "msg": f"Unexpected op: {op}",
                            "retryable": False,
                        },
                        stdout=stdout,
                    )

                # Post-process for trace_lint
                seq += 1
                data["seq"] = seq
                ts = cast(int, data.get("ts", 0))
                if start_ts is None:
                    start_ts = ts
                data["ms"] = ts - start_ts

                if op == "call":
                    data["dir"] = "in"
                    data["sha256_args"] = _sha256(data.get("args"))
                elif op == "result":
                    data["dir"] = "out"
                    if "output" in data:
                        data["sha256_output"] = _sha256(data.get("output"))
                    else:
                        data["sha256_output"] = _sha256(data.get("error"))
                elif op == "final":
                    final_found += 1
                    data["dir"] = "in"
                    data["sha256_output"] = _sha256(data.get("result"))
                    if final_found > 1:
                        return SmokeResult(
                            ok=False,
                            error={
                                "type": "FAIL_B3_MULTI_FINAL",
                                "msg": "Multiple final frames in smoke stdout",
                                "retryable": False,
                            },
                            stdout=stdout,
                        )

                processed_lines.append(canonical_json(data))
                last_parsed_data = data

            except json.JSONDecodeError:
                return SmokeResult(
                    ok=False,
                    error={
                        "type": "FAIL_B3_STDOUT_CHATTER",
                        "msg": "Non-JSON chatter in smoke stdout",
                        "retryable": False,
                    },
                    stdout=stdout,
                )

        if final_found == 0 or last_parsed_data is None:
            return SmokeResult(
                ok=False,
                error={
                    "type": "smoke_output_invalid",
                    "msg": "No final op found in stdout",
                    "retryable": False,
                },
                stdout=stdout,
            )

        # Reconstruct stdout with processed lines
        new_stdout = "\n".join(processed_lines) + "\n"

        if last_parsed_data["op"] == "final":
            is_ok = False
            if "ok" in last_parsed_data:
                is_ok = bool(last_parsed_data["ok"])

            res: dict[str, Any] = {}
            if "result" in last_parsed_data:
                res_val = last_parsed_data["result"]
                if isinstance(res_val, dict):
                    res = cast(dict[str, Any], res_val)

            err: CompileErr | None = None
            if not is_ok:
                # Try to extract error from result object
                if "error" in res:
                    err_val = res["error"]
                    if isinstance(err_val, dict):
                        err_obj = cast(dict[str, Any], err_val)
                        err_type = "smoke_failed"
                        if "type" in err_obj:
                            err_type = str(err_obj["type"])
                        err_msg = "Smoke test failed"
                        if "msg" in err_obj:
                            err_msg = str(err_obj["msg"])

                        err = {
                            "type": err_type,
                            "msg": err_msg,
                            "retryable": False,
                        }
                if err is None:
                    err = {
                        "type": "smoke_failed",
                        "msg": "Smoke test failed",
                        "retryable": False,
                    }

            return SmokeResult(
                ok=is_ok,
                final=res,
                error=err,
                stdout=new_stdout,
            )
        else:
            return SmokeResult(
                ok=False,
                error={
                    "type": "smoke_output_invalid",
                    "msg": "Final op must be last",
                    "retryable": False,
                },
                stdout=new_stdout,
            )

    except Exception as e:
        return SmokeResult(
            ok=False,
            error={"type": "smoke_internal_error", "msg": str(e), "retryable": False},
            stdout=stdout,
        )


def run_smoke_subprocess(
    prog_src: str, contract: CompileContract, timeout_margin: float = 0.5
) -> SmokeResult:
    """C3.T2: Run smoke in isolated subprocess."""
    harness = generate_smoke_harness(prog_src, contract)
    timeout = contract.get("budgets", {}).get("timeout_s", 60)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(harness)
        tmp_path = Path(f.name)

    try:
        # Run subprocess
        proc = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=timeout + timeout_margin,
            env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        )

        stdout = proc.stdout
        stderr = proc.stderr

        if proc.returncode != 0 and not stdout:
            return SmokeResult(
                ok=False,
                error={
                    "type": "smoke_crash",
                    "msg": stderr or f"Process exited with {proc.returncode}",
                    "retryable": False,
                },
                stdout=stdout,
                stderr=stderr,
            )

        res = parse_smoke_output(stdout)
        res.stderr = stderr
        return res

    except subprocess.TimeoutExpired:
        return SmokeResult(
            ok=False,
            error={
                "type": "FAIL_B3_TIMEOUT",
                "msg": f"Smoke test timed out after {timeout}s",
                "retryable": False,
            },
        )
    except Exception as e:
        return SmokeResult(
            ok=False, error={"type": "smoke_internal_error", "msg": str(e), "retryable": False}
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
