from __future__ import annotations

import unittest

from pirml.artifacts import ArtifactErrorType, default_layout, parse_view_artifact_path
from pirml.artifacts.errors import ArtifactPathError


class ArtifactPathTests(unittest.TestCase):
    def test_default_layout_uses_canonical_paths(self) -> None:
        layout = default_layout()
        self.assertEqual(layout.obj_dir.as_posix(), "art/obj")
        self.assertEqual(layout.views_dir.as_posix(), "art/views")
        self.assertEqual(layout.trace_path.as_posix(), "art/trace.ndjson")
        self.assertEqual(layout.index_path.as_posix(), "art/ndx.sqlite")

    def test_reject_singular_view_dir(self) -> None:
        with self.assertRaises(ArtifactPathError) as ctx:
            parse_view_artifact_path("art/view/v-001.ndjson")
        self.assertEqual(
            ctx.exception.error["type"],
            ArtifactErrorType.PATH_UNSUPPORTED_VARIANT.value,
        )
        self.assertFalse(ctx.exception.error["retryable"])

    def test_accept_plural_view_dir(self) -> None:
        view_id = parse_view_artifact_path("art/views/v-001.ndjson")
        self.assertEqual(view_id, "v-001")


if __name__ == "__main__":
    unittest.main()
