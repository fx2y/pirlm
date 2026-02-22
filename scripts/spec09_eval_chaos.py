from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pirml.cli_common import CliFailure, parse_runner_config, parse_suite_config
from pirml.eval_runner import run_suite_shard, shard_path
from scripts.tools.common import emit_error


def _write_dataset(path: Path, rows: list[dict[str, str]]) -> Path:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _row_by_task(rows: list[dict[str, object]], task_id: str) -> dict[str, object]:
    for row in rows:
        if row.get("task_id") == task_id and row.get("terminal") is True:
            return row
    raise AssertionError(f"missing terminal row for task_id={task_id}")


def main() -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="spec09_c6_chaos_") as tmp:
            root = Path(tmp)
            out_dir = root / "out"

            timeout_dataset = _write_dataset(
                root / "timeout.jsonl",
                [{"task_id": "Q_TIMEOUT", "query": "__timeout__ case", "expected_answer": "x"}],
            )
            timeout_rows = run_suite_shard(
                suite_cfg=parse_suite_config(suite="golden50", dataset=str(timeout_dataset)),
                runner_cfg=parse_runner_config(
                    jobs=1,
                    shards=1,
                    shard=0,
                    timeout_s=10.0,
                    ctx_byte_cap=1024,
                    seed=0,
                    out_dir=str(out_dir / "timeout"),
                ),
            )
            timeout_row = _row_by_task(timeout_rows, "Q_TIMEOUT")
            if timeout_row.get("fail_tag") != "TIMEOUT":
                raise AssertionError(f"timeout lane drift: {timeout_row}")

            bad_dataset = root / "invalid.jsonl"
            bad_dataset.write_text('{"task_id":"Q1","query":"x"}\n{bad-json}\n', encoding="utf-8")
            try:
                run_suite_shard(
                    suite_cfg=parse_suite_config(suite="golden50", dataset=str(bad_dataset)),
                    runner_cfg=parse_runner_config(
                        jobs=1,
                        shards=1,
                        shard=0,
                        timeout_s=10.0,
                        ctx_byte_cap=1024,
                        seed=0,
                        out_dir=str(out_dir / "invalid"),
                    ),
                )
            except CliFailure as err:
                invalid_lane = {"rc": err.code, "type": err.err_type, "msg": err.msg}
            else:
                raise AssertionError("invalid-json lane did not fail")
            if invalid_lane["type"] != "validation" or invalid_lane["rc"] != 1:
                raise AssertionError(f"invalid-json lane drift: {invalid_lane}")

            replay_dataset = _write_dataset(
                root / "replay.jsonl",
                [{"task_id": "Q_REPLAY", "query": "alpha", "expected_answer": "alpha"}],
            )
            previous_force = os.environ.get("PIRML_REPLAY_FORCE_MISMATCH")
            os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = "Q_REPLAY"
            try:
                replay_rows = run_suite_shard(
                    suite_cfg=parse_suite_config(suite="golden50", dataset=str(replay_dataset)),
                    runner_cfg=parse_runner_config(
                        jobs=1,
                        shards=1,
                        shard=0,
                        timeout_s=10.0,
                        ctx_byte_cap=1024,
                        seed=0,
                        out_dir=str(out_dir / "replay_mismatch"),
                    ),
                )
            finally:
                if previous_force is None:
                    os.environ.pop("PIRML_REPLAY_FORCE_MISMATCH", None)
                else:
                    os.environ["PIRML_REPLAY_FORCE_MISMATCH"] = previous_force
            replay_row = _row_by_task(replay_rows, "Q_REPLAY")
            if replay_row.get("fail_tag") != "REPLAY_MISMATCH":
                raise AssertionError(f"replay lane drift: {replay_row}")

            resume_dataset = _write_dataset(
                root / "resume.jsonl",
                [{"task_id": "Q_RESUME", "query": "bravo", "expected_answer": "bravo"}],
            )
            resume_runner = parse_runner_config(
                jobs=1,
                shards=1,
                shard=0,
                timeout_s=10.0,
                ctx_byte_cap=1024,
                seed=0,
                out_dir=str(out_dir / "resume"),
            )
            resume_suite = parse_suite_config(suite="golden50", dataset=str(resume_dataset))
            shard = shard_path(out_dir=resume_runner.out_dir, suite=resume_suite.suite, shard=0)
            shard.parent.mkdir(parents=True, exist_ok=True)
            shard.write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "task_id": "Q_RESUME",
                        "suite": "golden50",
                        "shard": 0,
                        "attempt": 0,
                        "terminal": False,
                        "note": "forced_interrupt:partial",
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            first_resume_rows = run_suite_shard(suite_cfg=resume_suite, runner_cfg=resume_runner)
            second_resume_rows = run_suite_shard(suite_cfg=resume_suite, runner_cfg=resume_runner)
            if _row_by_task(first_resume_rows, "Q_RESUME").get("seq") != 2:
                raise AssertionError("resume terminal seq drift")
            if second_resume_rows[0].get("note") != "resume_skip:terminal_exists":
                raise AssertionError(f"resume skip lane drift: {second_resume_rows[0]}")

            print(
                json.dumps(
                    {
                        "ok": True,
                        "invalid_json_lane": invalid_lane,
                        "resume_skip_note": second_resume_rows[0]["note"],
                        "replay_mismatch_fail_tag": replay_row["fail_tag"],
                        "timeout_fail_tag": timeout_row["fail_tag"],
                    },
                    sort_keys=True,
                )
            )
    except CliFailure as err:
        emit_error(err.err_type, err.msg, err.code)
    except Exception as exc:
        emit_error("integrity", str(exc), 2)


if __name__ == "__main__":
    main()
