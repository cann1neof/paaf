"""Side A of the bake-off: the PAAF port implemented over LangChain + langchain-mcp-adapters.

THROWAWAY (SC#5, D-18). What survives is the measurement in
``.planning/phases/01-spike-gate/raw/bakeoff-results.md``.

This module is the **only** place in the bake-off allowed to import ``langchain*``. That is
not decoration: ``port.py`` is stdlib-only and ``test_port_conformance.py`` fails if any
``langchain`` type is reachable from a public annotation here. It is a small rehearsal of
the rule CLAUDE.md sets for the real framework — *all LangChain imports confined to a single
package, enforced by a lint rule that fails CI* — and doing it here is how the spike finds
out what that rule actually costs.

What it answers
---------------
* **SPIKE-05** — do Ollama token counts come back non-``None`` *through the port's trace
  layer*, on the streaming path? Read after aggregation, never off a chunk (Pitfall 8).
* **SPIKE-06** — do MCP tool **args** and **structured results** both survive the callback
  layer? The structured half lives in ``ToolMessage.artifact['structured_content']``, and
  ``port.split_tool_output`` is what keeps it (Pitfall 9).
* **SPIKE-07 / D-17** — how much translation code did hiding LangChain behind the port take.

Privacy posture (PRIV-02 / T-01-06-TEL): tracing is an ``AsyncCallbackHandler`` draining
into an in-process ``TraceRecorder``. No LangSmith client is constructed, no tracer is
registered, nothing is exported. 01-04 proved ``langsmith`` is installed but inert; this
module does nothing to change that.

Run the live probe:
    uv run --python spike/bakeoff/.venv/bin/python -m bakeoff.adapter_langchain
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from langchain.chat_models import init_chat_model
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from bakeoff.port import (
    REQUIRED_LANGCHAIN_HOOKS,
    McpServerSpec,
    ModelHandle,
    ModelProfile,
    TokenUsage,
    ToolInvocation,
    ToolRoundTrip,
    ToolSpec,
    TraceEvent,
    TraceRecorder,
    UsageAggregator,
    missing_hooks,
    naive_tool_output,
    split_tool_output,
)

__all__ = ["LangChainAdapter", "LangChainTrace", "trace_handler_gaps"]


# ======================================================================================
# Translation helpers — the private half of the port. Every line here is a line the
# PAAF boundary cost, and D-17 counts them.
# ======================================================================================


def _usage_from_metadata(raw: Any, source: str) -> TokenUsage | None:
    """``usage_metadata`` (a plain dict in langchain-core 1.x) -> PAAF :class:`TokenUsage`."""
    if not raw:
        return None
    return TokenUsage(
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        total_tokens=raw.get("total_tokens"),
        source=source,
    )


def _text_of(chunk: Any) -> str:
    """Pull display text out of a message chunk without assuming ``content`` is a string.

    ``qwen3.5`` is a *thinking* model and langchain-core 1.x carries structured content
    blocks, so ``chunk.content`` can be a list of dicts. ``.text`` is the accessor that
    flattens to the visible answer; the fallback keeps a raw string working.
    """
    text = getattr(chunk, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    parts = [
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "".join(parts)


def _tool_spec_of(tool: Any) -> ToolSpec:
    """``StructuredTool`` -> :class:`ToolSpec`. ``args_schema`` is already a JSON schema dict."""
    schema = getattr(tool, "args_schema", None)
    if not isinstance(schema, dict):
        schema = getattr(schema, "model_json_schema", lambda: {})()
    return ToolSpec(
        name=tool.name,
        description=tool.description or "",
        input_schema=dict(schema or {}),
    )


# ======================================================================================
# Tracing
# ======================================================================================


class LangChainTrace(AsyncCallbackHandler):
    """Drains LangChain's callback stream into a framework-free :class:`TraceRecorder`.

    All six hooks are overridden, and the pair that matters is ``on_chat_model_start`` +
    ``on_llm_start``. ``AsyncCallbackHandler`` supplies every hook as an inherited no-op,
    so a handler implementing only ``on_llm_start`` still *has* an ``on_chat_model_start``
    — it simply never records anything, because chat models fire the other one. That
    handler would report "prompts are not visible through callbacks" and overturn Decision
    1 on a measurement error. ``test_trace_handler.py`` pins the rule against doubles;
    ``trace_handler_gaps()`` applies it to this class.
    """

    def __init__(self, recorder: TraceRecorder) -> None:
        super().__init__()
        self.recorder = recorder
        self.last_llm_end_usage: TokenUsage | None = None
        self.raw_llm_end_usage: Any = None
        #: Kept verbatim so the probe can run the *naive* capture over the same live
        #: object. Asserting "the artifact survived" is only worth something alongside a
        #: demonstration that the wrong capture loses it on identical input.
        self.raw_tool_end_outputs: list[Any] = []

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.recorder.record_prompt(
            _render_messages(messages),
            run_id=str(run_id),
            model_choice=(metadata or {}).get("ls_model_name"),
            hook="on_chat_model_start",
        )

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.recorder.record_prompt(
            list(prompts),
            run_id=str(run_id),
            model_choice=(metadata or {}).get("ls_model_name"),
            hook="on_llm_start",
        )

    async def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        self.recorder.record_token(token, run_id=str(run_id))

    async def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """SPIKE-05's vantage point: usage rides on the FINAL result, not on a chunk."""
        raw: Any = None
        try:
            message = response.generations[0][0].message
            raw = getattr(message, "usage_metadata", None)
        except (AttributeError, IndexError):  # pragma: no cover - shape guard
            raw = None
        if not raw:
            raw = (getattr(response, "llm_output", None) or {}).get("usage_metadata")
        self.raw_llm_end_usage = raw
        usage = _usage_from_metadata(raw, source="on_llm_end")
        self.last_llm_end_usage = usage
        self.recorder.record_usage(usage, run_id=str(run_id))

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """SPIKE-06, args half. ``inputs`` is the parsed dict; ``input_str`` the rendering."""
        args = inputs if isinstance(inputs, dict) else {"__input_str__": input_str}
        self.recorder.record_tool_start(
            ToolInvocation(name=serialized.get("name", "?"), args=dict(args)),
            run_id=str(run_id),
        )

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """SPIKE-06, results half. The whole object — ``str(output)`` is the bug (Pitfall 9)."""
        name = getattr(output, "name", None) or kwargs.get("name") or "?"
        self.raw_tool_end_outputs.append(output)
        self.recorder.record_tool_end(split_tool_output(str(name), output), run_id=str(run_id))


def _render_messages(messages: Any) -> list[list[dict[str, Any]]]:
    """Framework messages -> plain dicts, so the trace holds no ``BaseMessage``."""
    rendered: list[list[dict[str, Any]]] = []
    for batch in messages or []:
        rendered.append(
            [
                {
                    "type": getattr(m, "type", "?"),
                    "content": _text_of(m),
                }
                for m in batch
            ]
        )
    return rendered


def trace_handler_gaps() -> tuple[str, ...]:
    """Required callback hooks this adapter's handler does not override itself."""
    return missing_hooks(LangChainTrace, REQUIRED_LANGCHAIN_HOOKS)


# ======================================================================================
# The adapter
# ======================================================================================


class LangChainAdapter:
    """The D-16 port surface, over LangChain. No framework type crosses the boundary."""

    name = "langchain"

    def __init__(self) -> None:
        self._recorder = TraceRecorder()
        self._handler = LangChainTrace(self._recorder)
        self._model: Any = None
        self._profile: ModelProfile | None = None
        self._mcp_client: Any = None
        self._tools: list[Any] = []
        #: Set by :meth:`stream`; SPIKE-05's streaming-path answer.
        self.stream_usage: TokenUsage | None = None
        self.stream_chunk_usages: list[TokenUsage | None] = []

    # -- 1. model loading from a named profile ---------------------------------------
    async def load_profile(self, profile: ModelProfile) -> ModelHandle:
        options = dict(profile.options)
        if profile.base_url:
            options["base_url"] = profile.base_url
        self._model = init_chat_model(f"{profile.provider}:{profile.model_id}", **options)
        self._profile = profile
        self._recorder.record_run_start(f"load_profile:{profile.name}")
        return ModelHandle(
            profile_name=profile.name,
            provider=profile.provider,
            model_id=profile.model_id,
            loaded=self._model is not None,
        )

    # -- 5. MCP ----------------------------------------------------------------------
    async def attach_mcp(self, spec: McpServerSpec) -> tuple[ToolSpec, ...]:
        self._mcp_client = MultiServerMCPClient(
            {
                spec.name: {
                    "command": spec.command,
                    "args": list(spec.args),
                    "transport": spec.transport,
                }
            }
        )
        self._tools = await self._mcp_client.get_tools()
        return tuple(_tool_spec_of(tool) for tool in self._tools)

    # -- 2. streaming ----------------------------------------------------------------
    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield text tokens; read usage only once the stream is closed (Pitfall 8)."""
        aggregator = UsageAggregator()
        self.stream_chunk_usages = []
        config = {"callbacks": [self._handler]}
        async for chunk in self._model.astream(prompt, config=config):
            usage = _usage_from_metadata(getattr(chunk, "usage_metadata", None), "chunk")
            aggregator.add_chunk(usage)
            self.stream_chunk_usages.append(usage)
            text = _text_of(chunk)
            if text:
                yield text
        aggregator.finish(self._handler.last_llm_end_usage)
        self.stream_usage = aggregator.usage

    # -- 3. one tool-call round trip --------------------------------------------------
    async def call_tool(self, prompt: str) -> ToolRoundTrip:
        bound = self._model.bind_tools(self._tools)
        config = {"callbacks": [self._handler]}
        by_name = {tool.name: tool for tool in self._tools}

        first = await bound.ainvoke([HumanMessage(prompt)], config=config)
        history: list[Any] = [HumanMessage(prompt), first]
        invocations: list[ToolInvocation] = []
        results = []

        for call in getattr(first, "tool_calls", []) or []:
            invocations.append(ToolInvocation(name=call["name"], args=dict(call["args"])))
            tool = by_name.get(call["name"])
            if tool is None:
                self._recorder.record_error(f"model called unknown tool {call['name']!r}")
                continue
            # Passing the whole tool_call (not just args) is what makes langchain return a
            # ToolMessage carrying `.artifact` rather than the bare content half.
            message = await tool.ainvoke(call, config=config)
            history.append(message)
            results.append(split_tool_output(call["name"], message))

        final = await bound.ainvoke(history, config=config)
        return ToolRoundTrip(
            prompt=prompt,
            final_text=_text_of(final),
            invocations=tuple(invocations),
            results=tuple(results),
            usage=_usage_from_metadata(getattr(final, "usage_metadata", None), "ainvoke"),
        )

    # -- 4. tracing ------------------------------------------------------------------
    def trace_events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._recorder.events)

    @property
    def recorder(self) -> TraceRecorder:
        return self._recorder

    async def aclose(self) -> None:
        self._tools = []
        self._mcp_client = None
        self._model = None


# ======================================================================================
# Live probe
# ======================================================================================

PROFILE = ModelProfile(
    name="local-capable",
    provider="ollama",
    model_id="qwen3.5:9b",
    base_url=None,
)

MCP_SPEC = McpServerSpec(
    name="probe",
    command=sys.executable,
    args=("spike/bakeoff/mcp_server/server.py",),
)

STREAM_PROMPT = "Reply with exactly the words: hello from the port."
TOOL_PROMPT = "What is the current status of the kitchen? Use the room_status tool."


async def run_probe() -> dict[str, Any]:
    """Exercise the whole port once and return the SPIKE-05/06 evidence as plain data."""
    started = time.perf_counter()
    adapter = LangChainAdapter()
    evidence: dict[str, Any] = {"adapter": adapter.name}

    handle = await adapter.load_profile(PROFILE)
    evidence["model_handle"] = {
        "profile_name": handle.profile_name,
        "provider": handle.provider,
        "model_id": handle.model_id,
        "loaded": handle.loaded,
    }

    specs = await adapter.attach_mcp(MCP_SPEC)
    evidence["mcp_tools"] = [
        {"name": s.name, "description": s.description, "arg_keys": sorted(s.input_schema.get("properties", {}))}
        for s in specs
    ]

    t0 = time.perf_counter()
    chunks: list[str] = []
    async for token in adapter.stream(STREAM_PROMPT):
        chunks.append(token)
    evidence["stream"] = {
        "seconds": round(time.perf_counter() - t0, 2),
        "yielded_chunks": len(chunks),
        "text": "".join(chunks).strip()[:200],
        "chunk_usages_populated": sum(
            1 for u in adapter.stream_chunk_usages if u is not None and u.is_populated
        ),
        "chunk_usages_total": len(adapter.stream_chunk_usages),
    }
    evidence["spike_05"] = {
        "streaming_usage_after_aggregation": _usage_dict(adapter.stream_usage),
        "on_llm_end_raw_usage_metadata": adapter._handler.raw_llm_end_usage,
        "naive_first_chunk_read": _usage_dict(
            adapter.stream_chunk_usages[0] if adapter.stream_chunk_usages else None
        ),
    }

    t1 = time.perf_counter()
    trip = await adapter.call_tool(TOOL_PROMPT)
    evidence["spike_06"] = {
        "seconds": round(time.perf_counter() - t1, 2),
        "invocations": [{"name": i.name, "args": dict(i.args)} for i in trip.invocations],
        "results": [
            {
                "name": r.name,
                "content_preview": str(r.content)[:120],
                "artifact_present": r.artifact_present,
                "structured_content": dict(r.structured_content) if r.structured_content else None,
            }
            for r in trip.results
        ],
        "final_text": trip.final_text.strip()[:300],
        "final_usage": _usage_dict(trip.usage),
    }

    recorder = adapter.recorder
    handler = adapter._handler

    # What the CALLBACK layer saw, as distinct from what call_tool assembled for itself.
    # SPIKE-06 is a question about callbacks, so the evidence has to come from them.
    evidence["spike_06_via_callbacks"] = {
        "tool_start_args": [dict(i.args) for i in recorder.tool_invocations],
        "tool_end_output_types": [
            f"{type(o).__module__}.{type(o).__name__}" for o in handler.raw_tool_end_outputs
        ],
        "correct_capture_structured_content": [
            dict(r.structured_content) if r.structured_content else None
            for r in recorder.tool_results
        ],
        # The negative control, on the same live objects: Pitfall 9's str(output).
        "naive_capture_structured_content": [
            naive_tool_output("room_status", o).structured_content
            for o in handler.raw_tool_end_outputs
        ],
        "naive_capture_artifact_present": [
            naive_tool_output("room_status", o).artifact_present
            for o in handler.raw_tool_end_outputs
        ],
    }
    # Live evidence for the "implement BOTH start hooks" rule: which one actually fired.
    evidence["start_hooks_that_fired"] = sorted(set(h for h in recorder.prompt_hooks if h))

    evidence["trace_summary"] = recorder.summary()
    evidence["trace_kinds"] = sorted({e.kind for e in recorder.events})
    evidence["callback_hook_gaps"] = list(trace_handler_gaps())
    evidence["telemetry"] = _telemetry_state()
    evidence["total_seconds"] = round(time.perf_counter() - started, 2)

    await adapter.aclose()
    return evidence


def _usage_dict(usage: TokenUsage | None) -> dict[str, Any] | None:
    if usage is None:
        return None
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "source": usage.source,
        "is_populated": usage.is_populated,
    }


def _telemetry_state() -> dict[str, Any]:
    """Asserted, not assumed (PRIV-02). 01-04 proved the exporters ship installed-but-inert."""
    import importlib.util

    from langsmith.utils import tracing_is_enabled

    return {
        "langsmith_tracing_enabled": bool(tracing_is_enabled()),
        "real_logfire_installed": importlib.util.find_spec("logfire") is not None,
    }


def main() -> None:
    evidence = asyncio.run(run_probe())
    print(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
