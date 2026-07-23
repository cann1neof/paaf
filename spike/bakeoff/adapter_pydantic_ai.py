"""Side B of the bake-off: the same PAAF port implemented over Pydantic AI **v2**.

THROWAWAY (SC#5, D-18).

Same port, same MCP server, same Ollama model, same trace vocabulary as
``adapter_langchain.py``. Only the framework underneath differs — which is the whole point:
D-17 asks what each one *costs* to hide, and that is unanswerable unless both are hiding the
same thing.

Pitfall 12 governs every import below. ``MCPServerStdio`` / ``MCPServerSSE`` /
``MCPServerStreamableHTTP`` do **not exist** in 2.x, and ``mcp_servers=`` / ``instrument=`` /
``prepare_tools=`` are gone from the ``Agent`` constructor. Every symbol used here was
read out of the installed 2.13.0 wheel by introspection before it was written, not recalled.
Getting this wrong would end the bake-off on a typo and score Pydantic AI as "harder" for a
reason that has nothing to do with porting.

Privacy (PRIV-02 / T-01-06-TEL): ``pydantic_ai.capabilities.Instrumentation`` is the
OpenTelemetry/Logfire integration point and is **deliberately not used**. ``Hooks`` gives
in-process tracing with no exporter. The probe asserts this at runtime rather than claiming it.

Run the live probe:
    uv run --python spike/bakeoff/.venv/bin/python -m bakeoff.adapter_pydantic_ai
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent
from pydantic_ai.capabilities import Hooks
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

from bakeoff.port import (
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
    structured_content_matches,
)

#: What `mcp_server/server.py` is known to send for `room_status("kitchen")`. Comparing
#: against it — rather than against "an artifact was present" — is what keeps SPIKE-06
#: from passing for any tool that returns anything.
EXPECTED_STRUCTURED = {
    "room": "kitchen",
    "temperature_c": 21.5,
    "humidity_pct": 44,
    "devices": ["kettle", "ceiling-lamp"],
}

__all__ = ["PydanticAIAdapter", "PydanticAITrace", "trace_handler_gaps"]

#: The v2 hooks this adapter must implement to cover the same ground LangChain's six
#: callbacks cover. There is no chat/completion split here — one ``before_model_request``
#: serves both — which removes LangChain's single sharpest trap outright.
REQUIRED_PYDANTIC_AI_HOOKS: tuple[str, ...] = (
    "before_model_request",
    "after_model_request",
    "before_tool_execute",
    "after_tool_execute",
    # LangChain's `on_llm_new_token` has no direct counterpart; `on.event` carries the
    # whole AgentStreamEvent stream, of which text deltas are one kind. Registered so the
    # trace-fidelity comparison is not decided by something this adapter simply skipped.
    "event",
)


# ======================================================================================
# Translation helpers — the private half of the port
# ======================================================================================


def _usage_from_run_usage(raw: Any, source: str) -> TokenUsage | None:
    """``RunUsage``/``RequestUsage`` -> PAAF :class:`TokenUsage`.

    Pydantic AI names these ``input_tokens``/``output_tokens`` on an object rather than a
    dict, and exposes no ``total``; it is summed here so the two adapters report the same
    shape and the SPIKE-05 comparison is like-for-like.
    """
    if raw is None:
        return None
    input_tokens = getattr(raw, "input_tokens", None)
    output_tokens = getattr(raw, "output_tokens", None)
    total = getattr(raw, "total_tokens", None)
    if total is None and input_tokens is not None and output_tokens is not None:
        total = input_tokens + output_tokens
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        source=source,
    )


def _render_messages(messages: Any) -> list[dict[str, Any]]:
    """``ModelMessage`` list -> plain dicts, so the trace holds no framework object."""
    rendered: list[dict[str, Any]] = []
    for message in messages or []:
        rendered.append(
            {
                "kind": getattr(message, "kind", "?"),
                "parts": [
                    {
                        "part_kind": getattr(part, "part_kind", type(part).__name__),
                        "content": str(getattr(part, "content", ""))[:2000],
                    }
                    for part in getattr(message, "parts", [])
                ],
            }
        )
    return rendered


def _tool_spec_of(tool: Any) -> ToolSpec:
    """``mcp.types.Tool`` -> :class:`ToolSpec`. ``list_tools()`` returns raw MCP types."""
    return ToolSpec(
        name=tool.name,
        description=tool.description or "",
        input_schema=dict(tool.inputSchema or {}),
    )


def _text_of_response(response: Any) -> str:
    """Flatten a ``ModelResponse``'s parts to the visible answer, skipping thinking parts."""
    parts = getattr(response, "parts", []) or []
    out: list[str] = []
    for part in parts:
        if getattr(part, "part_kind", "") == "text":
            out.append(str(getattr(part, "content", "")))
    return "".join(out)


# ======================================================================================
# Tracing
# ======================================================================================


class PydanticAITrace:
    """Drains Pydantic AI v2 ``Hooks`` into the same framework-free :class:`TraceRecorder`.

    A structural difference worth naming, because it is a *risk* difference and not a
    style one: LangChain callbacks are fire-and-forget observers, while these hooks are
    **transformers** — each one must return the value it was handed
    (``before_model_request`` returns the request context, ``after_tool_execute`` returns
    the result). A tracer that forgets a ``return`` does not merely fail to record; it
    corrupts the run it was watching. Observation is not free of side effects here.
    """

    def __init__(self, recorder: TraceRecorder) -> None:
        self.recorder = recorder
        self.last_response_usage: TokenUsage | None = None
        self.raw_response_usage: Any = None
        #: Kept verbatim so the probe can run the naive capture over the same live objects.
        self.raw_tool_results: list[Any] = []

    async def before_model_request(self, ctx: Any, request_context: Any) -> Any:
        model = getattr(request_context, "model", None)
        self.recorder.record_prompt(
            _render_messages(getattr(request_context, "messages", [])),
            run_id=str(getattr(ctx, "run_id", "") or ""),
            model_choice=getattr(model, "model_name", None),
            hook="before_model_request",
        )
        return request_context

    async def after_model_request(self, ctx: Any, *, request_context: Any, response: Any) -> Any:
        """SPIKE-05's vantage point on this side: usage rides on the ``ModelResponse``."""
        raw = getattr(response, "usage", None)
        self.raw_response_usage = raw
        usage = _usage_from_run_usage(raw, source="after_model_request")
        self.last_response_usage = usage
        self.recorder.record_usage(usage, run_id=str(getattr(ctx, "run_id", "") or ""))
        return response

    async def before_tool_execute(
        self, ctx: Any, *, call: Any, tool_def: Any, args: Any
    ) -> Any:
        """SPIKE-06, args half."""
        name = getattr(tool_def, "name", None) or getattr(call, "tool_name", "?")
        self.recorder.record_tool_start(
            ToolInvocation(name=str(name), args=dict(args) if isinstance(args, dict) else {"args": args}),
            run_id=str(getattr(ctx, "run_id", "") or ""),
        )
        return args

    async def after_tool_execute(
        self, ctx: Any, *, call: Any, tool_def: Any, args: Any, result: Any
    ) -> Any:
        """SPIKE-06, results half. ``split_tool_output`` is shared with the LangChain side."""
        name = getattr(tool_def, "name", None) or getattr(call, "tool_name", "?")
        self.raw_tool_results.append(result)
        self.recorder.record_tool_end(
            split_tool_output(str(name), result),
            run_id=str(getattr(ctx, "run_id", "") or ""),
        )
        return result

    async def event(self, ctx: Any, event: Any) -> Any:
        """Per-event hook — the nearest counterpart to LangChain's ``on_llm_new_token``.

        There is no token hook in v2; there is an event stream, and text deltas are one
        event kind within it. Filtering for ``TextPartDelta`` here reconstructs the same
        signal, so the fidelity comparison is not decided by an omission on this side.
        """
        delta = getattr(event, "delta", None)
        token = getattr(delta, "content_delta", None)
        if isinstance(token, str) and token:
            self.recorder.record_token(token, run_id=str(getattr(ctx, "run_id", "") or ""))
        return event

    def as_capability(self) -> Hooks:
        """Register every hook and hand back the ``Hooks`` capability."""
        hooks = Hooks()
        hooks.on.before_model_request(self.before_model_request)
        hooks.on.after_model_request(self.after_model_request)
        hooks.on.before_tool_execute(self.before_tool_execute)
        hooks.on.after_tool_execute(self.after_tool_execute)
        hooks.on.event(self.event)
        return hooks


#: `Hooks._registry` key -> the public `hooks.on.<name>` that registered it.
_REGISTRY_ALIASES = {"_on_event": "event"}


def registered_hook_names(hooks: Hooks) -> tuple[str, ...]:
    """Which hooks a ``Hooks`` instance actually has registered.

    Reaches for the private ``_registry`` because 2.13.0 exposes no public accessor —
    ``repr(hooks)`` renders it (``Hooks({'before_model_request': 1})``) but there is no
    supported way to ask. Recorded as friction, not worked around silently: *verifying
    that your tracing is wired up requires a private attribute.*
    """
    registry = getattr(hooks, "_registry", None)
    if isinstance(registry, dict):
        # And the keys are not the public names: `hooks.on.event(...)` registers under
        # `_on_event`. Two layers of private detail to answer "is my tracer wired up?".
        return tuple(sorted(_REGISTRY_ALIASES.get(k, k) for k in registry))
    return ()  # pragma: no cover - would signal an upstream rename


def trace_handler_gaps() -> tuple[str, ...]:
    """Required hooks this adapter's tracer does not implement itself."""
    defined = missing_hooks(
        PydanticAITrace, REQUIRED_PYDANTIC_AI_HOOKS, framework_roots=("pydantic_ai",)
    )
    registered = registered_hook_names(PydanticAITrace(TraceRecorder()).as_capability())
    unregistered = tuple(h for h in REQUIRED_PYDANTIC_AI_HOOKS if h not in registered)
    return tuple(sorted(set(defined) | set(unregistered)))


# ======================================================================================
# The adapter
# ======================================================================================


class PydanticAIAdapter:
    """The D-16 port surface, over Pydantic AI v2. No framework type crosses the boundary."""

    name = "pydantic_ai"

    def __init__(self) -> None:
        self._recorder = TraceRecorder()
        self._tracer = PydanticAITrace(self._recorder)
        self._hooks: Any = None
        self._model: Any = None
        self._profile: ModelProfile | None = None
        self._toolset: Any = None
        self._stack = AsyncExitStack()
        self._agent_plain: Any = None
        self._agent_tools: Any = None
        self.stream_usage: TokenUsage | None = None
        self.stream_chunk_usages: list[TokenUsage | None] = []

    # -- 1. model loading from a named profile ---------------------------------------
    async def load_profile(self, profile: ModelProfile) -> ModelHandle:
        # `Agent("ollama:qwen3.5:9b")` alone raises UserError here: the Ollama provider is
        # built on the OpenAI SDK and demands an explicit OpenAI-compatible base URL (or
        # OLLAMA_BASE_URL). So the profile's base_url is mandatory on this side, and it must
        # carry the `/v1` sub-path — the same PAAF profile cannot be handed to both adapters
        # unchanged. Recorded as a D-17 finding.
        provider = OllamaProvider(base_url=profile.base_url, **dict(profile.options))
        self._model = OllamaModel(profile.model_id, provider=provider)
        self._profile = profile
        self._hooks = self._tracer.as_capability()
        self._agent_plain = Agent(self._model, capabilities=[self._hooks])
        self._recorder.record_run_start(f"load_profile:{profile.name}")
        return ModelHandle(
            profile_name=profile.name,
            provider=profile.provider,
            model_id=profile.model_id,
            loaded=self._model is not None,
        )

    # -- 5. MCP ----------------------------------------------------------------------
    async def attach_mcp(self, spec: McpServerSpec) -> tuple[ToolSpec, ...]:
        # An explicit StdioTransport rather than the documented `MCPToolset("server.py")`
        # shortcut: the shortcut lets FastMCP guess an interpreter, and this spike must run
        # under `spike/bakeoff/.venv` specifically. It also maps 1:1 onto McpServerSpec.
        transport = StdioTransport(command=spec.command, args=list(spec.args))
        self._toolset = MCPToolset(transport)
        await self._stack.enter_async_context(self._toolset)
        tools = await self._toolset.list_tools()
        self._agent_tools = Agent(
            self._model, toolsets=[self._toolset], capabilities=[self._hooks]
        )
        return tuple(_tool_spec_of(tool) for tool in tools)

    # -- 2. streaming ----------------------------------------------------------------
    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield text deltas; read usage only once the stream is closed (Pitfall 8)."""
        aggregator = UsageAggregator()
        self.stream_chunk_usages = []
        async with self._agent_plain.run_stream(prompt) as result:
            async for delta in result.stream_text(delta=True):
                # No per-delta usage is exposed at all on this API, so every chunk is a
                # None by construction rather than by timing — see the results write-up.
                aggregator.add_chunk(None)
                self.stream_chunk_usages.append(None)
                if delta:
                    yield delta
            # `.usage` is a PROPERTY on both StreamedRunResult and AgentRunResult in
            # 2.13.0 — not the `usage()` method the v1-era snippets call.
            raw_usage = getattr(result, "usage", None)
        aggregator.finish(
            _usage_from_run_usage(raw_usage, "run_stream.usage()")
            or self._tracer.last_response_usage
        )
        self.stream_usage = aggregator.usage

    # -- 3. one tool-call round trip --------------------------------------------------
    async def call_tool(self, prompt: str) -> ToolRoundTrip:
        result = await self._agent_tools.run(prompt)
        raw_usage = getattr(result, "usage", None)
        # The hooks are the tracing layer, so the round trip is read back out of them —
        # the same discipline the LangChain side uses. SPIKE-06 is a question about the
        # tracing layer, and evidence assembled outside it would answer a different one.
        return ToolRoundTrip(
            prompt=prompt,
            final_text=str(getattr(result, "output", "") or ""),
            invocations=tuple(self._recorder.tool_invocations),
            results=tuple(self._recorder.tool_results),
            usage=_usage_from_run_usage(raw_usage, "run().usage()"),
        )

    # -- 4. tracing ------------------------------------------------------------------
    def trace_events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._recorder.events)

    @property
    def recorder(self) -> TraceRecorder:
        return self._recorder

    async def aclose(self) -> None:
        await self._stack.aclose()
        self._toolset = None
        self._agent_plain = None
        self._agent_tools = None
        self._model = None


# ======================================================================================
# Live probe — deliberately the same shape as the LangChain one
# ======================================================================================

PROFILE = ModelProfile(
    name="local-capable",
    provider="ollama",
    model_id="qwen3.5:9b",
    # NOT the same string the LangChain side needs (which took base_url=None and defaulted
    # correctly). See load_profile.
    base_url="http://127.0.0.1:11434/v1",
)

MCP_SPEC = McpServerSpec(
    name="probe",
    command=sys.executable,
    args=("spike/bakeoff/mcp_server/server.py",),
)

# "Reply with exactly the words: X" was the original prompt and it was a bad one: the
# model overthinks literal-compliance instructions, and its reasoning then collides with
# Ollama's default 4096-token context. Measured truncation at that ceiling on BOTH routes
# (native /api/chat 1/3, OpenAI-compat 2/4), so it is a daemon+model property, not a
# framework one. A plain greeting reasons for 285-598 tokens and completed 3/3.
STREAM_PROMPT = "Say hello."
TOOL_PROMPT = "What is the current status of the kitchen? Use the room_status tool."


async def run_probe() -> dict[str, Any]:
    started = time.perf_counter()
    adapter = PydanticAIAdapter()
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
        {
            "name": s.name,
            "description": s.description,
            "arg_keys": sorted(s.input_schema.get("properties", {})),
        }
        for s in specs
    ]

    t0 = time.perf_counter()
    chunks: list[str] = []
    # `qwen3.5:9b` is a thinking model at temperature 1, and Ollama's default num_ctx is
    # 4096 while the model itself supports 262144. Reasoning length for this five-word
    # answer was measured at 406 / 2937 / 4075 tokens across three identical calls, so the
    # run self-truncates at the context ceiling maybe two times in five. That is a property
    # of the model and the daemon, NOT of either framework — but Pydantic AI *raises*
    # UnexpectedModelBehavior where LangChain silently returns the short text, so it is
    # measured here rather than tuned away. Attempts and truncations are reported.
    attempts = 0
    truncations: list[str] = []
    while attempts < 4:
        attempts += 1
        chunks = []
        try:
            async for token in adapter.stream(STREAM_PROMPT):
                chunks.append(token)
            break
        except UnexpectedModelBehavior as exc:
            truncations.append(str(exc)[:200])
    evidence["stream"] = {
        "seconds": round(time.perf_counter() - t0, 2),
        "yielded_chunks": len(chunks),
        "text": "".join(chunks).strip()[:200],
        "chunk_usages_populated": sum(
            1 for u in adapter.stream_chunk_usages if u is not None and u.is_populated
        ),
        "chunk_usages_total": len(adapter.stream_chunk_usages),
        "attempts": attempts,
        "context_window_truncations": truncations,
    }
    evidence["spike_05"] = {
        "streaming_usage_after_aggregation": _usage_dict(adapter.stream_usage),
        "after_model_request_raw_usage": repr(adapter._tracer.raw_response_usage)[:300],
        "naive_first_chunk_read": _usage_dict(
            adapter.stream_chunk_usages[0] if adapter.stream_chunk_usages else None
        ),
    }

    t1 = time.perf_counter()
    trip = await adapter.call_tool(TOOL_PROMPT)
    tracer = adapter._tracer
    recorder = adapter.recorder
    evidence["spike_06_via_hooks"] = {
        "seconds": round(time.perf_counter() - t1, 2),
        "tool_start_args": [dict(i.args) for i in recorder.tool_invocations],
        "tool_result_types": [
            f"{type(o).__module__}.{type(o).__name__}" for o in tracer.raw_tool_results
        ],
        "correct_capture_structured_content": [
            dict(r.structured_content) if r.structured_content else None
            for r in recorder.tool_results
        ],
        "naive_capture_structured_content": [
            naive_tool_output("room_status", o).structured_content for o in tracer.raw_tool_results
        ],
        # The assertion that can fail: byte-for-byte against the server's frozen fixture.
        "structured_content_matches_server_fixture": [
            structured_content_matches(r, EXPECTED_STRUCTURED) for r in recorder.tool_results
        ],
        "naive_capture_matches_server_fixture": [
            structured_content_matches(
                naive_tool_output("room_status", o), EXPECTED_STRUCTURED
            )
            for o in tracer.raw_tool_results
        ],
        "raw_result_repr": [repr(o)[:400] for o in tracer.raw_tool_results],
        "final_text": trip.final_text.strip()[:300],
        "final_usage": _usage_dict(trip.usage),
    }
    evidence["start_hooks_that_fired"] = sorted(set(h for h in recorder.prompt_hooks if h))
    evidence["registered_hooks"] = list(registered_hook_names(adapter._hooks))
    evidence["trace_summary"] = recorder.summary()
    evidence["trace_kinds"] = sorted({e.kind for e in recorder.events})
    evidence["hook_gaps"] = list(trace_handler_gaps())
    evidence["telemetry"] = _telemetry_state(adapter)
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


def _telemetry_state(adapter: PydanticAIAdapter) -> dict[str, Any]:
    """Asserted, not assumed (PRIV-02). Instrumentation is the OTel/Logfire path — off."""
    import importlib.util

    capabilities = [type(c).__name__ for c in ([adapter._hooks] if adapter._hooks else [])]
    return {
        "capabilities_attached": capabilities,
        "instrumentation_enabled": any(c == "Instrumentation" for c in capabilities),
        "real_logfire_installed": importlib.util.find_spec("logfire") is not None,
    }


def main() -> None:
    evidence = asyncio.run(run_probe())
    print(json.dumps(evidence, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
