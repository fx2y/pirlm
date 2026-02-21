from __future__ import annotations

import asyncio
import contextlib
import io
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from pirml.artifacts.errors import ArtifactPathError
from pirml.artifacts.store import ArtifactStore
from pirml.artifacts.view_dsl import SliceSpec
from pirml.artifacts.view_materialize import ViewMaterializer
from pirml.clock import SequenceClock
from pirml.compiler.model import ModelAdapter
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
            import os

            emit_pi_pointers = os.getenv("PIRML_EMIT_PI_POINTERS") == "1"
        self.emit_pi_pointers = emit_pi_pointers
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
            full_prompt = self.build_prompt(state)
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
                from .governor import create_citation_map

                citations = create_citation_map([], str(state.Final))

                # C5.T07: Emit web_output.json (Optional, if store has a base path)
                if hasattr(self.store.layout, "root"):
                    out_path = Path(self.store.layout.root) / "web_output.json"
                    # S32: Project final under root {ok,results,output?,meta?}
                    web_out = {
                        "ok": True,
                        "results": [],  # Supervisor fills this in runtime, but placeholder for now
                        "output": {
                            "answer": str(state.Final),
                            "citations": citations,
                        },
                        "meta": {"iters": iters + 1, "subcalls": self._subcall_count},
                    }
                    out_path.write_text(json.dumps(web_out, indent=2))

                    # C6.T01: Emit pi CustomEntry pointer row
                    if self.emit_pi_pointers:
                        from pirml.runtime.rpc import send_custom

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

    def build_prompt(self, state: RlmState) -> str:
        # C5.T02/T04: Context Governor with bulk off-ctx
        from .governor import K_CAP_TOKENS, apply_cohesion_rule, est_tokens, pack_ctx

        items: list[dict[str, Any]] = []
        # Variables
        s_dict = state.to_dict()
        for k, v in s_dict.items():
            critical = k == "P"
            if isinstance(v, list) and k in ("DOCS", "CHUNKS", "SUMS", "BUF"):
                v_list = cast("list[Any]", v)
                # S34: Handle-only ctx pack / excerpt
                items.append(
                    {
                        "id": f"var:{k}",
                        "text": f"BulkVar {k}: list (len={len(v_list)})",  # Meta only
                        "kind": "var",
                        "critical": critical,
                    }
                )
                # Add excerpts separately as candidates
                for i, x in enumerate(v_list[:50]):
                    items.append(
                        {
                            "id": f"var:{k}:{i}",
                            "text": f"{k}[{i}]: {str(x)[:240]}",  # S34 excerpt cap
                            "kind": "excerpt",
                            "critical": False,
                        }
                    )
            else:
                items.append(
                    {"id": f"var:{k}", "text": str(v), "kind": "var", "critical": critical}
                )

        # History
        for f in self.history:
            # C6.T03: Hard-block ctx contamination
            if f["ev"] == "custom":
                continue

            items.append(
                {
                    "id": f"history:{f['seq']}",
                    "text": f"Hist {f['seq']} ({f['ev']}): {f['prefix']}... (len={f['len']})",
                    "kind": "history",
                    "ev": f["ev"],
                }
            )

        # Pack under budget
        packed_ids = pack_ctx(state.P, items, k_limit=K_CAP_TOKENS)
        # Apply cohesion (ensure call/result pairs stay if applicable, though here mostly logs)
        final_ids = apply_cohesion_rule(packed_ids, items)

        final_ids_set = set(final_ids)
        parts = [f"Goal: {state.P}"]

        vars_block: list[str] = []
        hist_block: list[str] = []
        for it in items:
            if it["id"] in final_ids_set:
                if it["kind"] == "var":
                    vars_block.append(it["text"])
                else:
                    hist_block.append(it["text"])

        if vars_block:
            parts.append("Variables:\n" + "\n".join(vars_block))
        if hist_block:
            parts.append("History:\n" + "\n".join(hist_block))

        if self.emit_pi_pointers:
            from pirml.runtime.rpc import send_custom
            tokens_before = sum(est_tokens(it["text"]) for it in items)
            first_kept = final_ids[0] if final_ids else None
            send_custom(
                "pirml_summary",
                {
                    "summary": f"Context packed: {len(final_ids)}/{len(items)} items kept",
                    "firstKeptEntryId": first_kept,
                    "tokensBefore": tokens_before,
                },
            )

        return "\n\n".join(parts)

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
                    wrap_code = "async def __rlm_exec_wrap():\n" + "\n".join(
                        f"    {line}" for line in code.splitlines()
                    )
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
        self,
        data: bytes | str,
        kind: str = "raw",
        mime: str = "text/plain",
        parents: list[str] | None = None,
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
