from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def derive_summary(out_dir: Path) -> str | None:
    """C1.T06: Derive UX summary from output/web_output artifacts only."""
    # S21: Derive from web_output.json rich result
    web_out_path = out_dir / "web_output.json"
    if web_out_path.exists():
        try:
            wo = json.loads(web_out_path.read_text(encoding="utf-8"))
            if isinstance(wo, dict):
                wo_dict = cast("dict[str, Any]", wo)
                ans = wo_dict.get("answer", "")
                if isinstance(ans, str) and ans:
                    return ans[:120] + ("..." if len(ans) > 120 else "")
        except Exception:
            pass

    # Fallback to final.json output.answer
    final_path = out_dir / "final.json"
    if final_path.exists():
        try:
            final = json.loads(final_path.read_text(encoding="utf-8"))
            if not isinstance(final, dict):
                return None
            final_dict = cast("dict[str, Any]", final)
            output = final_dict.get("output", {})
            if isinstance(output, dict):
                output_dict = cast("dict[str, Any]", output)
                ans = output_dict.get("answer")
                if isinstance(ans, str):
                    return ans[:120] + ("..." if len(ans) > 120 else "")
        except Exception:
            pass

    return None
