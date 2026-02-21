from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .kernel import RlmKernel


def project_web_output(
    kernel: RlmKernel,
    answer: str,
    citations: list[dict[str, Any]],
) -> Path | None:
    """I10: Final root compact contract unchanged.
    G07: Unify web_output shape {answer, citations, trace_ptr}.
    """
    if not hasattr(kernel.store.layout, "root"):
        return None

    out_path = Path(kernel.store.layout.root) / "web_output.json"
    web_out: dict[str, Any] = {
        "answer": answer,
        "citations": citations,
        "trace_ptr": str(kernel.store.layout.trace_path),
    }
    out_path.write_text(json.dumps(web_out, indent=2))
    return out_path
