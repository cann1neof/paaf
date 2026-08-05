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

``test_turn_result_carries_the_inert_handoff_seam`` is the Phase-4 seam guard:
``TurnResult.handoff`` exists and is always ``None`` this phase, so adding real
handoff behavior in Phase 4 does not change the port's shape.
"""

from __future__ import annotations

import dataclasses
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


def test_turn_result_carries_the_inert_handoff_seam() -> None:
    """The Phase-4 seam is present and defaults to None (design-only this phase)."""
    assert ports.TurnResult.__dataclass_fields__["handoff"].default is None
    result = ports.TurnResult(text="hello", served_by="local", usage=ports.Usage())
    assert result.handoff is None
    assert result.fallback_trail == []


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
    assert ModelProfile.__module__ == "paaf_llm.profiles"
    assert LlmConfig.__module__ == "paaf_llm.profiles"


def test_public_surface_exposes_no_engine_symbol() -> None:
    """The adapter package is never part of the public surface (Pitfall 4)."""
    assert not any("_engine" in name.lower() for name in paaf_llm.__all__)
    assert all(hasattr(paaf_llm, name) for name in paaf_llm.__all__)
    assert paaf_llm.__version__ == "0.1.0"
