import tempfile
import unittest
from pathlib import Path
from typing import Any

from pirml.runtime.tools import ErrorType, default_registry


class ToolContractTests(unittest.TestCase):
    def setUp(self):
        self.registry = default_registry()

    def test_readfile_limit(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
            tmp.write("A" * 100)
            tmp_path = tmp.name

        try:
            # Read with small limit
            res: Any = self.registry.execute("readfile", {"path": tmp_path, "max_bytes": 10})
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["output"]), 10)
            self.assertTrue(res["meta"]["truncated"])
            self.assertEqual(res["meta"]["size"], 100)
            self.assertEqual(res["meta"]["read_bytes"], 10)

            # Read with large limit
            res = self.registry.execute("readfile", {"path": tmp_path, "max_bytes": 200})
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["output"]), 100)
            self.assertFalse(res["meta"]["truncated"])
        finally:
            Path(tmp_path).unlink()

    def test_bash_structured_error(self):
        res: Any = self.registry.execute("bash", {"command": "exit 42"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["type"], ErrorType.EXECUTION_ERROR)
        self.assertEqual(res["meta"]["exitCode"], 42)

    def test_echo_arg_error(self):
        res: Any = self.registry.execute("echo", {"not_text": "foo"})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["type"], ErrorType.ARGUMENT_ERROR)


if __name__ == "__main__":
    unittest.main()
