from __future__ import annotations

import asyncio
import contextlib
import io
import os
import sys
import time
import traceback
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from pirml.artifacts.errors import ArtifactPathError
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec
from pirml.artifacts.view_materialize import ViewMaterializer
from pirml.clock import SequenceClock
from pirml.compiler.model import ModelAdapter
from pirml.runtime.rpc import send_custom
from pirml.web.etl import chunk_views, pack_batches

from .errors import RlmKernelError
from .governor import build_rlm_prompt, create_citation_map
from .history import RlmHistory
from .project import project_web_output
from .types import RlmBudget, RlmErrorType


@dataclass
class RlmState:
    P: str
    Final: Any | None = None
    DOCS: list[str] = field(default_factory=lambda: cast("list[str]", []))
    CHUNKS: list[str] = field(default_factory=lambda: cast("list[str]", []))
    SUMS: list[str] = field(default_factory=lambda: cast("list[str]", []))
    BUF: list[Any] = field(default_factory=lambda: cast("list[Any]", []))

    def to_dict(self) -> dict[str, Any]:
        """C3.T01: State dataclass owns big vars"""
        return {
            "P": self.P,
            "Final": self.Final,
            "DOCS": list(self.DOCS),
            "CHUNKS": list(self.CHUNKS),
            "SUMS": list(self.SUMS),
            "BUF": list(self.BUF),
        }

    def update(self, globs: Mapping[str, Any]) -> None:
        for k in ["Final", "DOCS", "CHUNKS", "SUMS", "BUF"]:
            if k in globs:
                setattr(self, k, globs[k])


class RlmKernel:
    def __init__(
        self,
        store: ArtifactStore,
        model_adapter: ModelAdapter,
        budget: RlmBudget | None = None,
        clock: SequenceClock | None = None,
        emit_pi_pointers: bool | None = None,
    ) -> None:
        self.store = store
        self.model = model_adapter
        self.budget: RlmBudget = budget or {
            "max_iters": 10,
            "max_subcalls": 200,
            "max_parallel": 5,
            "timeout_s": 30.0,
        }
        self.clock = clock or SequenceClock.from_env()
        # C6.T00: Opt-in via flag or env
        if emit_pi_pointers is None:
            emit_pi_pointers = os.getenv("PIRML_EMIT_PI_POINTERS") == "1"
        self.emit_pi_pointers = emit_pi_pointers
        self.history = RlmHistory()
        self.view_vm = ViewMaterializer(store)
        self.subcall_count = 0
        self.parallel_sem = asyncio.Semaphore(self.budget["max_parallel"])

    async def run(self, prompt: str) -> Any:
        self.history = RlmHistory()
        self.subcall_count = 0
        start_time = time.monotonic()
        state = RlmState(P=prompt)

        # C3.T02: REPL executor injects helpers get,put,llm_query
        helpers = {
            "get": self._get_helper,
            "put": self._put_helper,
            "llm_query": self.llm_query_helper,
            "amap": self._amap_helper,
            "chunk_views": chunk_views,
            "pack_batches": pack_batches,
        }

        iters = 0
        while iters < self.budget["max_iters"]:
            # C3.T06: Timeout guard
            if time.monotonic() - start_time > self.budget["timeout_s"]:
                raise RlmKernelError(
                    error_type=RlmErrorType.INTEGRITY,
                    msg=f"RLM kernel timeout after {self.budget['timeout_s']}s",
                )

            # 1. Root LM generates code
            full_prompt = build_rlm_prompt(state, self.history, self.emit_pi_pointers)
            code = await asyncio.to_thread(self.model.compile_once, full_prompt)

            # 2. REPL exec
            stdout = await self._repl_exec(state, code, helpers)

            # 3. History update (metadata only) C3.T03
            self.history.append(
                ev="log",
                prefix=stdout[:100],
                full_len=len(stdout),
                ts=self.clock.now(),
                code=code,
            )

            # 4. Stop condition C3.T04
            if state.Final is not None:
                # C5.T05/T06: Project final and pack citations
                ts_now = self.clock.now()
                citations = create_citation_map([], str(state.Final), ts=ts_now)

                # C5.T07, I10: Emit web_output.json
                out_path = project_web_output(self, str(state.Final), citations)

                # C6.T01: Emit pi CustomEntry pointer row
                if self.emit_pi_pointers and out_path:
                    # Collect roots from DOCS/CHUNKS/SUMS
                    roots = list(set(state.DOCS + state.CHUNKS + state.SUMS))
                    send_custom(
                        "pirml",
                        {
                            "trace": str(self.store.layout.trace_path),
                            "final": str(out_path),
                            "roots": roots,
                        },
                    )

                return state.Final

            iters += 1

        raise RlmKernelError(
            error_type=RlmErrorType.MAX_ITERS_REACHED,
            msg=f"Max iterations ({self.budget['max_iters']}) reached without Final set",
        )

    async def _repl_exec(self, state: RlmState, code: str, helpers: dict[str, Any]) -> str:
        # C3.T07: Enforce channel split
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            try:
                globs = state.to_dict()
                globs.update(helpers)
                # To support async in exec, we wrap in an async function
                # or use a more sophisticated approach.
                # For C4, we want top-level await support in the generated code.
                if "await " in code:
                    # S31: Propagate state assignments from async wrapper
                    state_keys = ["Final", "DOCS", "CHUNKS", "SUMS", "BUF"]
                    globals_decl = "    global " + ", ".join(state_keys) + "\n"
                    wrap_code = (
                        "async def __rlm_exec_wrap():\n"
                        + globals_decl
                        + "\n".join(f"    {line}" for line in code.splitlines())
                    )
                    exec(wrap_code, globs)
                    await globs["__rlm_exec_wrap"]()
                else:
                    exec(code, globs)
                state.update(globs)
            except RlmKernelError:
                raise
            except Exception as e:
                traceback.print_exc()
                print(f"Error: {e}")
        return stdout.getvalue()

    def _get_helper(self, aid_vid: str, spec: SliceSpec | None = None) -> str:
        # G08: Strip prefixes before calling store
        clean_id = aid_vid
        if aid_vid.startswith(("cas_", "vid_")):
            clean_id = aid_vid[4:]

        try:
            if spec:
                vid = self.view_vm.materialize(clean_id, spec)
                return self.store.get_view_text(vid)

            kind = self.store.index.get_kind(clean_id)
            if kind == "slice":
                return self.store.get_view_text(clean_id)
            if kind:
                return self.store.get_bytes(clean_id).decode("utf-8", errors="replace")

            raise RlmKernelError(error_type=RlmErrorType.INVALID_ARGS, msg=f"Not found: {aid_vid}")
        except ArtifactPathError as e:
            raise RlmKernelError(error_type=RlmErrorType.INVALID_ARGS, msg=str(e)) from e
        except Exception as e:
            raise RlmKernelError(error_type=RlmErrorType.INTEGRITY, msg=str(e)) from e

    def _put_helper(
        self,
        data: bytes | str,
        kind: str = "raw",
        mime: str = "text/plain",
        parents: list[str] | None = None,
    ) -> str:
        # G08: Strip prefixes from parents if they exist
        clean_parents = None
        if parents:
            clean_parents = [p[4:] if p.startswith(("cas_", "vid_")) else p for p in parents]

        data_bytes = data.encode("utf-8") if isinstance(data, str) else data
        aid = self.store.put_raw(data_bytes, kind=kind, mime=mime, parents=clean_parents)
        # G08: Return with cas_ prefix for citation mapping
        return f"cas_{aid}"

    async def llm_query_helper(self, prompt: str) -> str:
        # C3.T06: Budget guards
        self.subcall_count += 1
        if self.subcall_count > 20:
            print(
                f"Warning: subcall count {self.subcall_count} exceeds soft limit 20",
                file=sys.stderr,
            )

        if self.subcall_count > self.budget["max_subcalls"]:
            raise RlmKernelError(
                error_type=RlmErrorType.BUDGET_EXCEEDED,
                msg=f"Max subcalls ({self.budget['max_subcalls']}) exceeded",
            )
        return await asyncio.to_thread(self.model.compile_once, prompt)

    async def _amap_helper(self, prompts: list[str]) -> list[str]:
        """C4.T02: Map step uses bounded asyncio.gather; merge order equals source chunk order"""
        from .recursion import amap_recursive

        return await amap_recursive(self, prompts)
