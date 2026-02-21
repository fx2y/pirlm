from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast


def validate_error(error: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(error, dict):
        return [f"{path} must be an object"]

    if "type" not in error:
        errors.append(f"{path} missing required 'type'")
    if "msg" not in error:
        errors.append(f"{path} missing required 'msg'")

    allowed = {"type", "msg", "retryable"}
    for key in cast(Mapping[str, Any], error):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")

    if "type" in error and not isinstance(error["type"], str):
        errors.append(f"{path}.type must be a string")
    if "msg" in error and not isinstance(error["msg"], str):
        errors.append(f"{path}.msg must be a string")
    if "retryable" in error and not isinstance(error["retryable"], bool):
        errors.append(f"{path}.retryable must be a boolean")

    return errors


def validate_result(result: Any, index: int) -> list[str]:
    errors: list[str] = []
    path = f"results[{index}]"
    if not isinstance(result, dict):
        return [f"{path} must be an object"]

    for req in ["id", "tool", "ok"]:
        if req not in result:
            errors.append(f"{path} missing required '{req}'")

    allowed = {"id", "tool", "ok", "error"}
    for key in cast(Mapping[str, Any], result):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")

    if "id" in result:
        res_id = cast(str, result["id"])
        if not re.match(r"^c[0-9]{5}$", res_id):
            errors.append(f"{path}.id '{res_id}' violates pattern ^c[0-9]{{5}}$")

    if "tool" in result and not isinstance(result["tool"], str):
        errors.append(f"{path}.tool must be a string")
    if "ok" in result and not isinstance(result["ok"], bool):
        errors.append(f"{path}.ok must be a boolean")

    if "error" in result:
        errors.extend(validate_error(result["error"], f"{path}.error"))

    return errors


def validate_contract(contract_raw: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(contract_raw, dict):
        return [f"{path} must be an object"]
    contract = cast(dict[str, Any], contract_raw)

    for req in ["tool_deps", "io_schema", "budgets", "assertions"]:
        if req not in contract:
            errors.append(f"{path} missing required '{req}'")

    if "tool_deps" in contract:
        tool_deps = contract["tool_deps"]
        if not isinstance(tool_deps, list):
            errors.append(f"{path}.tool_deps must be a list")
        else:
            for item in cast(list[Any], tool_deps):
                if not isinstance(item, str):
                    errors.append(f"{path}.tool_deps must be a list of strings")

    if "io_schema" in contract:
        io_raw = contract["io_schema"]
        if not isinstance(io_raw, dict):
            errors.append(f"{path}.io_schema must be an object")
        else:
            io = cast(dict[str, Any], io_raw)
            for req in ["trace_ptr", "final_schema", "citations_schema"]:
                if req not in io:
                    errors.append(f"{path}.io_schema missing required '{req}'")
            if "trace_ptr" in io and not isinstance(io["trace_ptr"], str):
                errors.append(f"{path}.io_schema.trace_ptr must be a string")

    if "budgets" in contract:
        budgets_raw = contract["budgets"]
        if not isinstance(budgets_raw, dict):
            errors.append(f"{path}.budgets must be an object")
        else:
            budgets = cast(dict[str, Any], budgets_raw)
            fields = ["max_calls", "max_parallel", "max_bytes_in", "max_bytes_out", "timeout_s"]
            for field in fields:
                if field not in budgets:
                    errors.append(f"{path}.budgets missing required '{field}'")
                elif not isinstance(budgets[field], int) or budgets[field] < 1:
                    errors.append(f"{path}.budgets.{field} must be a positive integer")

    if "assertions" in contract and not isinstance(contract["assertions"], list):
        errors.append(f"{path}.assertions must be a list")

    return errors


def validate_verification_error(error: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(error, dict):
        return [f"{path} must be an object"]

    for req in ["code", "msg"]:
        if req not in error:
            errors.append(f"{path} missing required '{req}'")

    allowed = {"code", "msg", "line", "symbol"}
    for key in cast(Mapping[str, Any], error):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")

    return errors


def validate_compile_error(ce: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(ce, dict):
        return [f"{path} must be an object"]

    for req in ["ok", "errors", "warnings", "stage"]:
        if req not in ce:
            errors.append(f"{path} missing required '{req}'")

    if "ok" in ce and ce["ok"] is not False:
        errors.append(f"{path}.ok must be false")

    if "stage" in ce and not isinstance(ce["stage"], str):
        errors.append(f"{path}.stage must be a string")

    if "errors" in ce:
        ce_errors = cast(Any, ce["errors"])
        if not isinstance(ce_errors, list):
            errors.append(f"{path}.errors must be a list")
        else:
            for i, err in enumerate(cast(list[Any], ce_errors)):
                errors.extend(validate_verification_error(err, f"{path}.errors[{i}]"))

    if "warnings" in ce:
        ce_warnings = cast(Any, ce["warnings"])
        if not isinstance(ce_warnings, list):
            errors.append(f"{path}.warnings must be a list")
        else:
            for i, err in enumerate(cast(list[Any], ce_warnings)):
                errors.extend(validate_verification_error(err, f"{path}.warnings[{i}]"))

    return errors


def _has_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_row_artifact(path: Path) -> tuple[list[Any], list[str]]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return [], ["artifact is empty"]

    # Try full JSON first (array or single object)
    if stripped[0] in "[{":
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return cast(list[Any], parsed), []
            if isinstance(parsed, dict):
                return [parsed], []
        except json.JSONDecodeError:
            # Might be NDJSON where first line is an object
            pass

    # Fallback to NDJSON (line-by-line)
    rows: list[Any] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            return [], [f"line {idx}: invalid JSON: {exc}"]
    if not rows:
        return [], ["artifact has no rows"]
    return rows, []


def validate_serp_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    errors: list[str] = []
    allowed = {"url", "title", "snippet", "rank", "source"}
    required = {"url", "title", "snippet", "rank", "source"}
    for req in required:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in cast(Mapping[str, Any], row):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "url" in row and not isinstance(row["url"], str):
        errors.append(f"{path}.url must be a string")
    if "title" in row and not isinstance(row["title"], str):
        errors.append(f"{path}.title must be a string")
    if "snippet" in row and not isinstance(row["snippet"], str):
        errors.append(f"{path}.snippet must be a string")
    if "rank" in row and not _is_int(row["rank"]):
        errors.append(f"{path}.rank must be an integer")
    if "source" in row and not isinstance(row["source"], str):
        errors.append(f"{path}.source must be a string")
    return errors


def validate_doc_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    row_map = cast(dict[str, Any], row)
    errors: list[str] = []
    allowed = {
        "url",
        "final_url",
        "status",
        "headers",
        "content_type",
        "bytes",
        "encoding_guess",
        "body",
        "body_sha256",
    }
    required = allowed
    for req in required:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in row_map:
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "url" in row_map and not isinstance(row_map["url"], str):
        errors.append(f"{path}.url must be a string")
    if "final_url" in row_map and not isinstance(row_map["final_url"], str):
        errors.append(f"{path}.final_url must be a string")
    if "status" in row_map and not _is_int(row_map["status"]):
        errors.append(f"{path}.status must be an integer")
    if "headers" in row_map:
        headers = row_map["headers"]
        if not isinstance(headers, dict):
            errors.append(f"{path}.headers must be an object")
        else:
            for value in cast(Mapping[str, Any], headers).values():
                if not isinstance(value, str):
                    errors.append(f"{path}.headers must be string:string map")
                    break
    if "content_type" in row_map and not isinstance(row_map["content_type"], str):
        errors.append(f"{path}.content_type must be a string")
    if "bytes" in row_map and not _is_int(row_map["bytes"]):
        errors.append(f"{path}.bytes must be an integer")
    if "encoding_guess" in row_map and not isinstance(row_map["encoding_guess"], str):
        errors.append(f"{path}.encoding_guess must be a string")
    if "body" in row_map and not isinstance(row_map["body"], str):
        errors.append(f"{path}.body must be a string")
    if "body_sha256" in row_map and not _has_sha256(row_map["body_sha256"]):
        errors.append(f"{path}.body_sha256 must be a 64-char lower-hex digest")
    return errors


def validate_extract_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    errors: list[str] = []
    allowed = {
        "doc_sha256",
        "url",
        "chunk_id",
        "kind",
        "path_hint",
        "text",
        "score",
        "source_rank",
        "doc_rank",
    }
    for req in allowed:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in cast(Mapping[str, Any], row):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "doc_sha256" in row and not _has_sha256(row["doc_sha256"]):
        errors.append(f"{path}.doc_sha256 must be a 64-char lower-hex digest")
    if "url" in row and not isinstance(row["url"], str):
        errors.append(f"{path}.url must be a string")
    if "chunk_id" in row and not isinstance(row["chunk_id"], str):
        errors.append(f"{path}.chunk_id must be a string")
    if "kind" in row and not isinstance(row["kind"], str):
        errors.append(f"{path}.kind must be a string")
    if "path_hint" in row and not isinstance(row["path_hint"], str):
        errors.append(f"{path}.path_hint must be a string")
    if "text" in row and not isinstance(row["text"], str):
        errors.append(f"{path}.text must be a string")
    if "score" in row and not _is_number(row["score"]):
        errors.append(f"{path}.score must be numeric")
    if "source_rank" in row and not _is_int(row["source_rank"]):
        errors.append(f"{path}.source_rank must be an integer")
    if "doc_rank" in row and not _is_int(row["doc_rank"]):
        errors.append(f"{path}.doc_rank must be an integer")
    return errors


def validate_citation_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    errors: list[str] = []
    allowed = {"url", "doc_sha256", "chunk_id", "quote", "retrieved_at"}
    for req in allowed:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in cast(Mapping[str, Any], row):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "url" in row and not isinstance(row["url"], str):
        errors.append(f"{path}.url must be a string")
    if "doc_sha256" in row and not _has_sha256(row["doc_sha256"]):
        errors.append(f"{path}.doc_sha256 must be a 64-char lower-hex digest")
    if "chunk_id" in row and not isinstance(row["chunk_id"], str):
        errors.append(f"{path}.chunk_id must be a string")
    if "quote" in row and not isinstance(row["quote"], str):
        errors.append(f"{path}.quote must be a string")
    if "retrieved_at" in row and not _is_int(row["retrieved_at"]):
        errors.append(f"{path}.retrieved_at must be an integer")
    return errors


def validate_web_eval_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    errors: list[str] = []
    allowed = {"qid", "plan", "acc", "fetches", "bytes", "chunks", "cache_hit", "note"}
    required = {"qid", "plan", "acc", "fetches", "bytes", "chunks", "cache_hit"}
    for req in required:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in cast(Mapping[str, Any], row):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "qid" in row and not isinstance(row["qid"], str):
        errors.append(f"{path}.qid must be a string")
    if "plan" in row and not isinstance(row["plan"], str):
        errors.append(f"{path}.plan must be a string")
    if "acc" in row and not _is_number(row["acc"]):
        errors.append(f"{path}.acc must be numeric")
    if "fetches" in row and not _is_int(row["fetches"]):
        errors.append(f"{path}.fetches must be an integer")
    if "bytes" in row and not _is_int(row["bytes"]):
        errors.append(f"{path}.bytes must be an integer")
    if "chunks" in row and not _is_int(row["chunks"]):
        errors.append(f"{path}.chunks must be an integer")
    if "cache_hit" in row and not _is_number(row["cache_hit"]):
        errors.append(f"{path}.cache_hit must be numeric")
    if "note" in row and not isinstance(row["note"], str):
        errors.append(f"{path}.note must be a string")
    return errors


def validate_web_trace_row(row: Any, index: int) -> list[str]:
    path = f"rows[{index}]"
    if not isinstance(row, dict):
        return [f"{path} must be an object"]
    errors: list[str] = []
    allowed = {
        "op",
        "ts",
        "seq",
        "ms",
        "q",
        "url",
        "provider",
        "status",
        "bytes",
        "sha256",
        "cache_hit",
        "error",
    }
    required = {"op", "ts", "seq", "ms"}
    for req in required:
        if req not in row:
            errors.append(f"{path} missing required '{req}'")
    for key in cast(Mapping[str, Any], row):
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    valid_ops = {"search_call", "search_result", "fetch_call", "fetch_result"}
    if "op" in row and row["op"] not in valid_ops:
        errors.append(f"{path}.op must be one of {sorted(valid_ops)}")
    if "ts" in row and not _is_int(row["ts"]):
        errors.append(f"{path}.ts must be an integer")
    if "seq" in row and not _is_int(row["seq"]):
        errors.append(f"{path}.seq must be an integer")
    if "ms" in row and not _is_int(row["ms"]):
        errors.append(f"{path}.ms must be an integer")
    if "url" in row and not isinstance(row["url"], str):
        errors.append(f"{path}.url must be a string")
    if "q" in row and not isinstance(row["q"], str):
        errors.append(f"{path}.q must be a string")
    if "provider" in row and not isinstance(row["provider"], str):
        errors.append(f"{path}.provider must be a string")
    if "status" in row and not _is_int(row["status"]):
        errors.append(f"{path}.status must be an integer")
    if "bytes" in row and not _is_int(row["bytes"]):
        errors.append(f"{path}.bytes must be an integer")
    if "sha256" in row and not _has_sha256(row["sha256"]):
        errors.append(f"{path}.sha256 must be a 64-char lower-hex digest")
    if "cache_hit" in row and not isinstance(row["cache_hit"], bool):
        errors.append(f"{path}.cache_hit must be a boolean")
    if "error" in row and not isinstance(row["error"], str):
        errors.append(f"{path}.error must be a string")
    return errors


def validate_web_output(payload: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{path} must be an object"]
    allowed = {"answer", "citations", "trace_ptr"}
    required = allowed
    payload_map = cast(dict[str, Any], payload)
    for req in required:
        if req not in payload_map:
            errors.append(f"{path} missing required '{req}'")
    for key in payload_map:
        if key not in allowed:
            errors.append(f"{path} has unexpected field '{key}'")
    if "answer" in payload_map and not isinstance(payload_map["answer"], str):
        errors.append(f"{path}.answer must be a string")
    if "trace_ptr" in payload_map and not isinstance(payload_map["trace_ptr"], str):
        errors.append(f"{path}.trace_ptr must be a string")
    if "citations" in payload_map:
        citations = payload_map["citations"]
        if not isinstance(citations, list):
            errors.append(f"{path}.citations must be a list")
        else:
            for i, citation in enumerate(cast(list[Any], citations)):
                errors.extend(validate_citation_row(citation, i))
    return errors


def _validate_json_artifacts(
    *,
    paths: list[Path] | None,
    missing_label: str,
    validate: Callable[[Any, str], list[str]],
) -> int:
    if not paths:
        return 0

    exit_code = 0
    for artifact_path in paths:
        if not artifact_path.exists():
            print(
                f"Error: Required {missing_label} artifact missing: {artifact_path}",
                file=sys.stderr,
            )
            return 1
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            errors = validate(payload, str(artifact_path))
            if errors:
                print(f"Schema validation failed for {artifact_path}:", file=sys.stderr)
                for err in errors:
                    print(f"  - {err}", file=sys.stderr)
                exit_code = 1
            else:
                print(f"Verified {artifact_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading {artifact_path}: {exc}", file=sys.stderr)
            exit_code = 1
    return exit_code


def _validate_row_artifacts(
    *,
    paths: list[Path] | None,
    missing_label: str,
    validate_row: Callable[[Any, int], list[str]],
) -> int:
    if not paths:
        return 0

    exit_code = 0
    for artifact_path in paths:
        if not artifact_path.exists():
            print(
                f"Error: Required {missing_label} artifact missing: {artifact_path}",
                file=sys.stderr,
            )
            return 1

        rows, parse_errors = _parse_row_artifact(artifact_path)
        errors = list(parse_errors)
        for index, row in enumerate(rows):
            errors.extend(validate_row(row, index))

        if errors:
            print(f"Schema validation failed for {artifact_path}:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"Verified {artifact_path}")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description="PIRML Schema Linter")

    parser.add_argument("--final", type=Path, help="Path to final.json artifact")
    parser.add_argument(
        "--contract", action="append", type=Path, help="Path(s) to contract.json artifacts"
    )
    parser.add_argument(
        "--compile-error",
        action="append",
        type=Path,
        help="Path(s) to compile_error.json artifacts",
    )
    parser.add_argument("--serp", action="append", type=Path, help="Path(s) to SERP artifacts")
    parser.add_argument(
        "--doc", action="append", type=Path, help="Path(s) to fetched-doc artifacts"
    )
    parser.add_argument(
        "--extract", action="append", type=Path, help="Path(s) to extract/chunk artifacts"
    )
    parser.add_argument(
        "--citation", action="append", type=Path, help="Path(s) to citation artifacts"
    )
    parser.add_argument(
        "--web-eval", action="append", type=Path, help="Path(s) to web eval artifacts"
    )
    parser.add_argument(
        "--web-trace", action="append", type=Path, help="Path(s) to web trace artifacts"
    )
    parser.add_argument("--web-output", type=Path, help="Path to web output artifact")

    args = parser.parse_args()
    if not any(
        (
            args.final,
            args.contract,
            args.compile_error,
            args.serp,
            args.doc,
            args.extract,
            args.citation,
            args.web_eval,
            args.web_trace,
            args.web_output,
        )
    ):
        print(
            "Error: pass at least one artifact path "
            "("
            "--final/--contract/--compile-error/--serp/--doc/--extract/--citation/"
            "--web-eval/--web-trace/--web-output"
            ")",
            file=sys.stderr,
        )
        return 1

    exit_code = 0

    if args.final:
        final_path = args.final
        if not final_path.exists():
            print(f"Error: Required final artifact missing: {final_path}", file=sys.stderr)
            return 1
        try:
            final = json.loads(final_path.read_text(encoding="utf-8"))
            errors: list[str] = []
            if not isinstance(final, dict):
                errors.append("Root must be an object")
            else:
                if "ok" not in final:
                    errors.append("Root missing required 'ok'")
                if "results" not in final:
                    errors.append("Root missing required 'results'")
                allowed = {"ok", "results", "output", "meta"}
                for key in cast(Mapping[str, Any], final):
                    if key not in allowed:
                        errors.append(f"Root has unexpected field '{key}'")
                if "ok" in final and not isinstance(final["ok"], bool):
                    errors.append("Root.ok must be a boolean")
                if "results" in final:
                    results = cast(list[Any], final["results"])
                    for i, result in enumerate(results):
                        errors.extend(validate_result(result, i))
            if errors:
                print(f"Schema validation failed for {final_path}:", file=sys.stderr)
                for err in errors:
                    print(f"  - {err}", file=sys.stderr)
                exit_code = 1
            else:
                print(f"Verified {final_path}")
        except Exception as exc:  # noqa: BLE001
            print(f"Error reading {final_path}: {exc}", file=sys.stderr)
            exit_code = 1

    exit_code = max(
        exit_code,
        _validate_json_artifacts(
            paths=args.contract,
            missing_label="contract",
            validate=validate_contract,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_json_artifacts(
            paths=args.compile_error,
            missing_label="compile_error",
            validate=validate_compile_error,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(
            paths=args.serp, missing_label="serp", validate_row=validate_serp_row
        ),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(paths=args.doc, missing_label="doc", validate_row=validate_doc_row),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(
            paths=args.extract,
            missing_label="extract",
            validate_row=validate_extract_row,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(
            paths=args.citation,
            missing_label="citation",
            validate_row=validate_citation_row,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(
            paths=args.web_eval,
            missing_label="web-eval",
            validate_row=validate_web_eval_row,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_row_artifacts(
            paths=args.web_trace,
            missing_label="web-trace",
            validate_row=validate_web_trace_row,
        ),
    )
    exit_code = max(
        exit_code,
        _validate_json_artifacts(
            paths=[args.web_output] if args.web_output else None,
            missing_label="web-output",
            validate=validate_web_output,
        ),
    )
    if args.web_output and args.web_output.exists():
        try:
            payload = json.loads(args.web_output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            payload_map = cast(dict[str, Any], payload)
            trace_ptr = payload_map.get("trace_ptr")
            if isinstance(trace_ptr, str):
                ptr_path = Path(trace_ptr)
                if not ptr_path.exists():
                    print(
                        f"Error: web_output.trace_ptr target missing: {ptr_path}",
                        file=sys.stderr,
                    )
                    exit_code = 1
                if args.web_trace and ptr_path not in args.web_trace:
                    print(
                        f"Error: web_output.trace_ptr {ptr_path} not listed in --web-trace args",
                        file=sys.stderr,
                    )
                    exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
