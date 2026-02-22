from __future__ import annotations

import json
import unittest
from collections.abc import Mapping
from typing import Any

from pirml.compiler.verify import verify_compile_output
from pirml.runtime.exec import execute_with_retry
from pirml.runtime.policy import ToolRuntimePolicy, cache_key_for_call, resolve_effective_timeout
from pirml.runtime.tools import ToolRegistry


class Spec09C5RuntimePolicyTests(unittest.TestCase):
    def _prog(self) -> str:
        return (
            "import asyncio\n"
            "from pirml.runtime.rpc import send_final\n"
            "async def TOOL_pirml_echo(args):\n"
            "    return args.get('text', '')\n"
            "async def main():\n"
            "    await TOOL_pirml_echo({'text':'hi'})\n"
            "    send_final(True, {})\n"
            "if __name__ == '__main__':\n"
            "    asyncio.run(main())\n"
        )

    def _base_contract(self) -> dict[str, Any]:
        return {
            "tool_deps": ["pirml.echo"],
            "io_schema": {
                "trace_ptr": "trace.ndjson",
                "final_schema": {},
                "citations_schema": {},
            },
            "budgets": {
                "max_calls": 5,
                "max_parallel": 1,
                "max_bytes_in": 1000,
                "max_bytes_out": 1000,
                "timeout_s": 5,
            },
            "assertions": [],
        }

    def test_contract_policy_fields_required_shape(self) -> None:
        contract = self._base_contract()
        contract["artifact_writes"] = ["artifacts/out.json"]
        contract["tool_policies"] = {
            "pirml.echo": {
                "idempotent": True,
                "cacheable": False,
                "max_payload_bytes": 128,
                "retry": {"n": 1},
                "timeout_s": 1,
            }
        }
        contract["timeouts"] = {"default_s": 2, "tool_overrides": {"pirml.echo": 1}}
        parsed, errors = verify_compile_output(self._prog(), json.dumps(contract), ["pirml.echo"])
        self.assertEqual(errors, [], errors)
        self.assertIsNotNone(parsed)

        # Fail-closed unsupported variant lane (C5.T04): cacheable remains explicit+typed unsupported.
        contract_bad = self._base_contract()
        contract_bad["tool_policies"] = {"pirml.echo": {"idempotent": True, "cacheable": True}}
        _, errors_bad = verify_compile_output(self._prog(), json.dumps(contract_bad), ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "unsupported_policy_variant" for e in errors_bad))

    def test_verifier_blocks_outside_artifact_root(self) -> None:
        contract = self._base_contract()
        contract["artifact_writes"] = ["../oops.json"]
        _, errors = verify_compile_output(self._prog(), json.dumps(contract), ["pirml.echo"])
        self.assertTrue(any(e.get("code") == "artifact_path_denied" for e in errors), errors)

    def test_retry_only_when_idempotent(self) -> None:
        registry = ToolRegistry()
        calls = {"n": 0}

        def flaky(_args: Mapping[str, Any], _timeout: float | None) -> dict[str, Any]:
            calls["n"] += 1
            if calls["n"] < 3:
                return {
                    "ok": False,
                    "error": {"type": "execution_error", "msg": "flaky", "retryable": True},
                }
            return {"ok": True, "output": "ok"}

        registry.register("echo", flaky)
        payload, retries = execute_with_retry(
            registry,
            tool="echo",
            args={},
            timeout=1.0,
            max_retries=5,
            policy=ToolRuntimePolicy(idempotent=True, retry_n=2),
        )
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(retries, 2)
        self.assertEqual(calls["n"], 3)

    def test_retry_rejected_when_non_idempotent(self) -> None:
        registry = ToolRegistry()
        calls = {"n": 0}

        def should_not_run(_args: Mapping[str, Any], _timeout: float | None) -> dict[str, Any]:
            calls["n"] += 1
            return {"ok": True, "output": "unexpected"}

        registry.register("echo", should_not_run)
        payload, retries = execute_with_retry(
            registry,
            tool="echo",
            args={},
            timeout=1.0,
            max_retries=5,
            policy=ToolRuntimePolicy(idempotent=False, retry_n=1),
        )
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(retries, 0)
        self.assertEqual(calls["n"], 0)
        error = payload.get("error", {})
        self.assertEqual(error.get("type"), "unsupported")

    def test_payload_cap_enforced(self) -> None:
        registry = ToolRegistry()

        def large_output(_args: Mapping[str, Any], _timeout: float | None) -> dict[str, Any]:
            return {"ok": True, "output": "x" * 200}

        registry.register("echo", large_output)
        payload, retries = execute_with_retry(
            registry,
            tool="echo",
            args={},
            timeout=1.0,
            max_retries=0,
            policy=ToolRuntimePolicy(idempotent=True, max_payload_bytes=32),
        )
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(retries, 0)
        error = payload.get("error", {})
        self.assertEqual(error.get("type"), "output_too_large")
        meta = payload.get("meta", {})
        self.assertEqual(meta.get("policy_max_payload_bytes"), 32)
        self.assertTrue(int(meta.get("output_bytes", 0)) > 32)

    def test_timeout_and_cache_helpers_are_deterministic(self) -> None:
        self.assertEqual(
            cache_key_for_call("echo", {"b": 2, "a": 1}),
            cache_key_for_call("echo", {"a": 1, "b": 2}),
        )
        self.assertEqual(
            resolve_effective_timeout(call_timeout=9.0, remaining_timeout=5.0, policy_timeout=7.0),
            5.0,
        )
        self.assertEqual(
            resolve_effective_timeout(call_timeout=None, remaining_timeout=5.0, policy_timeout=3.0),
            3.0,
        )


if __name__ == "__main__":
    unittest.main()
