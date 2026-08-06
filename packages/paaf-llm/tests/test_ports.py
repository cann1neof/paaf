# SPDX-License-Identifier: Apache-2.0
"""MODEL-08: the port is PAAF-typed, framework-free, and shaped for Phase 4.

These tests pin the three properties that make ``ports.py`` a *port* rather than
a mirror of whatever agent framework happens to serve a turn:

1. the value types are frozen (a ``Message`` handed to an adapter cannot be
   mutated behind the caller's back),
2. every degraded trigger the fallback loop must classify has exactly one PAAF
   exception type carrying exactly one :class:`FallbackReason`, and
3. the module imports no agent framework at all — asserted against the source
   text, so the guard survives a future refactor that hides an import behind a
   helper.

**Phase-4 additions (MESH-01/02).** The mesh's tool vocabulary lives in a SECOND
protocol, :class:`ports.ToolCallingChatAdapter`, so ``ChatAdapter``'s own
definition is unchanged (D-02) — ``test_chat_adapter_is_a_two_method_protocol``
is the guard that keeps it that way, and it is a *negative* control: it fails the
moment somebody grows the Phase-3 port instead of extending it.
:class:`ports.UndeclaredPeer`'s two non-subclass assertions matter for the same
reason ``EngineError``'s do — a routing violation absorbed by the fallback loop
would print a confident, wrong explanation at a routing bug.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path

import paaf_llm
import pytest
from paaf_llm import ports


def test_message_is_a_frozen_value() -> None:
    msg = ports.Message("user", "hi")
    assert (msg.role, msg.content) == ("user", "hi")
    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.content = "tampered"  # type: ignore[misc]


def test_usage_defaults_to_unknown_counts() -> None:
    """A provider that reports no tokens is representable, not a crash (SPIKE-05)."""
    usage = ports.Usage()
    assert usage.prompt_tokens is None
    assert usage.completion_tokens is None
    assert ports.Usage(11, 22).completion_tokens == 22


def test_turn_result_handoff_defaults_to_none() -> None:
    """The handoff seam still defaults to None — a turn need not hand off (MESH-01)."""
    assert ports.TurnResult.__dataclass_fields__["handoff"].default is None
    result = ports.TurnResult(text="hello", served_by="local", usage=ports.Usage())
    assert result.handoff is None
    assert result.fallback_trail == []


def test_turn_result_handoff_is_typed_rather_than_any() -> None:
    """Phase 4 replaced the ``type HandoffRequest = Any`` placeholder with the payload.

    Asserted against the source text rather than ``get_type_hints`` because the
    annotation is a string under ``from __future__ import annotations``: an
    ``Any`` left behind here would resolve happily and say nothing.
    """
    source = inspect.getsource(ports)
    assert "type HandoffRequest = Any" not in source
    declaration = (
        source.split("class TurnResult")[1].split("handoff:")[1].split("\n")[0]
    )
    assert "Any" not in declaration
    assert ports.TurnResult.__dataclass_fields__["handoff"].type == (
        "HandoffRequest | None"
    )


def test_handoff_request_names_both_ends_and_is_frozen() -> None:
    """MESH-01: the accepted handoff rides back on the result as a value, not a string."""
    request = ports.HandoffRequest(from_agent="host", to_agent="chef")
    assert (request.from_agent, request.to_agent) == ("host", "chef")
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.to_agent = "admin"  # type: ignore[misc]


def test_tool_spec_is_a_frozen_value() -> None:
    """A ToolSpec crosses the port into adapter code — it must not be rewritable."""
    spec = ports.ToolSpec(name="transfer_to_chef", description="cooking", parameters={})
    assert (spec.name, spec.description, spec.parameters) == (
        "transfer_to_chef",
        "cooking",
        {},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.name = "transfer_to_admin"  # type: ignore[misc]


def test_tool_call_is_a_frozen_value_with_an_optional_id() -> None:
    """``call_id`` is optional because several providers publish no id at all."""
    call = ports.ToolCall(name="transfer_to_chef", arguments={})
    assert call.call_id is None
    assert ports.ToolCall("t", {}, "abc").call_id == "abc"
    with pytest.raises(dataclasses.FrozenInstanceError):
        call.name = "tampered"  # type: ignore[misc]


def test_mesh_signal_kinds_are_the_six_declared_events() -> None:
    """All six exist NOW even though later plans trigger four of them.

    ``ports.py`` is edited by one plan in this phase; declaring the vocabulary
    once is what keeps a later wave from having to serialize behind another edit
    to this file.
    """
    assert {kind.value for kind in ports.MeshSignalKind} == {
        "undeclared_peer",
        "budget_exhausted",
        "observer_retry",
        "observer_reroute",
        "unobserved",
        "mesh_unavailable",
    }
    # A ``str`` enum for the same reason ``FallbackReason`` is one: it serializes
    # into the trace's JSON and prints in a notice without a lookup table.
    assert ports.MeshSignalKind.UNDECLARED_PEER == "undeclared_peer"


def test_mesh_signal_is_a_frozen_value() -> None:
    signal = ports.MeshSignal(
        kind=ports.MeshSignalKind.UNDECLARED_PEER,
        turn_id="deadbeef",
        from_agent="host",
        to_agent="admin",
    )
    assert signal.detail == ""
    with pytest.raises(dataclasses.FrozenInstanceError):
        signal.detail = "tampered"  # type: ignore[misc]


def test_mesh_signal_sink_is_a_one_method_protocol() -> None:
    """D-05's "flashlight" endpoint — narrow enough to satisfy in four lines."""
    assert getattr(ports.MeshSignalSink, "_is_protocol", False)
    assert [
        name for name in vars(ports.MeshSignalSink) if not name.startswith("_")
    ] == ["signal"]


def test_undeclared_peer_is_neither_a_degraded_provider_nor_a_config_error() -> None:
    """Negative control: a routing violation is not one more fallback hop (Pattern 2).

    If ``UndeclaredPeer`` subclassed ``AdapterError`` the loop would swallow it
    and print ``↳ fell back to cloud (connection)`` at a routing bug. If it
    subclassed ``EngineError`` it would claim the user's YAML is wrong when
    ``_check_refs`` has already proven the graph integral.
    """
    assert not issubclass(ports.UndeclaredPeer, ports.AdapterError)
    assert not issubclass(ports.UndeclaredPeer, ports.EngineError)
    assert not issubclass(ports.UndeclaredPeer, ports.AllProvidersFailed)
    assert issubclass(ports.UndeclaredPeer, Exception)


def test_tool_calling_chat_adapter_extends_the_phase_3_port() -> None:
    """D-02: the mesh grows a SECOND protocol; ``ChatAdapter`` itself is untouched."""
    assert issubclass(ports.ToolCallingChatAdapter, ports.ChatAdapter)
    assert getattr(ports.ToolCallingChatAdapter, "_is_protocol", False)
    assert hasattr(ports.ToolCallingChatAdapter, "stream_with_tools")
    assert hasattr(ports.ToolCallingChatAdapter, "last_tool_calls")
    # Inherited, not redeclared — the two Phase-3 methods still come from the base.
    assert "stream" not in vars(ports.ToolCallingChatAdapter)
    assert "last_usage" not in vars(ports.ToolCallingChatAdapter)


def test_tool_calling_chat_adapter_is_runtime_checkable() -> None:
    """The engine feature-detects with ``isinstance`` (Code Example 1)."""

    class _NotToolCalling:
        def stream(self, profile: object, messages: object) -> object: ...
        def last_usage(self) -> object: ...

    assert not isinstance(_NotToolCalling(), ports.ToolCallingChatAdapter)


def test_turn_result_records_which_profile_served_and_the_hops() -> None:
    result = ports.TurnResult(
        text="hello",
        served_by="cloud",
        usage=ports.Usage(1, 2),
        fallback_trail=[("local", "cloud", "connection")],
    )
    assert result.served_by == "cloud"
    assert result.fallback_trail == [("local", "cloud", "connection")]


@pytest.mark.parametrize(
    ("error_type", "reason"),
    [
        (ports.ConnectionFailed, ports.FallbackReason.CONNECTION),
        (ports.RequestTimedOut, ports.FallbackReason.TIMEOUT),
        (ports.ServerError, ports.FallbackReason.HTTP_5XX),
        (ports.RateLimited, ports.FallbackReason.HTTP_429),
    ],
)
def test_each_adapter_error_carries_its_fallback_reason(
    error_type: type[ports.AdapterError], reason: ports.FallbackReason
) -> None:
    """The engine classifies a degraded provider by reading ``.reason`` (MODEL-04)."""
    assert issubclass(error_type, ports.AdapterError)
    assert error_type.reason is reason
    assert error_type("boom").reason is reason


def test_slow_first_token_has_no_adapter_error() -> None:
    """Negative control: SLOW_FIRST_TOKEN is the ENGINE's deadline, not an adapter's.

    If an adapter could raise it, the first-token budget would be the provider's
    to define rather than the user's (D-04/D-05).
    """
    adapter_reasons = {
        cls.reason
        for cls in vars(ports).values()
        if isinstance(cls, type)
        and issubclass(cls, ports.AdapterError)
        and cls is not ports.AdapterError
    }
    assert ports.FallbackReason.SLOW_FIRST_TOKEN not in adapter_reasons
    assert len(adapter_reasons) == 4


def test_all_providers_failed_is_not_a_fallback_trigger() -> None:
    """Negative control: exhausting the chain is terminal, never another hop."""
    assert not issubclass(ports.AllProvidersFailed, ports.AdapterError)
    assert issubclass(ports.AllProvidersFailed, Exception)


def test_engine_error_is_not_a_degraded_provider() -> None:
    """Negative control: a configuration failure is never one more fallback hop.

    The same shape as :func:`test_all_providers_failed_is_not_a_fallback_trigger`
    and for the same reason. If ``EngineError`` subclassed ``AdapterError`` the
    chain would print ``↳ fell back to cloud (connection)`` at someone whose real
    problem is a typo in their YAML — a wrong reason, offered confidently.
    """
    assert not issubclass(ports.EngineError, ports.AdapterError)
    assert issubclass(ports.EngineError, Exception)


def test_chat_adapter_is_a_two_method_protocol() -> None:
    assert hasattr(ports.ChatAdapter, "stream")
    assert hasattr(ports.ChatAdapter, "last_usage")
    assert getattr(ports.ChatAdapter, "_is_protocol", False)


def test_ports_source_imports_no_agent_framework() -> None:
    """Source assertion (T-03-11): ports.py may not name the framework at all."""
    source = Path(ports.__file__).read_text(encoding="utf-8")
    for forbidden in ("import langchain", "import langgraph", "from langchain"):
        assert forbidden not in source
    assert "_engine" not in source


def test_public_surface_re_exports_paaf_types() -> None:
    from paaf_llm import (
        AdapterError,
        AllProvidersFailed,
        ChatAdapter,
        EngineError,
        LlmConfig,
        Message,
        ModelProfile,
        TurnResult,
        Usage,
    )

    assert Message is ports.Message
    assert Usage is ports.Usage
    assert TurnResult is ports.TurnResult
    assert ChatAdapter is ports.ChatAdapter
    assert AdapterError is ports.AdapterError
    assert AllProvidersFailed is ports.AllProvidersFailed
    assert EngineError is ports.EngineError
    assert ModelProfile.__module__ == "paaf_llm.profiles"
    assert LlmConfig.__module__ == "paaf_llm.profiles"


def test_public_surface_re_exports_the_mesh_vocabulary() -> None:
    """MESH-01/02: every new port name is importable from the package root."""
    mesh_names = {
        "HandoffRequest",
        "MeshSignal",
        "MeshSignalKind",
        "MeshSignalSink",
        "ToolCall",
        "ToolCallingChatAdapter",
        "ToolSpec",
        "UndeclaredPeer",
    }
    assert mesh_names <= set(paaf_llm.__all__)
    for name in mesh_names:
        assert getattr(paaf_llm, name) is getattr(ports, name)


def test_public_all_is_sorted() -> None:
    """A sorted ``__all__`` is how a re-export stays reviewable as the surface grows."""
    assert paaf_llm.__all__ == sorted(paaf_llm.__all__)


def test_public_surface_exposes_no_engine_symbol() -> None:
    """The adapter package is never part of the public surface (Pitfall 4)."""
    assert not any("_engine" in name.lower() for name in paaf_llm.__all__)
    assert all(hasattr(paaf_llm, name) for name in paaf_llm.__all__)
    assert paaf_llm.__version__ == "0.1.0"
