# SPDX-License-Identifier: Apache-2.0
"""The walking skeleton: the agent talks, remembers, and gives up honestly.

This is the "it talks" half of plan 03-06. Before any fallback question is
interesting, the plain path has to work: compose the system prompt ONCE through
the single composer (D-02 — no re-derivation, so ``paaf prompt`` cannot drift
from what was actually sent), stream a reply, and keep the exchange in memory so
the *next* turn sees it. ``tests/test_fallback.py`` covers what happens when a
provider degrades; this file covers what happens when nothing does.

Two assertions here are about the shape of the code rather than its behavior,
and they are deliberate: the engine's fallback loop is the one thing this phase
hand-rolls instead of delegating, precisely because it must run with the agent
framework uninstalled (SC#1). A source assertion is the cheapest way to keep
that true, and it fails the build rather than a review.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from paaf_llm import agent as agent_module
from paaf_llm.agent import Agent
from paaf_llm.compose import PromptComposer
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import AllProvidersFailed, ConnectionFailed, Message
from paaf_llm.profiles import LlmConfig


def _agent_source() -> str:
    return Path(agent_module.__file__).read_text(encoding="utf-8")


async def test_it_talks(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """One healthy profile streams a reply, and the exchange enters history."""
    config = make_llm_config(active="local")
    fake_adapter.program("local", tokens=["hel", "lo"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("hi")

    assert result.text == "hello"
    assert result.served_by == "local"
    assert result.fallback_trail == []
    assert result.handoff is None  # the Phase-4 seam stays inert
    assert agent.history == [Message("user", "hi"), Message("assistant", "hello")]


async def test_multi_turn_history(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """The second turn actually SEES the first — history crosses the port."""
    config = make_llm_config(active="local")
    fake_adapter.program("local", tokens=["ok"])
    agent = Agent.build(config, fake_adapter)

    await agent.turn("first")
    await agent.turn("second")

    sent = fake_adapter.calls[1][1]
    assert [m.role for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1] == Message("user", "first")
    assert sent[2] == Message("assistant", "ok")
    assert sent[3] == Message("user", "second")


async def test_the_system_message_is_the_composers_output_verbatim(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """D-02/PERS-05: the engine sends compose() byte-for-byte, adding nothing."""
    fragments = [("weather", "Report temperatures in Celsius.")]
    config = make_llm_config(active="local", base_prompt="You are PAAF.")
    fake_adapter.program("local", tokens=["ok"])
    agent = Agent.build(config, fake_adapter, skill_fragments=fragments)

    await agent.turn("hi")

    system = fake_adapter.calls[0][1][0]
    assert system.role == "system"
    assert system.content == PromptComposer().compose("You are PAAF.", fragments)


async def test_usage_aggregated(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """SPIKE-05: usage is read once AFTER aggregation, so the counts are real."""
    config = make_llm_config(active="local")
    fake_adapter.program("local", tokens=["a", "b"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("hi")

    assert result.usage.prompt_tokens is not None
    assert result.usage.completion_tokens is not None
    assert result.usage == fake_adapter.last_usage()


async def test_all_providers_failed_when_the_whole_chain_degrades(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """The end of the chain is terminal, and a failed turn is NOT remembered."""
    config = make_llm_config(active="local", fallbacks=["cloud"])
    fake_adapter.program("local", fail=ConnectionFailed)
    fake_adapter.program("cloud", fail=ConnectionFailed)
    agent = Agent.build(config, fake_adapter)

    with pytest.raises(AllProvidersFailed):
        await agent.turn("hi")

    # A turn nobody answered must not enter history: the next turn would then
    # ship a user message the model never saw a reply to.
    assert agent.history == []


async def test_warmup_visits_every_profile_in_the_chain(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """Pitfall 2 (two-clock): cold load is paid at warmup, not against the budget."""
    preloaded: list[str] = []

    class _PreloadingAdapter(FakeAdapter):
        async def preload(self, profile: object) -> None:
            preloaded.append(self.program_key(profile))  # type: ignore[arg-type]

    adapter = _PreloadingAdapter()
    config = make_llm_config(active="local", fallbacks=["cloud"])
    agent = Agent.build(config, adapter)

    await agent.warmup()

    assert preloaded == ["local", "cloud"]
    # An adapter with no preload path (the plain fake) must not explode.
    await Agent.build(config, fake_adapter).warmup()


def test_agent_source_imports_no_agent_framework() -> None:
    """MODEL-08/SC#1: the fallback loop is pure PAAF — it names no framework."""
    source = _agent_source()
    for forbidden in ("import langchain", "import langgraph", "from langchain"):
        assert forbidden not in source
    assert "_engine" not in source


def test_first_token_deadline_wraps_only_the_first_anext() -> None:
    """The deadline is time-to-FIRST-token, and the generator is closed on it.

    Source assertion because the alternative — a deadline around the whole
    stream — passes every behavioral test the fake can express while quietly
    aborting a long, healthy reply (D-04: the slow-first-token trigger is about
    *reaching* the first token, never about the rest of the stream).
    """
    source = _agent_source()
    assert "asyncio.timeout(profile.first_token_budget_s)" in source
    assert "__anext__()" in source
    assert "aclose()" in source
