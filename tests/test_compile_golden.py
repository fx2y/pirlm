from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pirml.compiler.compile import compile_task
from tests.compile_manifest import load_fixture_cases


class TestCompileGolden(unittest.TestCase):
    def setUp(self):
        self.corpus_path = Path("tests/fixtures/compile/corpus.jsonl")
        self.golden_dir = Path("tests/golden/compile")
        self.tools_dir = Path("tests/fixtures/toolsearch/catalog")
        self.golden_dir.mkdir(parents=True, exist_ok=True)
        self.cases = load_fixture_cases(self.corpus_path)

    def test_compile_corpus_goldens(self):
        for case in self.cases:
            case_golden_dir = self.golden_dir / case.id
            case_golden_dir.mkdir(parents=True, exist_ok=True)

            # Mock model adapter to return case raw text
            with patch(
                "pirml.compiler.model.StubModelAdapter.compile_once",
                return_value=case.raw_model_text,
            ):
                # We use a temp dir for actual output to compare with golden
                import tempfile

                with tempfile.TemporaryDirectory() as tmp_dir:
                    out_path = Path(tmp_dir)
                    compile_task(
                        task=case.task,
                        tools_dir=self.tools_dir,
                        out_dir=out_path,
                        skip_smoke=(case.stage != "smoke"),
                    )

                    # Artifacts to check
                    artifacts = ["prog.py", "contract.json", "compile_error.json"]
                    for art in artifacts:
                        actual_path = out_path / art
                        golden_path = case_golden_dir / art

                        if actual_path.exists():
                            actual_content = actual_path.read_text()
                            # If JSON, normalize it
                            if art.endswith(".json"):
                                try:
                                    obj = json.loads(actual_content)
                                    actual_content = json.dumps(obj, indent=2, sort_keys=True)
                                except Exception:
                                    pass

                            if golden_path.exists():
                                expected_content = golden_path.read_text()
                                if actual_content != expected_content:
                                    if os.getenv("PIRML_UPDATE_GOLDEN") == "1":
                                        golden_path.write_text(actual_content)
                                        print(f"Updated golden: {golden_path}")
                                        continue
                                    self.assertEqual(
                                        actual_content,
                                        expected_content,
                                        f"Golden mismatch for {case.id}/{art}. Run with PIRML_UPDATE_GOLDEN=1 if expected.",
                                    )
                            else:
                                if os.getenv("PIRML_UPDATE_GOLDEN") == "1":
                                    golden_path.write_text(actual_content)
                                    print(f"Generated golden: {golden_path}")
                                    continue
                                self.fail(
                                    f"Golden missing for {case.id}/{art}. Set PIRML_UPDATE_GOLDEN=1 to generate."
                                )
                        else:
                            # If artifact doesn't exist but golden does, that's a fail
                            if golden_path.exists():
                                self.fail(f"Missing expected artifact {art} for {case.id}")


if __name__ == "__main__":
    unittest.main()
