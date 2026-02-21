from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from pirml.artifacts.errors import ArtifactPathError
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec
from pirml.artifacts.view_materialize import ViewMaterializer
from pirml.clock import SequenceClock
from pirml.compiler.model import ModelAdapter
import asyncio
from pirml.web.etl import chunk_views, pack_batches

from .errors import RlmKernelError
from .history import RlmHistory
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
        self.history = RlmHistory()
        self.view_vm = ViewMaterializer(store)
        self._subcall_count = 0
        self._parallel_sem = asyncio.Semaphore(self.budget["max_parallel"])

    async def run(self, prompt: str) -> Any:
        import time

        start_time = time.monotonic()
        state = RlmState(P=prompt)

        # C3.T02: REPL executor injects helpers get,put,llm_query
        helpers = {
            "get": self._get_helper,
            "put": self._put_helper,
            "llm_query": self._llm_query_helper,
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
            full_prompt = self._build_prompt(state)
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
                return state.Final

            iters += 1

        raise RlmKernelError(
            error_type=RlmErrorType.MAX_ITERS_REACHED,
            msg=f"Max iterations ({self.budget['max_iters']}) reached without Final set",
        )

    def _build_prompt(self, state: RlmState) -> str:
        # Simplistic prompt for now, showing metadata-only history
        return f"Prompt: {state.P}\nHistory: {self.history.to_dict_list()}\nVars: {state.to_dict()}"

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
                    wrap_code = f"async def __rlm_exec_wrap():\n" + "\n".join(f"    {l}" for l in code.splitlines())
                    locs: dict[str, Any] = {}
                    exec(wrap_code, globs, locs)
                    await locs["__rlm_exec_wrap"]()
                else:
                    exec(code, globs)
                state.update(globs)
            except RlmKernelError:
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Error: {e}")
        return stdout.getvalue()

    def _get_helper(self, aid_vid: str, spec: SliceSpec | None = None) -> str:
        try:
            if spec:
                vid = self.view_vm.materialize(aid_vid, spec)
                return self.store.get_view_text(vid)
            else:
                kind = self.store.index.get_kind(aid_vid)
                if kind == "slice":
                    return self.store.get_view_text(aid_vid)
                elif kind:
                    return self.store.get_bytes(aid_vid).decode("utf-8", errors="replace")
                else:
                    raise RlmKernelError(
                        error_type=RlmErrorType.INVALID_ARGS, msg=f"Not found: {aid_vid}"
                    )
        except ArtifactPathError as e:
            raise RlmKernelError(error_type=RlmErrorType.INVALID_ARGS, msg=str(e)) from e
        except Exception as e:
            raise RlmKernelError(error_type=RlmErrorType.INTEGRITY, msg=str(e)) from e

    def _put_helper(
        self, data: bytes | str, kind: str = "raw", mime: str = "text/plain", parents: list[str] | None = None
    ) -> str:
        data_bytes = data.encode("utf-8") if isinstance(data, str) else data
        return self.store.put_raw(data_bytes, kind=kind, mime=mime, parents=parents)

    async def _llm_query_helper(self, prompt: str) -> str:
        # C3.T06: Budget guards
        self._subcall_count += 1
        if self._subcall_count > 20:
            import sys
            print(
                f"Warning: subcall count {self._subcall_count} exceeds soft limit 20",
                file=sys.stderr,
            )

        if self._subcall_count > self.budget["max_subcalls"]:
            raise RlmKernelError(
                error_type=RlmErrorType.BUDGET_EXCEEDED,
                msg=f"Max subcalls ({self.budget['max_subcalls']}) exceeded",
            )
        return await asyncio.to_thread(self.model.compile_once, prompt)

    async def _amap_helper(self, prompts: list[str]) -> list[str]:
        """C4.T02: Map step uses bounded asyncio.gather; merge order equals source chunk order"""
        async def _limited_query(p: str) -> str:
            async with self._parallel_sem:
                return await self._llm_query_helper(p)
        
        tasks = [asyncio.create_task(_limited_query(p)) for p in prompts]
        return list(await asyncio.gather(*tasks))
