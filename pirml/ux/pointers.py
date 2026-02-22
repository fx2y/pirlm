from __future__ import annotations

import hashlib
from pathlib import Path

from pirml.clock import SequenceClock

from .types import PointerPayload


def generate_run_id(clock: SequenceClock) -> str:
    # S07: rid=f"r{clock.now():010d}"
    return f"r{clock.now():010d}"


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
    final_path = out_dir / "final.json"
    run_sha = compute_run_sha(final_path)

    # S10: payload=canonical_json({"runId":rid,"trace":trace,"final":final,"hash":sha})
    return {
        "runId": run_id,
        "trace": str(out_dir / "trace.ndjson"),
        "final": str(final_path),
        "artifactsDir": str(art_root),
        "roots": [str(out_dir), str(art_root)],
        "runSha": run_sha,
        "ts": ts,
    }


def project_last_run(out_dir: Path, art_root: Path, project_root: Path) -> None:
    # C1.T04: Implement deterministic .pirml projection facade
    pirml_dir = project_root / ".pirml"
    pirml_dir.mkdir(exist_ok=True)

    trace_src = out_dir / "trace.ndjson"
    final_src = out_dir / "final.json"

    trace_dst = pirml_dir / "trace.ndjson"
    final_dst = pirml_dir / "final.json"
    art_dst = pirml_dir / "artifacts"

    # Force rewrite (deterministic)
    for p in [trace_dst, final_dst, art_dst]:
        if p.is_symlink() or p.exists():
            if p.is_dir() and not p.is_symlink():
                import shutil

                shutil.rmtree(p)
            else:
                p.unlink()

    # Use absolute paths for symlinks to ensure they resolve from anywhere
    if trace_src.exists():
        trace_dst.symlink_to(trace_src.absolute())
    if final_src.exists():
        final_dst.symlink_to(final_src.absolute())
    if art_root.exists():
        art_dst.symlink_to(art_root.absolute())
