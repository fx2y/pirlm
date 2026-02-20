from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class RedFailCase:
    id: str
    cycle: str
    invariant: str


@dataclass(frozen=True)
class CompileFixtureCase:
    id: str
    stage: str
    task: str
    tools_topk: tuple[str, ...]
    raw_model_text: str
    expect: str
    expected_fail_id: str | None


EXTRACT_RED_FAILS: tuple[RedFailCase, ...] = (
    RedFailCase("FAIL_B0_EXTRA_TEXT_REJECTED", "C1", "V.B0.SENTINEL"),
    RedFailCase("FAIL_B0_MISSING_CONTRACT_BLOCK", "C1", "V.B0.SENTINEL"),
    RedFailCase("FAIL_B0_DUPLICATE_SENTINEL", "C1", "V.B0.SENTINEL"),
    RedFailCase("FAIL_B0_CONTRACT_JSON_INVALID", "C1", "V.B0.CONTRACT_JSON"),
    RedFailCase("FAIL_B0_PROG_SIZE_OVER_CAP", "C1", "V.B0.PROG_SIZE"),
)

VERIFY_RED_FAILS: tuple[RedFailCase, ...] = (
    RedFailCase("FAIL_B1_TOOL_DEP_HALLUCINATION", "C2", "V.B1.TOOL_DEPS"),
    RedFailCase("FAIL_B1_BUDGET_MISSING_OR_NEGATIVE", "C2", "V.B1.BUDGETS"),
    RedFailCase("FAIL_B1_IOSCHEMA_MISSING", "C2", "V.B1.IOSCHEMA"),
    RedFailCase("FAIL_B2_IMPORT_DENIED", "C2", "V.B2.IMPORTS"),
    RedFailCase("FAIL_B2_BANNED_CALL_DETECTED", "C2", "V.B2.BAN_CALLS"),
    RedFailCase("FAIL_B2_NONAWAIT_OR_UNKNOWN_WRAPPER", "C2", "V.B2.CALL_SHAPE"),
    RedFailCase("FAIL_B2_HIDDEN_SERIAL_REJECTED", "C2", "V.B2.GATHER"),
    RedFailCase("FAIL_B2_EXTRA_PRINT_REJECTED", "C2", "V.B2.SINGLE_FINAL"),
)

SMOKE_RED_FAILS: tuple[RedFailCase, ...] = (
    RedFailCase("FAIL_B3_STDOUT_CHATTER", "C3", "V.B3.SMOKE_JSON"),
    RedFailCase("FAIL_B3_MULTI_FINAL", "C3", "V.B3.SMOKE_JSON"),
    RedFailCase("FAIL_B3_CALL_BUDGET_OVERFLOW", "C3", "V.B3.BUDGET_CALLS"),
    RedFailCase("FAIL_B3_PARALLEL_BUDGET_OVERFLOW", "C3", "V.B3.BUDGET_CALLS"),
    RedFailCase("FAIL_B3_BYTES_BUDGET_OVERFLOW", "C3", "V.B3.BYTES"),
    RedFailCase("FAIL_B3_TIMEOUT", "C3", "V.B3.SMOKE_JSON"),
    RedFailCase("FAIL_B3_DETERMINISM_DRIFT", "C3", "V.B3.DET"),
)


def all_red_fail_ids() -> tuple[str, ...]:
    rows = EXTRACT_RED_FAILS + VERIFY_RED_FAILS + SMOKE_RED_FAILS
    return tuple(row.id for row in rows)


def load_fixture_cases(path: Path) -> tuple[CompileFixtureCase, ...]:
    rows: list[CompileFixtureCase] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        decoded: object = json.loads(line)
        if not isinstance(decoded, dict):
            raise ValueError("fixture row must be an object")
        obj = cast(dict[str, object], decoded)

        if obj.get("k") == "meta":
            continue
        required = {"id", "stage", "task", "tools_topk", "raw_model_text", "expect"}
        missing = required.difference(obj)
        if missing:
            raise ValueError(
                f"fixture {obj.get('id', '<unknown>')} missing keys: {sorted(missing)}"
            )

        fixture_id = obj["id"]
        stage = obj["stage"]
        task = obj["task"]
        raw_model_text = obj["raw_model_text"]
        expect = obj["expect"]
        if (
            not isinstance(fixture_id, str)
            or not isinstance(stage, str)
            or not isinstance(task, str)
            or not isinstance(raw_model_text, str)
            or not isinstance(expect, str)
        ):
            raise ValueError("fixture scalar fields must be strings")

        tools_topk_obj = obj["tools_topk"]
        if not isinstance(tools_topk_obj, list):
            raise ValueError(f"fixture {fixture_id} tools_topk must be list[str]")
        tools_topk_seq = cast(list[object], tools_topk_obj)
        tools_topk_items: list[str] = []
        for item in tools_topk_seq:
            if not isinstance(item, str):
                raise ValueError(f"fixture {fixture_id} tools_topk must be list[str]")
            tools_topk_items.append(item)
        tools_topk = tuple(tools_topk_items)

        expected_fail_obj = obj.get("expected_fail_id")
        if expected_fail_obj is not None and not isinstance(expected_fail_obj, str):
            raise ValueError(f"fixture {fixture_id} expected_fail_id must be str|null")

        rows.append(
            CompileFixtureCase(
                id=fixture_id,
                stage=stage,
                task=task,
                tools_topk=tools_topk,
                raw_model_text=raw_model_text,
                expect=expect,
                expected_fail_id=expected_fail_obj,
            )
        )
    return tuple(rows)
