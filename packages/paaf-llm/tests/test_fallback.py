# SPDX-License-Identifier: Apache-2.0
"""MODEL-03/04 + D-06: losing a provider must not lose the conversation.

Five ways a provider can stop being useful, and the loop must survive all five:
it is unreachable (MODEL-03), it times out, it answers 5xx, it answers 429, or —
the one no framework built-in expresses — it accepts the request and then never
produces a first token inside the user's budget (D-04/D-05).

Every test here runs against the shipped fake with the agent framework
uninstalled (SC#1), and none of them opens a socket: a degraded provider is
*programmed*, never simulated by a real transport, so the suite is deterministic
and sub-second.

The negative controls matter as much as the triggers. ``test_healthy_no_fallback``
proves the loop does not fall back when it must not, and
``test_no_mid_stream_fallback`` proves the deadline is time-to-FIRST-token rather
than a stopwatch on the whole reply. Without them, an engine that always fell
back — or one that aborted long healthy answers — would pass every positive test
in this file.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from paaf_llm.agent import Agent
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    AdapterError,
    ConnectionFailed,
    FallbackReason,
    RateLimited,
    RequestTimedOut,
    ServerError,
)
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_trace.store import TraceStore

#: Marks the one trigger that is NOT an adapter exception. "Too slow" is the
#: user's judgement (``first_token_budget_s``), so only the engine may classify
#: it — the fake merely sleeps (see :mod:`paaf_llm.fake`).
SLOW = "slow-first-token"

#: A budget small enough to fire well inside a test, paired with a delay
#: comfortably above it. Both are sub-second: the suite must stay fast.
BUDGET_S = 0.02
DELAY_S = 0.5

#: ``(trigger, expected reason recorded in the trail)`` — the four degraded
#: adapter errors (MODEL-04) plus the engine-owned deadline (D-04/D-05).
TRIGGERS: list[tuple[Any, str]] = [
    (ConnectionFailed, FallbackReason.CONNECTION.value),
    (RequestTimedOut, FallbackReason.TIMEOUT.value),
    (ServerError, FallbackReason.HTTP_5XX.value),
    (RateLimited, FallbackReason.HTTP_429.value),
    (SLOW, FallbackReason.SLOW_FIRST_TOKEN.value),
]


def chain_config(
    make_profile: Callable[..., ModelProfile], **local_overrides: Any
) -> LlmConfig:
    """A two-profile config: active ``local``, then ``cloud``, in that order."""
    return LlmConfig(
        active_profile="local",
        profiles={
            "local": make_profile("local", **local_overrides),
            "cloud": make_profile("cloud"),
        },
        fallback_chain=["cloud"],
    )


def degrade_local(
    adapter: FakeAdapter, make_profile: Callable[..., ModelProfile], trigger: Any
) -> LlmConfig:
    """Program ``local`` to fail with ``trigger`` and ``cloud`` to answer."""
    if trigger is SLOW:
        config = chain_config(make_profile, first_token_budget_s=BUDGET_S)
        adapter.program("local", tokens=["late"], first_token_delay_s=DELAY_S)
    else:
        config = chain_config(make_profile)
        adapter.program("local", fail=trigger)
    adapter.program("cloud", tokens=["from-", "cloud"])
    return config


async def drain(store: TraceStore, tmp_path: Path) -> list[dict[str, Any]]:
    """Stop the writer, then read every ``runs`` row back out of the DB.

    ``stop()`` flushes the queue and is idempotent, so the ``trace_store``
    fixture's own teardown stays safe. The path is the one the fixture names
    (see ``conftest.py``) — reading the real file is the point: an assertion
    against an in-memory list would not prove the row was ever written.
    """
    await store.stop()
    assert store.dropped == 0, "a trace event was dropped — the read proves nothing"
    async with (
        aiosqlite.connect(str(tmp_path / "trace.db")) as db,
        db.execute(
            "SELECT prompts, model, served_by, fallback_trail, "
            "prompt_tokens, completion_tokens FROM runs"
        ) as cur,
    ):
        rows = await cur.fetchall()
    keys = (
        "prompts",
        "model",
        "served_by",
        "fallback_trail",
        "prompt_tokens",
        "completion_tokens",
    )
    return [dict(zip(keys, row, strict=True)) for row in rows]


# --------------------------------------------------------------- D-06 trace --


@pytest.mark.parametrize(("trigger", "reason"), TRIGGERS, ids=[r for _t, r in TRIGGERS])
async def test_fallback_traced(
    fake_adapter: FakeAdapter,
    make_profile: Callable[..., ModelProfile],
    trace_store: TraceStore,
    tmp_path: Path,
    trigger: Any,
    reason: str,
) -> None:
    """Every degraded reason reaches the trace, named, with its from/to hop."""
    config = degrade_local(fake_adapter, make_profile, trigger)
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    await agent.turn("hi")
    rows = await drain(trace_store, tmp_path)

    assert len(rows) == 1, "exactly one run row per turn"
    assert rows[0]["served_by"] == "cloud"
    assert json.loads(rows[0]["fallback_trail"]) == [
        {"from": "local", "to": "cloud", "reason": reason}
    ]


async def test_trace_records_the_served_profile_and_the_prompt(
    fake_adapter: FakeAdapter,
    make_llm_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """A healthy turn is traced too — with an EMPTY trail, not a missing one."""
    config = make_llm_config(active="local", base_prompt="You are PAAF.")
    fake_adapter.program("local", tokens=["ok"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    await agent.turn("hi")
    rows = await drain(trace_store, tmp_path)

    assert rows[0]["prompts"] == "You are PAAF."
    assert rows[0]["model"] == "local"
    assert rows[0]["served_by"] == "local"
    assert json.loads(rows[0]["fallback_trail"]) == []


async def test_usage_aggregated_reaches_the_trace(
    fake_adapter: FakeAdapter,
    make_llm_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """SPIKE-05: the counts written are the post-aggregation ones, not None."""
    config = make_llm_config(active="local")
    fake_adapter.program("local", tokens=["a", "b"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    result = await agent.turn("hi")
    rows = await drain(trace_store, tmp_path)

    assert rows[0]["prompt_tokens"] == result.usage.prompt_tokens
    assert rows[0]["completion_tokens"] == result.usage.completion_tokens
    assert rows[0]["prompt_tokens"] is not None
    assert rows[0]["completion_tokens"] is not None


async def test_no_trace_store_is_not_an_error(
    fake_adapter: FakeAdapter, make_llm_config: Callable[..., LlmConfig]
) -> None:
    """Tracing is optional: an agent built without a sink still serves turns."""
    config = make_llm_config(active="local")
    fake_adapter.program("local", tokens=["ok"])

    result = await Agent.build(config, fake_adapter).turn("hi")

    assert result.text == "ok"


def test_every_fallback_reason_has_a_trigger_in_this_file() -> None:
    """Control: the parametrization covers the WHOLE reason enum, not a subset.

    A new ``FallbackReason`` added without a trigger here would otherwise ship
    entirely untested while this file still looked exhaustive.
    """
    covered = {reason for _trigger, reason in TRIGGERS}
    assert covered == {r.value for r in FallbackReason}


def test_adapter_error_subclasses_are_all_exercised() -> None:
    """Control: every AdapterError subclass appears as a programmed trigger."""
    triggered = {t for t, _r in TRIGGERS if isinstance(t, type)}
    assert triggered == set(AdapterError.__subclasses__())
