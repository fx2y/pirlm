import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirml.runtime.tools import ErrorType, default_registry


class ToolContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = default_registry()

    def test_readfile_limit(self):
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            tmp.write(("A" * 100).encode())
            tmp_path = tmp.name

        try:
            # Read with small limit
            res: Any = self.registry.execute("readfile", {"path": tmp_path, "max_bytes": 10})
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["output"].encode()), 10)
            self.assertTrue(res["meta"]["truncated"])
            self.assertEqual(res["meta"]["size"], 100)
            self.assertEqual(res["meta"]["read_bytes"], 10)

            # Read with large limit
            res = self.registry.execute("readfile", {"path": tmp_path, "max_bytes": 200})
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["output"].encode()), 100)
            self.assertFalse(res["meta"]["truncated"])
        finally:
            Path(tmp_path).unlink()

    def test_G7_readfile_byte_cap(self) -> None:
        """G7: readfile caps chars, not bytes"""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as tmp:
            # 2 emoji = 8 bytes in UTF-8
            tmp.write("😀😀".encode())
            tmp_path = tmp.name

        try:
            # If it caps chars, max_bytes=4 might return 1 emoji (4 bytes) or 4 emojis if it thought they were 1 byte
            # If it caps bytes, it should return exactly 4 bytes (1 emoji)
            result = self.registry.execute("readfile", {"path": tmp_path, "max_bytes": 4})
            self.assertTrue(result.get("ok"))
            output = result.get("output", "")
            self.assertEqual(len(output.encode()), 4)
            meta = result.get("meta", {})
            self.assertEqual(meta.get("read_bytes"), 4)
        finally:
            Path(tmp_path).unlink()

    def test_bash_structured_error(self):
        res: Any = self.registry.execute("bash", {"command": "exit 42"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["type"], ErrorType.EXECUTION_ERROR)
        self.assertEqual(res["meta"]["exitCode"], 42)

    def test_echo_arg_error(self) -> None:
        res: Any = self.registry.execute("echo", {"not_text": "foo"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["type"], ErrorType.ARGUMENT_ERROR)

    def test_bash_timeout(self) -> None:
        res: Any = self.registry.execute("bash", {"command": "sleep 10"}, timeout=0.1)
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["type"], ErrorType.TIMEOUT)
        self.assertIn("timeout after 0.1s", res["error"]["msg"])

    def test_execute_with_retry_respects_retryable(self) -> None:
        from pirml.runtime.exec import execute_with_retry

        # Mock tool that fails with retryable=True then False
        class MockRegistry:
            def __init__(self) -> None:
                self.calls = 0

            def execute(self, name: str, args: Any, timeout: float | None = None) -> Any:
                _ = name, args, timeout
                self.calls += 1
                if self.calls == 1:
                    return {
                        "ok": False,
                        "error": {"type": "transient", "msg": "fail", "retryable": True},
                    }
                return {"ok": True, "output": "success"}

        reg = MockRegistry()
        payload, retries = execute_with_retry(
            reg,  # type: ignore
            tool="test",
            args={},
            timeout=None,
            max_retries=2,
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(retries, 1)
        self.assertEqual(reg.calls, 2)

        # Mock tool that fails with retryable=False
        reg2 = MockRegistry()

        def fail_non_retryable(name: str, args: Any, timeout: Any = None) -> Any:
            _ = name, args, timeout
            reg2.calls += 1
            return {"ok": False, "error": {"type": "fatal", "msg": "fail", "retryable": False}}

        reg2.execute = fail_non_retryable  # type: ignore
        payload, retries = execute_with_retry(
            reg2,  # type: ignore
            tool="test",
            args={},
            timeout=None,
            max_retries=2,
        )
        self.assertFalse(payload["ok"])
        self.assertEqual(retries, 0)
        self.assertEqual(reg2.calls, 1)


if __name__ == "__main__":
    unittest.main()
