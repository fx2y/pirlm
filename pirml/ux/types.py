from typing import Any, TypedDict


class PointerPayload(TypedDict):
    runId: str
    trace: str
    final: str
    artifactsDir: str
    roots: list[str]
    runSha: str
    ts: int


class RunResult(TypedDict):
    ok: bool
    runId: str
    pointer: PointerPayload | None
    error: Any | None
    output: Any | None
    meta: Any | None
