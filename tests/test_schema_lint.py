from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestSchemaLintCLI(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.schema_lint", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_requires_explicit_artifacts(self) -> None:
        completed = self._run()
        self.assertEqual(completed.returncode, 1)
        self.assertIn("at least one artifact path", completed.stderr)

    def test_missing_final_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-final.json"
            completed = self._run("--final", str(missing))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Required final artifact missing", completed.stderr)

    def test_ignores_unscoped_out_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            final_path = root / "final.json"
            final_path.write_text(json.dumps({"ok": True, "results": []}), encoding="utf-8")

            junk = root / "out" / "junk" / "contract.json"
            junk.parent.mkdir(parents=True, exist_ok=True)
            junk.write_text("{not json", encoding="utf-8")

            completed = self._run("--final", str(final_path))
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_required_contract_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-contract.json"
            completed = self._run("--contract", str(missing))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Required contract artifact missing", completed.stderr)

    def test_missing_web_artifact_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.serp.ndjson"
            completed = self._run("--serp", str(missing))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("Required serp artifact missing", completed.stderr)

    def test_web_artifacts_validate_with_explicit_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            serp = root / "serp.ndjson"
            doc = root / "doc.ndjson"
            extract = root / "extract.ndjson"
            citation = root / "citation.ndjson"
            web_eval = root / "eval.ndjson"
            web_trace = root / "web_trace.ndjson"
            web_output = root / "web_output.json"

            serp.write_text(
                json.dumps(
                    {
                        "url": "https://example.com",
                        "title": "Example",
                        "snippet": "Snippet",
                        "rank": 0,
                        "source": "fixture",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            doc.write_text(
                json.dumps(
                    {
                        "url": "https://example.com",
                        "final_url": "https://example.com",
                        "status": 200,
                        "headers": {"content-type": "text/html"},
                        "content_type": "text/html",
                        "bytes": 12,
                        "encoding_guess": "utf-8",
                        "body": "<p>ok</p>",
                        "body_sha256": "a" * 64,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            extract.write_text(
                json.dumps(
                    {
                        "doc_sha256": "a" * 64,
                        "url": "https://example.com",
                        "chunk_id": "chunk-1",
                        "kind": "p",
                        "path_hint": "body>p",
                        "text": "ok",
                        "score": 1.0,
                        "source_rank": 0,
                        "doc_rank": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            citation.write_text(
                json.dumps(
                    {
                        "url": "https://example.com",
                        "doc_sha256": "a" * 64,
                        "chunk_id": "chunk-1",
                        "quote": "ok",
                        "retrieved_at": 1700000000,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            web_eval.write_text(
                json.dumps(
                    {
                        "qid": "Q1",
                        "plan": "default",
                        "acc": 1.0,
                        "fetches": 1,
                        "bytes": 12,
                        "chunks": 1,
                        "cache_hit": 1.0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            web_trace.write_text(
                json.dumps(
                    {
                        "op": "search_call",
                        "ts": 0,
                        "seq": 1,
                        "ms": 0,
                        "q": "pirml",
                        "provider": "mock",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            web_output.write_text(
                json.dumps(
                    {
                        "answer": "ok",
                        "citations": [
                            {
                                "url": "https://example.com",
                                "doc_sha256": "a" * 64,
                                "chunk_id": "chunk-1",
                                "quote": "ok",
                                "retrieved_at": 1700000000,
                            }
                        ],
                        "trace_ptr": str(web_trace),
                    }
                ),
                encoding="utf-8",
            )

            completed = self._run(
                "--serp",
                str(serp),
                "--doc",
                str(doc),
                "--extract",
                str(extract),
                "--citation",
                str(citation),
                "--web-eval",
                str(web_eval),
                "--web-trace",
                str(web_trace),
                "--web-output",
                str(web_output),
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_web_artifact_schema_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "bad.citation.ndjson"
            artifact.write_text(
                json.dumps(
                    {
                        "url": "https://example.com",
                        "doc_sha256": "not-a-sha",
                        "chunk_id": "chunk-1",
                        "quote": "ok",
                        "retrieved_at": "bad",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            completed = self._run("--citation", str(artifact))
            self.assertEqual(completed.returncode, 1)
            self.assertIn("doc_sha256", completed.stderr)
            self.assertIn("retrieved_at", completed.stderr)


if __name__ == "__main__":
    unittest.main()
