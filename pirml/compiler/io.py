from __future__ import annotations

from pathlib import Path

from pirml.compiler.types import CompileContract, CompileErr, CompileErrorFile
from pirml.runtime.rpc import canonical_json


def write_raw(path: Path, raw_text: str) -> None:
    """Write raw model output to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_text, encoding="utf-8")


def write_prog(path: Path, prog_src: str) -> None:
    """Write generated prog.py to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(prog_src, encoding="utf-8")


def write_contract(path: Path, contract: CompileContract) -> None:
    """Write contract.json using canonical JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(contract), encoding="utf-8")


def write_compile_error(path: Path, error: CompileErr | CompileErrorFile) -> None:
    """Write compile_error.json using canonical JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(error), encoding="utf-8")
