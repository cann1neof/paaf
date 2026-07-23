"""The PAAF-typed port the bake-off implements twice (D-15/D-16).

THROWAWAY. Neither this code nor these signatures carry forward (D-18). Phase 3 designs
its port fresh from the findings. The only thing that survives this file is what it
*measures*.

Why a port at all
-----------------
SPIKE-07 asks one question — *which framework is easier to hide behind a port* — and that
question is unanswerable unless there is a port to hide behind. D-16 fixes the surface at
five things:

1. load a model from a **named profile**   -> :meth:`AgentPort.load_profile`
2. **stream** tokens                        -> :meth:`AgentPort.stream`
3. one **tool-call round trip**             -> :meth:`AgentPort.call_tool`
4. **callback-driven tracing**              -> :meth:`AgentPort.trace_events`
5. an **MCP server**                        -> :meth:`AgentPort.attach_mcp`

SPIKE-05 (are Ollama token counts non-``None``?) and SPIKE-06 (are MCP tool args *and*
structured results visible?) are answered by reading the trace this port emits — they run
*through* the port, not beside it.

Deliberate constraint: **this module imports nothing but the standard library.** No
langchain, no langgraph, no pydantic_ai, no mcp. If it needed one of them the whole
exercise would already have failed, and :func:`framework_types_in_signature` turns that
from a convention into a test.

The two shared helpers are not a convenience
--------------------------------------------
:class:`UsageAggregator` and :func:`split_tool_output` are used by **both** adapters on
purpose. RESEARCH Pitfall 8 and Pitfall 9 each describe a way to produce a *false negative*
— reading token usage from a streamed chunk, and stringifying a tool result so its
structured half disappears. If each adapter re-implemented those, a difference in the
answers would be ambiguous between "the framework hid it" and "this adapter's handler was
buggy". Sharing them means a ``None`` is attributable to the framework.

Their deliberately-wrong twins (:func:`naive_stream_usage`, :func:`naive_tool_output`) live
here too, as first-class negative controls: a test that cannot demonstrate the wrong answer
cannot claim credit for the right one (01-04's rule).
"""

from __future__ import annotations

import inspect
import time
import typing
from collections.abc import AsyncIterator, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

__all__ = [
    "AgentPort",
    "ConformanceReport",
    "McpServerSpec",
    "ModelHandle",
    "ModelProfile",
    "PORT_METHODS",
    "REQUIRED_LANGCHAIN_HOOKS",
    "ToolInvocation",
    "ToolResult",
    "ToolRoundTrip",
    "ToolSpec",
    "TokenUsage",
    "TraceEvent",
    "TraceRecorder",
    "UsageAggregator",
    "UsageReadTooEarly",
    "conformance_report",
    "framework_types_in_signature",
    "hooks_defined_by",
    "missing_hooks",
    "naive_stream_usage",
    "naive_tool_output",
    "split_tool_output",
    "structured_content_matches",
]


# ======================================================================================
# PAAF types — the vocabulary the port speaks. No framework object may appear here.
# ======================================================================================


@dataclass(frozen=True)
class ModelProfile:
    """A *named* model profile — the user-facing concept, not a framework model object.

    This is the shape a YAML profile would deserialize into. ``name`` is what a user
    types; everything else is how it resolves.
    """

    name: str
    provider: str
    model_id: str
    base_url: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelHandle:
    """What :meth:`AgentPort.load_profile` returns.

    Deliberately inert: it describes *that* a model loaded, never *which framework object*
    is holding it. The framework instance stays private to the adapter. If this dataclass
    ever grew a field typed as a framework class, the port would have stopped being a port.
    """

    profile_name: str
    provider: str
    model_id: str
    loaded: bool


@dataclass(frozen=True)
class McpServerSpec:
    """How to reach a local stdio MCP server."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    transport: Literal["stdio"] = "stdio"


@dataclass(frozen=True)
class ToolSpec:
    """A tool as the port describes it — name, description, JSON-schema arguments.

    Both adapters must hand back *these*, not their framework's tool class. Converting a
    framework tool into a ``ToolSpec`` is exactly the translation work D-17 wants counted.
    """

    name: str
    description: str
    input_schema: Mapping[str, Any]


@dataclass(frozen=True)
class TokenUsage:
    """Token counts. SPIKE-05 is the question of whether these are ``None``.

    Every field is nullable on purpose: a partially-populated usage record is a real
    outcome and must be representable, otherwise the measurement would be forced into a
    yes/no it does not deserve.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    source: str = ""

    @property
    def is_populated(self) -> bool:
        """True when input *and* output counts are both present.

        Not ``any(...)``: ``langchain_ollama``'s
        ``_get_usage_metadata_from_generation_info`` itself requires **both**
        ``prompt_eval_count`` and ``eval_count`` before it emits anything, so a
        half-populated record would mean something different from "token counts work".
        """
        return self.input_tokens is not None and self.output_tokens is not None


@dataclass(frozen=True)
class ToolInvocation:
    """The arguments half of SPIKE-06."""

    name: str
    args: Mapping[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """The results half of SPIKE-06 — and the reason it is two fields, not one.

    ``content`` is the text a model sees. ``artifact`` is the **structured** result. MCP
    tools converted by ``langchain_mcp_adapters`` are ``StructuredTool``s with
    ``response_format="content_and_artifact"``; their coroutine returns a *tuple* whose
    second element carries ``structured_content``. A trace that records only ``str(output)``
    keeps the first half and silently loses the second — and would report "MCP results are
    not visible through callbacks", overturning the framework choice on a handler bug
    (RESEARCH Pitfall 9).

    ``artifact_present`` is separate from ``artifact is not None`` so that "the tool
    returned a structured half that happened to be empty" stays distinguishable from
    "there was no structured half".
    """

    name: str
    content: Any
    artifact: Any = None
    artifact_present: bool = False
    structured_content: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ToolRoundTrip:
    """One complete prompt -> tool call -> tool result -> final answer cycle."""

    prompt: str
    final_text: str
    invocations: tuple[ToolInvocation, ...] = ()
    results: tuple[ToolResult, ...] = ()
    usage: TokenUsage | None = None


TraceKind = Literal[
    "run_start",
    "prompt",
    "token",
    "usage",
    "tool_start",
    "tool_end",
    "run_end",
    "error",
]


@dataclass(frozen=True)
class TraceEvent:
    """One in-process trace record. Never leaves the process; no exporter, ever (PRIV-02)."""

    kind: TraceKind
    at: float
    run_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


# ======================================================================================
# Pitfall 8 — token usage must be read AFTER the stream is aggregated
# ======================================================================================


class UsageReadTooEarly(RuntimeError):
    """Raised when :attr:`UsageAggregator.usage` is read before the stream finished.

    Loud by design. Ollama sends ``prompt_eval_count``/``eval_count`` only on the final
    ``done: True`` chunk, so every intermediate chunk carries ``usage_metadata=None``. A
    handler that reads early gets ``None`` and reports SPIKE-05 negative — a measurement
    error that would overturn the framework recommendation. Making the early read *raise*
    means the mistake cannot be made quietly.
    """


class UsageAggregator:
    """Accumulates per-chunk usage and refuses to answer until the stream is closed."""

    def __init__(self) -> None:
        self._chunks: list[TokenUsage | None] = []
        self._final: TokenUsage | None = None
        self._finished = False

    def add_chunk(self, usage: TokenUsage | None) -> None:
        if self._finished:  # pragma: no cover - guards misuse, not a measured path
            raise RuntimeError("add_chunk() after finish()")
        self._chunks.append(usage)

    def finish(self, final_usage: TokenUsage | None = None) -> None:
        """Close the stream. ``final_usage`` is what ``on_llm_end`` saw, when available."""
        self._finished = True
        if final_usage is not None and final_usage.is_populated:
            self._final = final_usage
            return
        for usage in reversed(self._chunks):
            if usage is not None and usage.is_populated:
                self._final = usage
                return
        self._final = final_usage

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def usage(self) -> TokenUsage | None:
        if not self._finished:
            raise UsageReadTooEarly(
                f"usage read after {len(self._chunks)} chunk(s) but before finish(); "
                "Ollama emits token counts only on the final chunk"
            )
        return self._final

    @property
    def first_chunk_usage(self) -> TokenUsage | None:
        """What a naive reader would have seen. Kept for the negative control, not for use."""
        return self._chunks[0] if self._chunks else None


def naive_stream_usage(chunks: Sequence[TokenUsage | None]) -> TokenUsage | None:
    """The WRONG reader Pitfall 8 describes: take usage off the first streamed chunk.

    Exists so a test can *demonstrate* the false negative rather than assert its absence.
    """
    return chunks[0] if chunks else None


# ======================================================================================
# Pitfall 9 — the artifact half must survive the port boundary
# ======================================================================================

_STRUCTURED_KEYS = ("structured_content", "structuredContent")


def _structured_of(artifact: Any) -> Mapping[str, Any] | None:
    """Pull ``structured_content`` out of whatever shape the artifact arrived in."""
    if artifact is None:
        return None
    if isinstance(artifact, Mapping):
        for key in _STRUCTURED_KEYS:
            if key in artifact:
                value = artifact[key]
                return value if isinstance(value, Mapping) else {"value": value}
        return artifact
    for key in _STRUCTURED_KEYS:
        value = getattr(artifact, key, None)
        if value is not None:
            return value if isinstance(value, Mapping) else {"value": value}
    return None


def split_tool_output(name: str, output: Any) -> ToolResult:
    """Split a framework tool output into the PAAF content/artifact halves, losing nothing.

    Handles, in order:

    * an object exposing ``.artifact`` (a langchain ``ToolMessage`` from a
      ``content_and_artifact`` tool),
    * a two-element tuple ``(content, artifact)`` (what such a tool's coroutine *returns*,
      before langchain wraps it),
    * a mapping already carrying ``structured_content``/``structuredContent``
      (the Pydantic AI / raw-MCP shape),
    * anything else -> content only, and ``artifact_present=False`` says so honestly.

    Never calls ``str()`` on the output. That single call is the whole of Pitfall 9.
    """
    if hasattr(output, "artifact"):
        artifact = getattr(output, "artifact")
        content = getattr(output, "content", output)
        return ToolResult(
            name=name,
            content=content,
            artifact=artifact,
            artifact_present=artifact is not None,
            structured_content=_structured_of(artifact),
        )

    if isinstance(output, tuple) and len(output) == 2:
        content, artifact = output
        return ToolResult(
            name=name,
            content=content,
            artifact=artifact,
            artifact_present=artifact is not None,
            structured_content=_structured_of(artifact),
        )

    if isinstance(output, Mapping) and any(k in output for k in _STRUCTURED_KEYS):
        structured = _structured_of(output)
        return ToolResult(
            name=name,
            content=output.get("content", output),
            artifact=output,
            artifact_present=True,
            structured_content=structured,
        )

    if isinstance(output, Mapping):
        # A bare mapping with no wrapper key: the structured payload IS the result.
        #
        # This branch exists because the first version of this function did not have it,
        # and it produced a false negative for the Pydantic AI adapter — whose
        # `after_tool_execute` hook hands over the MCP server's `structuredContent` as a
        # plain `dict`, with no content/artifact split at all. Reported as
        # `artifact_present: false`, which reads as "the structured half was lost" when the
        # truth is the opposite: nothing was ever wrapped, so nothing could be lost.
        #
        # Getting this wrong would have rejected a framework on a defect in the
        # instrument — which is the exact failure this whole plan exists to prevent, so it
        # is recorded here rather than quietly patched.
        return ToolResult(
            name=name,
            content=output,
            artifact=output,
            artifact_present=True,
            structured_content=output,
        )

    return ToolResult(name=name, content=output, artifact=None, artifact_present=False)


def naive_tool_output(name: str, output: Any) -> ToolResult:
    """The WRONG capture Pitfall 9 describes: stringify and drop the structured half."""
    return ToolResult(name=name, content=str(output), artifact=None, artifact_present=False)


def structured_content_matches(result: ToolResult, expected: Mapping[str, Any]) -> bool:
    """Does the captured structured payload equal what the MCP server is known to have sent?

    ``artifact_present`` alone is too weak to carry SPIKE-06 once bare mappings count as
    structured — every dict would satisfy it, and the requirement would be met by any tool
    that returned anything. This compares against the server's frozen fixture instead, so
    the check fails if a single field was dropped, renamed, or stringified. It is also the
    one assertion that reads identically across both frameworks despite their different
    result shapes, which is what makes the two answers comparable.
    """
    if result.structured_content is None:
        return False
    return dict(result.structured_content) == dict(expected)


# ======================================================================================
# Trace recorder — framework-free sink both adapters drain into
# ======================================================================================


class TraceRecorder:
    """In-process trace sink. No exporter, no network, no OTel, no LangSmith (PRIV-02)."""

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        self.events: list[TraceEvent] = []

    # -- writes ---------------------------------------------------------------------
    def _add(self, kind: TraceKind, run_id: str | None, **payload: Any) -> TraceEvent:
        event = TraceEvent(kind=kind, at=self._clock(), run_id=run_id, payload=payload)
        self.events.append(event)
        return event

    def record_run_start(self, label: str, *, run_id: str | None = None) -> None:
        self._add("run_start", run_id, label=label)

    def record_prompt(
        self,
        messages: Any,
        *,
        run_id: str | None = None,
        model_choice: str | None = None,
        hook: str = "",
    ) -> None:
        self._add("prompt", run_id, messages=messages, model_choice=model_choice, hook=hook)

    def record_token(self, token: str, *, run_id: str | None = None) -> None:
        self._add("token", run_id, token=token)

    def record_usage(self, usage: TokenUsage | None, *, run_id: str | None = None) -> None:
        self._add("usage", run_id, usage=usage)

    def record_tool_start(self, invocation: ToolInvocation, *, run_id: str | None = None) -> None:
        self._add("tool_start", run_id, invocation=invocation)

    def record_tool_end(self, result: ToolResult, *, run_id: str | None = None) -> None:
        self._add("tool_end", run_id, result=result)

    def record_run_end(self, label: str, *, run_id: str | None = None) -> None:
        self._add("run_end", run_id, label=label)

    def record_error(self, message: str, *, run_id: str | None = None) -> None:
        self._add("error", run_id, message=message)

    # -- reads ----------------------------------------------------------------------
    def of_kind(self, kind: TraceKind) -> tuple[TraceEvent, ...]:
        return tuple(e for e in self.events if e.kind == kind)

    @property
    def prompts(self) -> tuple[Any, ...]:
        return tuple(e.payload["messages"] for e in self.of_kind("prompt"))

    @property
    def prompt_hooks(self) -> tuple[str, ...]:
        """Which callback fired for each prompt — the evidence for the both-hooks rule."""
        return tuple(str(e.payload.get("hook", "")) for e in self.of_kind("prompt"))

    @property
    def tokens(self) -> tuple[str, ...]:
        return tuple(str(e.payload["token"]) for e in self.of_kind("token"))

    @property
    def usages(self) -> tuple[TokenUsage | None, ...]:
        return tuple(e.payload["usage"] for e in self.of_kind("usage"))

    @property
    def tool_invocations(self) -> tuple[ToolInvocation, ...]:
        return tuple(e.payload["invocation"] for e in self.of_kind("tool_start"))

    @property
    def tool_results(self) -> tuple[ToolResult, ...]:
        return tuple(e.payload["result"] for e in self.of_kind("tool_end"))

    def summary(self) -> dict[str, Any]:
        populated = [u for u in self.usages if u is not None and u.is_populated]
        with_artifact = [r for r in self.tool_results if r.artifact_present]
        return {
            "events": len(self.events),
            "prompts": len(self.prompts),
            "prompt_hooks": sorted(set(h for h in self.prompt_hooks if h)),
            "tokens": len(self.tokens),
            "usage_records": len(self.usages),
            "usage_records_populated": len(populated),
            "tool_invocations": len(self.tool_invocations),
            "tool_results": len(self.tool_results),
            "tool_results_with_artifact": len(with_artifact),
        }


# ======================================================================================
# Callback-hook conformance (the "implement BOTH" rule)
# ======================================================================================

#: RESEARCH §Anti-Patterns: CHAT models fire ``on_chat_model_start``, NOT ``on_llm_start``.
#: A handler implementing only the latter records nothing at all for a chat model — and
#: SPIKE-05/06 would report "prompts are not visible" against a handler that never fired.
REQUIRED_LANGCHAIN_HOOKS: tuple[str, ...] = (
    "on_chat_model_start",
    "on_llm_start",
    "on_llm_new_token",
    "on_llm_end",
    "on_tool_start",
    "on_tool_end",
)

#: Import roots that mark a class as belonging to a framework rather than to this spike.
FRAMEWORK_ROOTS: frozenset[str] = frozenset(
    {
        "langchain",
        "langchain_core",
        "langchain_ollama",
        "langchain_mcp_adapters",
        "langgraph",
        "pydantic_ai",
        "pydantic_graph",
        "mcp",
        "fastmcp",
        "openai",
        "ollama",
    }
)


def hooks_defined_by(cls: type, *, framework_roots: Iterable[str] = FRAMEWORK_ROOTS) -> set[str]:
    """Names the class (or its non-framework bases) defines *itself*.

    Walking the MRO and stopping at the first framework class is the point: every
    ``AsyncCallbackHandler`` subclass *inherits* all six hooks as no-ops, so
    ``hasattr(handler, "on_chat_model_start")`` is true even for a handler that overrides
    none of them. An inherited no-op records nothing. Presence is not implementation.
    """
    roots = set(framework_roots)
    defined: set[str] = set()
    for klass in cls.__mro__:
        if klass is object:
            continue
        root = (klass.__module__ or "").split(".")[0]
        if root in roots:
            break
        defined |= {name for name in vars(klass) if not name.startswith("__")}
    return defined


def missing_hooks(
    cls: type,
    required: Sequence[str] = REQUIRED_LANGCHAIN_HOOKS,
    *,
    framework_roots: Iterable[str] = FRAMEWORK_ROOTS,
) -> tuple[str, ...]:
    """Which required hooks the class does not override itself."""
    defined = hooks_defined_by(cls, framework_roots=framework_roots)
    return tuple(name for name in required if name not in defined)


# ======================================================================================
# The port
# ======================================================================================


@runtime_checkable
class AgentPort(Protocol):
    """The D-16 surface, implemented once over LangChain/LangGraph and once over Pydantic AI.

    These signatures do **not** survive to Phase 3 (D-18). They exist to be implemented
    twice so the difficulty of doing so is measurable.
    """

    #: Short adapter label, e.g. ``"langchain"`` / ``"pydantic_ai"``.
    name: str

    async def load_profile(self, profile: ModelProfile) -> ModelHandle:
        """Resolve a *named* profile into a loaded model. Returns PAAF types only."""
        ...

    async def attach_mcp(self, spec: McpServerSpec) -> tuple[ToolSpec, ...]:
        """Connect a local stdio MCP server and describe its tools as :class:`ToolSpec`."""
        ...

    def stream(self, prompt: str) -> AsyncIterator[str]:
        """Stream response tokens. An async generator: no framework chunk type escapes."""
        ...

    async def call_tool(self, prompt: str) -> ToolRoundTrip:
        """Run exactly one tool-call round trip against the attached MCP server."""
        ...

    def trace_events(self) -> tuple[TraceEvent, ...]:
        """Everything the adapter's callbacks/hooks captured, as PAAF trace records."""
        ...

    async def aclose(self) -> None:
        """Release the MCP subprocess and any framework client."""
        ...


PORT_METHODS: tuple[str, ...] = (
    "load_profile",
    "attach_mcp",
    "stream",
    "call_tool",
    "trace_events",
    "aclose",
)


def _param_shape(func: Any) -> tuple[tuple[str, str], ...]:
    """(name, kind) for every parameter except ``self``. Annotations deliberately ignored."""
    signature = inspect.signature(func)
    return tuple(
        (name, param.kind.name)
        for name, param in signature.parameters.items()
        if name != "self"
    )


def _walk_types(annotation: Any) -> Iterable[Any]:
    yield annotation
    for arg in typing.get_args(annotation):
        yield from _walk_types(arg)


def framework_types_in_signature(func: Any) -> tuple[str, ...]:
    """Framework classes reachable from a method's parameter or return annotations.

    Resolves annotations to real objects (rather than substring-matching their text) so
    that ``McpServerSpec`` — a PAAF dataclass whose *name* contains "Mcp" — is not
    mistaken for a leak, and so that an alias like ``from langchain_core.messages import
    BaseMessage as Msg`` cannot hide one.
    """
    try:
        hints = inspect.get_annotations(func, eval_str=True)
    except Exception:  # pragma: no cover - unresolvable annotation is itself reported
        return ("<unresolvable-annotations>",)

    leaked: list[str] = []
    for annotation in hints.values():
        for candidate in _walk_types(annotation):
            module = getattr(candidate, "__module__", "") or ""
            root = module.split(".")[0]
            if root in FRAMEWORK_ROOTS:
                leaked.append(f"{module}.{getattr(candidate, '__qualname__', candidate)}")
    return tuple(sorted(set(leaked)))


@dataclass(frozen=True)
class ConformanceReport:
    """Why a candidate does or does not satisfy the port."""

    candidate: str
    missing_methods: tuple[str, ...] = ()
    signature_mismatches: tuple[str, ...] = ()
    leaked_types: tuple[str, ...] = ()
    not_async: tuple[str, ...] = ()

    @property
    def conforms(self) -> bool:
        return not (
            self.missing_methods
            or self.signature_mismatches
            or self.leaked_types
            or self.not_async
        )

    def explain(self) -> str:
        if self.conforms:
            return f"{self.candidate}: conforms"
        parts = [f"{self.candidate}: DOES NOT conform"]
        if self.missing_methods:
            parts.append(f"  missing methods: {list(self.missing_methods)}")
        if self.signature_mismatches:
            parts.append(f"  signature mismatches: {list(self.signature_mismatches)}")
        if self.leaked_types:
            parts.append(f"  framework types in the public signature: {list(self.leaked_types)}")
        if self.not_async:
            parts.append(f"  wrong async shape: {list(self.not_async)}")
        return "\n".join(parts)


#: Methods that must be coroutine functions, and the one that must be an async generator.
_MUST_BE_COROUTINE = ("load_profile", "attach_mcp", "call_tool", "aclose")
_MUST_BE_ASYNC_GEN = ("stream",)


def conformance_report(candidate: Any, *, label: str | None = None) -> ConformanceReport:
    """Structural conformance to :class:`AgentPort`, stronger than ``isinstance``.

    ``isinstance(x, AgentPort)`` checks only that the *names* exist — an adapter whose
    ``call_tool`` took no arguments, returned a framework object and was not even async
    would still pass it. That is a check that cannot fail in the ways that matter, and
    01-04 established that a check which cannot fail is not a check. So this compares
    parameter names and kinds against the Protocol, requires the right async shape, and
    rejects any framework type reachable from a public annotation.
    """
    name = label or getattr(candidate, "name", None) or type(candidate).__name__
    missing: list[str] = []
    mismatches: list[str] = []
    leaked: list[str] = []
    not_async: list[str] = []

    for method_name in PORT_METHODS:
        expected = getattr(AgentPort, method_name)
        actual = getattr(candidate, method_name, None)
        if actual is None:
            missing.append(method_name)
            continue

        expected_shape = _param_shape(expected)
        actual_shape = _param_shape(actual)
        if expected_shape != actual_shape:
            mismatches.append(f"{method_name}: expected {expected_shape}, got {actual_shape}")

        leaked.extend(framework_types_in_signature(actual))

        unwrapped = inspect.unwrap(actual)
        if method_name in _MUST_BE_COROUTINE and not inspect.iscoroutinefunction(unwrapped):
            not_async.append(f"{method_name}: expected a coroutine function")
        if method_name in _MUST_BE_ASYNC_GEN and not inspect.isasyncgenfunction(unwrapped):
            not_async.append(f"{method_name}: expected an async generator function")

    if not hasattr(candidate, "name"):
        missing.append("name")

    return ConformanceReport(
        candidate=str(name),
        missing_methods=tuple(missing),
        signature_mismatches=tuple(mismatches),
        leaked_types=tuple(sorted(set(leaked))),
        not_async=tuple(not_async),
    )
