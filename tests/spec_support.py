from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_TS_FN_RE = re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def repo_path(relpath: str) -> Path:
    return _ROOT / relpath


def load_jsonl(relpath: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in repo_path(relpath).read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        rows.append(json.loads(text))
    return rows


def python_case_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def ts_case_names(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(_TS_FN_RE.findall(text))


def _python_module_ref_path(module_ref: str) -> Path | None:
    if module_ref.endswith(".py"):
        return repo_path(module_ref)
    if module_ref.startswith("tests."):
        return repo_path(module_ref.replace(".", "/") + ".py")
    return None


def assert_test_ref_exists(test_ref: str) -> None:
    module_ref, sep, case_name = test_ref.partition("::")
    if module_ref.endswith(".ts"):
        path = repo_path(module_ref)
        if not path.is_file():
            raise AssertionError(f"missing TS test file: {module_ref}")
        if sep and case_name and case_name not in ts_case_names(path):
            raise AssertionError(f"missing TS case {case_name} in {module_ref}")
        return

    path = _python_module_ref_path(module_ref)
    if path is None:
        raise AssertionError(f"unsupported test ref: {test_ref}")
    if not path.is_file():
        raise AssertionError(f"missing Python test file: {module_ref}")
    if sep and case_name and case_name not in python_case_names(path):
        raise AssertionError(f"missing Python case {case_name} in {module_ref}")
