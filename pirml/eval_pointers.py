from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict, cast

from pirml.artifacts import ArtifactStore, default_layout
from pirml.cli_common import CliFailure


class EvalPointerPayload(TypedDict):
    suite: str
    task_id: str
    run_id: str
    trace_ptr: str
    artifact_ids: list[str]
    report_ptr: str
    fail_tag: str


def build_eval_pointer_payload(
    *,
    suite: str,
    task_id: str,
    run_id: str,
    trace_ptr: str,
    artifact_ids: list[str],
    report_ptr: str = "",
    fail_tag: str = "",
) -> EvalPointerPayload:
    return {
        "suite": suite,
        "task_id": task_id,
        "run_id": run_id,
        "trace_ptr": trace_ptr,
        "artifact_ids": sorted(artifact_ids),
        "report_ptr": report_ptr,
        "fail_tag": fail_tag,
    }


def validate_eval_pointer_refs(rows: list[dict[str, Any]], *, art_root: str | Path) -> None:
    store = ArtifactStore(default_layout(Path(art_root)))
    try:
        for row in rows:
            raw = row.get("pi_ptr")
            if raw is None:
                continue
            if not isinstance(raw, dict):
                raise CliFailure("validation", "pi_ptr must be object when present", 1)
            ptr = cast(dict[str, Any], raw)
            for key in ("suite", "task_id", "run_id", "trace_ptr", "report_ptr", "fail_tag"):
                val = ptr.get(key, "")
                if not isinstance(val, str):
                    raise CliFailure("validation", f"pi_ptr.{key} must be string", 1)
            artifact_ids = ptr.get("artifact_ids")
            if not isinstance(artifact_ids, list) or any(not isinstance(x, str) for x in artifact_ids):
                raise CliFailure("validation", "pi_ptr.artifact_ids must be list[str]", 1)

            for path_key in ("trace_ptr", "report_ptr"):
                raw_path = cast(str, ptr.get(path_key, ""))
                if not raw_path:
                    continue
                path = Path(raw_path)
                if not path.exists():
                    raise CliFailure("unsupported", f"missing ref {path_key}: {path}", 1, retryable=False)
            for aid in cast(list[str], artifact_ids):
                if store.get_meta(aid) is None:
                    raise CliFailure("unsupported", f"missing ref artifact_id: {aid}", 1, retryable=False)
    finally:
        store.close()


__all__ = ["EvalPointerPayload", "build_eval_pointer_payload", "validate_eval_pointer_refs"]
