from __future__ import annotations

import unittest

from pirml.compiler.prompt import build_compile_prompt


class TestCompilePrompt(unittest.TestCase):
    def test_prompt_contains_task_and_tools(self):
        task = "list all files"
        tools = [
            {"name": "list_files", "description": "list files in dir", "input_schema": {}}
        ]
        budgets = {
            "max_calls": 5,
            "max_parallel": 2,
            "max_bytes_in": 1000,
            "max_bytes_out": 500,
            "timeout_s": 30,
        }

        prompt = build_compile_prompt(task, tools, budgets)
        self.assertIn("list all files", prompt)
        self.assertIn("list_files", prompt)
        self.assertIn("max_calls=5", prompt)
        self.assertIn("<<<PROG>>>", prompt)
        self.assertIn("<<<CONTRACT>>>", prompt)

    def test_prompt_deterministic(self):
        task = "task"
        tools = [{"name": "t1"}, {"name": "t2"}]
        budgets = {"max_calls": 10}
        p1 = build_compile_prompt(task, tools, budgets)
        p2 = build_compile_prompt(task, tools, budgets)
        self.assertEqual(p1, p2)


if __name__ == "__main__":
    unittest.main()
