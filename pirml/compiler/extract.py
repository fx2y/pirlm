from __future__ import annotations

import re
from typing import Tuple


class ExtractionError(Exception):
    def __init__(self, type: str, msg: str):
        self.type = type
        self.msg = msg
        super().__init__(f"{type}: {msg}")


def extract_blocks(raw_text: str) -> Tuple[str, str]:
    """C1.T6: Strict sentinel extractor (<<<PROG>>>/<<<CONTRACT>>>).
    Rejects extra prose, missing blocks, or duplicate sentinels.
    """
    m = re.split(r"<<<(PROG|CONTRACT)>>>", raw_text)

    # re.split(r'<<<(PROG|CONTRACT)>>>', 'pre<<<PROG>>>prog<<<CONTRACT>>>contract') ->
    # ['pre', 'PROG', 'prog', 'CONTRACT', 'contract']
    if len(m) != 5:
        raise ExtractionError(
            "sentinel_cardinality", f"Expected exactly 2 sentinels (PROG/CONTRACT), found {len(m)//2}"
        )

    if m[0].strip():
        raise ExtractionError("extra_prose", "Leading prose detected")

    if m[1] != "PROG":
        raise ExtractionError("invalid_order", f"Expected PROG sentinel first, found {m[1]}")

    if m[3] != "CONTRACT":
        raise ExtractionError("invalid_order", f"Expected CONTRACT sentinel second, found {m[3]}")

    prog_src = m[2].strip()
    contract_src = m[4].strip()

    return prog_src, contract_src
