from __future__ import annotations

import unittest
from typing import Any, cast

from pirml.runtime.tools import default_registry


class ToolSurfaceFreezeTests(unittest.TestCase):
    def test_registry_exact_set(self) -> None:
        registry = default_registry()
        tools_map = cast(dict[str, Any], vars(registry).get("_tools", {}))
        self.assertEqual(set(tools_map.keys()), {"echo", "readfile", "bash"})

    def test_registry_rejects_unknown_tool(self) -> None:
        registry = default_registry()
        result = registry.execute("spec09_unknown_tool", {})
        self.assertFalse(result.get("ok", True))
        self.assertEqual(result.get("error", {}).get("type"), "tool_not_found")


if __name__ == "__main__":
    unittest.main()
