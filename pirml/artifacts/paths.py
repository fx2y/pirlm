from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import ArtifactErrorType, ArtifactPathError


@dataclass(frozen=True)
class ArtifactLayout:
    root: Path
    obj_dir: Path
    views_dir: Path
    trace_path: Path
    index_path: Path


def default_layout(root: str | Path = "art") -> ArtifactLayout:
    root_path = Path(root)
    return ArtifactLayout(
        root=root_path,
        obj_dir=root_path / "obj",
        views_dir=root_path / "views",
        trace_path=root_path / "trace.ndjson",
        index_path=root_path / "ndx.sqlite",
    )


def _normalized_parts(path: str | Path) -> tuple[str, ...]:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return tuple(part for part in normalized.split("/") if part not in {"", "."})


def parse_view_artifact_path(path: str | Path) -> str:
    parts = _normalized_parts(path)
    if len(parts) < 3:
        raise ArtifactPathError(
            error_type=ArtifactErrorType.PATH_INVALID,
            msg=f"invalid view artifact path: {path}",
        )

    for idx in range(len(parts) - 1):
        if parts[idx] == "art" and parts[idx + 1] == "view":
            raise ArtifactPathError(
                error_type=ArtifactErrorType.PATH_UNSUPPORTED_VARIANT,
                msg="unsupported variant: art/view; use art/views",
            )

    for idx in range(len(parts) - 2):
        if parts[idx] == "art" and parts[idx + 1] == "views":
            view_file = parts[idx + 2]
            if idx + 3 != len(parts):
                raise ArtifactPathError(
                    error_type=ArtifactErrorType.PATH_INVALID,
                    msg=f"invalid view artifact path: {path}",
                )
            if not view_file.endswith(".ndjson") or len(view_file) <= len(".ndjson"):
                raise ArtifactPathError(
                    error_type=ArtifactErrorType.PATH_INVALID,
                    msg=f"invalid view filename: {view_file}",
                )
            return view_file[: -len(".ndjson")]

    raise ArtifactPathError(
        error_type=ArtifactErrorType.PATH_INVALID,
        msg=f"invalid view artifact path: {path}",
    )
