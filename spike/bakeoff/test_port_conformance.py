"""SPIKE-07: both adapters must satisfy the SAME port, structurally and honestly.

This is the test that makes "implemented twice" mean something. Without it, two modules
called ``adapter_*`` could diverge in signature, return framework objects, or forget to be
async, and the LOC comparison in ``raw/bakeoff-results.md`` would be comparing two
different jobs.

Adapters are imported **inside** the test bodies, never at module scope. A module-level
import of a not-yet-written adapter is a *collection* error, which pytest treats as fatal
for the whole run — that is 01-04's deviation 3 in a new disguise, and it would take the
39 tool-call-gate tests down with it.

Note that ``isinstance(x, AgentPort)`` is deliberately not the check. A ``runtime_checkable``
Protocol tests only that the names exist, so an adapter whose ``call_tool`` took no
arguments, was not async, and returned a raw ``AIMessage`` would still pass it. That is a
check that cannot fail in the ways that matter — the vacuity trap 01-04 hit with the
no-cloud assertion. ``conformance_report`` compares parameter shapes, requires the right
async form, and rejects framework types reachable from any public annotation.
"""

from __future__ import annotations

import importlib
from typing import Any, AsyncIterator

import pytest

from bakeoff.port import (
    PORT_METHODS,
    AgentPort,
    McpServerSpec,
    ModelHandle,
    ModelProfile,
    ToolRoundTrip,
    ToolSpec,
    TraceEvent,
    conformance_report,
    framework_types_in_signature,
)

#: id -> (module, class). Both are expected. Under the D-19 stopping rule an adapter may be
#: left incomplete — but that must be a *recorded* decision with a red test and a written
#: reason, never a quiet absence.
EXPECTED_ADAPTERS: tuple[tuple[str, str, str], ...] = (
    ("langchain", "bakeoff.adapter_langchain", "LangChainAdapter"),
    ("pydantic_ai", "bakeoff.adapter_pydantic_ai", "PydanticAIAdapter"),
)


def _load(module_name: str, class_name: str) -> type:
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:  # pragma: no cover - only on an unbuilt/abandoned adapter
        pytest.fail(
            f"{module_name} could not be imported: {exc}. Under D-19 an unbuilt adapter is "
            "a legitimate outcome, but it must be recorded in raw/bakeoff-results.md with "
            "the reason — and 'API friction from an unfamiliar v2 surface' is a materially "
            "different finding from 'the framework resists porting'."
        )
    return getattr(module, class_name)


# --------------------------------------------------------------------------------------
# Controls: prove the checker can fail, before trusting it to say the adapters pass
# --------------------------------------------------------------------------------------


class _GoodAdapter:
    """A minimal but genuinely conforming implementation."""

    name = "control_good"

    async def load_profile(self, profile: ModelProfile) -> ModelHandle:
        return ModelHandle(profile.name, profile.provider, profile.model_id, True)

    async def attach_mcp(self, spec: McpServerSpec) -> tuple[ToolSpec, ...]:
        return ()

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield prompt

    async def call_tool(self, prompt: str) -> ToolRoundTrip:
        return ToolRoundTrip(prompt=prompt, final_text="")

    def trace_events(self) -> tuple[TraceEvent, ...]:
        return ()

    async def aclose(self) -> None: ...


class _MissingMethodAdapter(_GoodAdapter):
    name = "control_missing"
    call_tool = None  # type: ignore[assignment]


class _WrongSignatureAdapter(_GoodAdapter):
    name = "control_wrong_signature"

    async def call_tool(self) -> ToolRoundTrip:  # type: ignore[override]
        return ToolRoundTrip(prompt="", final_text="")


class _NotAsyncAdapter(_GoodAdapter):
    name = "control_not_async"

    def call_tool(self, prompt: str) -> ToolRoundTrip:  # type: ignore[override]
        return ToolRoundTrip(prompt=prompt, final_text="")


class _SyncStreamAdapter(_GoodAdapter):
    name = "control_sync_stream"

    def stream(self, prompt: str):  # type: ignore[override]
        return iter([prompt])


def test_the_control_adapter_conforms():
    report = conformance_report(_GoodAdapter)
    assert report.conforms, report.explain()


@pytest.mark.parametrize(
    ("candidate", "attribute"),
    [
        (_MissingMethodAdapter, "missing_methods"),
        (_WrongSignatureAdapter, "signature_mismatches"),
        (_NotAsyncAdapter, "not_async"),
        (_SyncStreamAdapter, "not_async"),
    ],
    ids=["missing-method", "wrong-signature", "sync-call-tool", "sync-stream"],
)
def test_the_checker_rejects_each_way_of_not_conforming(candidate: type, attribute: str):
    report = conformance_report(candidate)
    assert not report.conforms, report.explain()
    assert getattr(report, attribute), f"expected a {attribute} finding: {report.explain()}"


def test_isinstance_alone_would_have_passed_a_broken_adapter():
    """Why this file does not use ``isinstance``. The trap, made explicit."""
    assert isinstance(_NotAsyncAdapter(), AgentPort)
    assert isinstance(_WrongSignatureAdapter(), AgentPort)
    assert not conformance_report(_NotAsyncAdapter).conforms
    assert not conformance_report(_WrongSignatureAdapter).conforms


def test_the_leak_detector_finds_a_real_framework_type():
    """A control for ``framework_types_in_signature``, using a genuine framework class.

    Substring matching on the annotation *text* would both miss an aliased import and
    false-positive on ``McpServerSpec``. Resolving to objects and reading ``__module__``
    does neither — but only a live framework class can demonstrate that.
    """
    from langchain_core.messages import BaseMessage as Aliased

    def leaky(self, messages: list[Aliased]) -> None: ...

    def clean(self, spec: McpServerSpec) -> tuple[ToolSpec, ...]: ...

    leaked = framework_types_in_signature(leaky)
    assert leaked and any("langchain" in name for name in leaked)
    assert framework_types_in_signature(clean) == ()


# --------------------------------------------------------------------------------------
# The adapters themselves
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("adapter_id", "module_name", "class_name"),
    EXPECTED_ADAPTERS,
    ids=[a[0] for a in EXPECTED_ADAPTERS],
)
def test_adapter_conforms_to_the_port(adapter_id: str, module_name: str, class_name: str):
    adapter = _load(module_name, class_name)
    report = conformance_report(adapter, label=adapter_id)
    assert report.conforms, report.explain()


@pytest.mark.parametrize(
    ("adapter_id", "module_name", "class_name"),
    EXPECTED_ADAPTERS,
    ids=[a[0] for a in EXPECTED_ADAPTERS],
)
def test_no_framework_type_reaches_the_port_boundary(
    adapter_id: str, module_name: str, class_name: str
):
    """D-17's "how many framework types leak toward the boundary", as a test rather than a count.

    The interesting number is not this one (it should be zero for both) — it is how much
    private translation code each adapter needed to *keep* it zero. That is measured in
    ``raw/bakeoff-results.md``.
    """
    adapter = _load(module_name, class_name)
    leaks: dict[str, Any] = {}
    for method_name in PORT_METHODS:
        method = getattr(adapter, method_name, None)
        if method is None:
            continue
        found = framework_types_in_signature(method)
        if found:
            leaks[method_name] = found
    assert not leaks, f"{adapter_id} leaks framework types: {leaks}"


@pytest.mark.parametrize(
    ("adapter_id", "module_name", "class_name"),
    EXPECTED_ADAPTERS,
    ids=[a[0] for a in EXPECTED_ADAPTERS],
)
def test_adapter_declares_the_required_callback_hooks(
    adapter_id: str, module_name: str, class_name: str
):
    """Each adapter must expose its trace handler and that handler must fire on chat models.

    ``test_trace_handler.py`` proves the rule against doubles; this applies it to the real
    handler, which is where an inherited-no-op would actually cost a measurement.
    """
    module = importlib.import_module(module_name)
    _load(module_name, class_name)  # fail loudly and identically if the class is absent
    missing = module.trace_handler_gaps()
    assert missing == (), f"{adapter_id} trace handler does not implement: {list(missing)}"
