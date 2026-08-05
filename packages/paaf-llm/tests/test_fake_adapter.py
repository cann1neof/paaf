# SPDX-License-Identifier: Apache-2.0
"""SC#1: the shipped fake drives the port deterministically, framework-free.

``FakeAdapter`` is the substrate the rest of Phase 3 is tested against, so its
own behavior has to be pinned first: scripted tokens arrive in order, each of the
four degraded triggers can be summoned on demand, and a slow first token is
*slow* rather than pre-classified — the engine's deadline decides, never the
adapter (D-04/D-05).

The two source-level assertions (``test_fake_source_imports_no_agent_framework``
and the Protocol conformance check) are what keep the fake honest as a stand-in:
if it ever needed the framework, the "suite passes with the framework
uninstalled" promise would be dead on arrival.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest
from paaf_llm import fake as fake_module
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    AdapterError,
    ChatAdapter,
    ConnectionFailed,
    Message,
    RateLimited,
    RequestTimedOut,
    ServerError,
    Usage,
)
from paaf_llm.profiles import ModelProfile

_HELLO = [Message("user", "hi")]


async def _drain(adapter: FakeAdapter, profile: ModelProfile) -> list[str]:
    return [token async for token in adapter.stream(profile, _HELLO)]


def test_fake_adapter_satisfies_the_chat_adapter_protocol() -> None:
    assert isinstance(FakeAdapter(), ChatAdapter)


async def test_streams_the_scripted_tokens_in_order(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    fake_adapter.program("local", tokens=["a", "b", "c"])
    assert await _drain(fake_adapter, make_profile("local")) == ["a", "b", "c"]


async def test_programs_are_addressed_per_profile(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """Two profiles, two scripts — the substrate every fallback test needs."""
    fake_adapter.program("local", tokens=["from-local"])
    fake_adapter.program("cloud", tokens=["from-cloud"])
    assert await _drain(fake_adapter, make_profile("local")) == ["from-local"]
    assert await _drain(fake_adapter, make_profile("cloud")) == ["from-cloud"]


async def test_last_usage_reports_concrete_counts_after_aggregation(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """SPIKE-05: usage is read once, AFTER the stream — and it is not vacuous."""
    fake_adapter.program("local", tokens=["a"], usage=Usage(31, 7))
    await _drain(fake_adapter, make_profile("local"))
    assert fake_adapter.last_usage() == Usage(31, 7)


async def test_last_usage_defaults_to_concrete_counts(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """An unspecified program still reports real numbers, so usage tests can fail."""
    fake_adapter.program("local", tokens=["a"])
    await _drain(fake_adapter, make_profile("local"))
    usage = fake_adapter.last_usage()
    assert usage.prompt_tokens is not None
    assert usage.completion_tokens is not None


@pytest.mark.parametrize(
    "failure",
    [ConnectionFailed, RequestTimedOut, ServerError, RateLimited],
)
async def test_programmed_failure_raises_on_the_first_token(
    fake_adapter: FakeAdapter,
    make_profile: Callable[..., ModelProfile],
    failure: type[AdapterError],
) -> None:
    """Each degraded trigger is summonable — the four fallback tests' substrate."""
    fake_adapter.program("local", fail=failure)
    gen = fake_adapter.stream(make_profile("local"), _HELLO)
    with pytest.raises(failure) as raised:
        await gen.__anext__()
    assert raised.value.reason is failure.reason


async def test_slow_first_token_is_the_engines_deadline_to_fire(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """The fake delays; it never raises SLOW_FIRST_TOKEN itself (D-04/D-05).

    Negative control for the whole slow-first-token design: if the fake raised an
    AdapterError here, the budget would belong to the provider rather than to the
    user's ``first_token_budget_s``.
    """
    fake_adapter.program("slow", tokens=["late"], first_token_delay_s=99)
    gen = fake_adapter.stream(make_profile("slow"), _HELLO)
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await gen.__anext__()
    await gen.aclose()


async def test_a_zero_delay_program_yields_immediately(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """Positive control: the delay above is the program's, not the fake's floor."""
    fake_adapter.program("local", tokens=["now"])
    async with asyncio.timeout(1.0):
        assert await _drain(fake_adapter, make_profile("local")) == ["now"]


async def test_unprogrammed_profile_fails_loudly(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """An unscripted profile is a test bug, not a silently empty stream.

    Pointedly NOT an ``AdapterError``: a fallback loop catches those, so a
    forgotten ``program()`` call would be swallowed as a plausible-looking hop.
    """
    gen = fake_adapter.stream(make_profile("never-programmed"), _HELLO)
    with pytest.raises(LookupError) as raised:
        await gen.__anext__()
    assert not isinstance(raised.value, AdapterError)
    assert "never-programmed" in str(raised.value)


async def test_records_the_messages_it_was_handed(
    fake_adapter: FakeAdapter, make_profile: Callable[..., ModelProfile]
) -> None:
    """Multi-turn/history and composed-prompt tests assert against ``calls``."""
    fake_adapter.program("local", tokens=["ok"])
    messages = [Message("system", "you are paaf"), Message("user", "hi")]
    async for _ in fake_adapter.stream(make_profile("local"), messages):
        pass
    assert fake_adapter.calls == [("local", tuple(messages))]


def test_fake_source_imports_no_agent_framework() -> None:
    """Source assertion (SC#1): the shipped fake may not name the framework."""
    source = Path(fake_module.__file__ or "").read_text(encoding="utf-8")
    for forbidden in ("import langchain", "import langgraph", "from langchain"):
        assert forbidden not in source
