from __future__ import annotations

import unittest


@unittest.skip("Spec08 C2 declared in C0; implementation lands in C2.")
class Spec08C2RunnerTests(unittest.TestCase):
    def test_append_only(self) -> None:
        pass

    def test_append_only_resume(self) -> None:
        pass

    def test_resume_skips_terminal(self) -> None:
        pass

    def test_timeout_tagged(self) -> None:
        pass

    def test_worker_continues_after_timeout(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
