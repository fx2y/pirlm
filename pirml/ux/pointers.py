from __future__ import annotations

import hashlib
from pathlib import Path

from .types import PointerPayload


def compute_run_sha(final_path: Path) -> str:
    # H6: Byte law: hash persisted/emitted bytes only
    if not final_path.exists():
        return ""
    content = final_path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def create_pointer_payload(
    run_id: str,
    out_dir: Path,
    art_root: Path,
    ts: int,
) -> PointerPayload:
    artifacts_dir = art_root if art_root.exists() else out_dir
    final_path = out_dir / "final.json"
    run_sha = compute_run_sha(final_path)

    # S10: payload=canonical_json({"runId":rid,"trace":trace,"final":final,"hash":sha})
    return {
        "runId": run_id,
        "trace": str(out_dir / "trace.ndjson"),
        "final": str(final_path),
        "artifactsDir": str(artifacts_dir),
        "roots": [str(out_dir), str(artifacts_dir)],
        "runSha": run_sha,
        "ts": ts,
    }


def project_last_run(out_dir: Path, art_root: Path, project_root: Path) -> None:
    # C1.T04: Implement deterministic .pirml projection facade
    pirml_dir = project_root / ".pirml"
    if pirml_dir.is_symlink() or pirml_dir.is_file():
        pirml_dir.unlink()
    pirml_dir.mkdir(exist_ok=True)

    trace_src = out_dir / "trace.ndjson"
    final_src = out_dir / "final.json"

    trace_dst = pirml_dir / "trace.ndjson"
    final_dst = pirml_dir / "final.json"
    art_dst = pirml_dir / "artifacts"

    # Replace only existing projection links/files; never recursively delete directories.
    for p in [trace_dst, final_dst, art_dst]:
        if p.is_symlink() or p.is_file():
            p.unlink()
            continue
        if p.is_dir():
            raise FileExistsError(f"Refusing to replace non-projection directory: {p}")

    # Use absolute paths for symlinks to ensure they resolve from anywhere
    if trace_src.exists():
        trace_dst.symlink_to(trace_src.absolute())
    if final_src.exists():
        final_dst.symlink_to(final_src.absolute())
    # Keep artifacts pointer resolvable even when canonical art/ root is absent.
    artifacts_src = art_root if art_root.exists() else out_dir
    art_dst.symlink_to(artifacts_src.absolute())
