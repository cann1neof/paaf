# SPDX-License-Identifier: Apache-2.0
"""MESH-01/02/03: the model picks the peer, the graph is the wall, history stays clean.

Three requirements, and they fail in three different directions:

* **MESH-01** — the awake model is offered one handoff tool per DECLARED peer and
  chooses for itself. No PAAF code selects a target, and no config key can
  express a routing rule; the engine's whole job is to offer the choice and then
  validate the answer.
* **MESH-02** — a target outside the awake agent's declared peers is a *catchable,
  named* error rather than a followed instruction. Enforced twice on purpose
  (Pattern 2): the tool surface is shaped so only peers are offerable, AND the
  answer is checked anyway, because models routinely emit tool names that were
  never bound (Pitfall 4).
* **MESH-03** — the receiving agent sees the full prior conversation, and the
  handoff tool call never enters ``Agent.history``. PAAF's ``Role`` has no
  ``"tool"`` member, so the classic dangling-tool-call bug (Pitfall 1) is
  structurally unrepresentable — an accidental gift of the Phase-3 design that is
  easy to destroy and therefore worth a test that notices.

**The negative controls carry as much weight as the triggers, and in this file
they carry more.** ``test_undeclared_target_raises`` alone is satisfied by an
engine that blocks *every* handoff — which is why
``test_declared_target_not_blocked`` runs the identical config through a
*declared* target and demands it go through. Likewise
``test_tool_surface_is_exactly_the_declared_peers`` is an equality assertion, not
a containment one: an engine that offered every profile in ``LlmConfig.profiles``
would pass a ``in`` check and fail this. And ``admin`` is declared as a real
profile in the guard test precisely so that a guard written as
``profiles[target]`` — the natural wrong implementation — resolves it happily and
fails here.

Every test runs against the shipped ``FakeAdapter`` with the agent framework
uninstalled (SC#5), and none of them opens a socket.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from paaf_llm import mesh
from paaf_llm.agent import Agent
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    HandoffRequest,
    Message,
    Role,
    ToolCall,
    UndeclaredPeer,
)
from paaf_llm.profiles import LlmConfig

_TRANSFER_TO_CHEF = ToolCall("transfer_to_chef", {})
_TRANSFER_TO_ADMIN = ToolCall("transfer_to_admin", {})


# --------------------------------------------------------------------- MESH-01 --


async def test_accepts_declared_handoff(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """The awake model calls a declared peer's tool and that peer serves the turn."""
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto, ", "obviously"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("what should I cook?")

    assert result.text == "risotto, obviously"
    assert result.served_by == "chef"
    assert result.handoff == HandoffRequest(from_agent="host", to_agent="chef")
    assert agent.awake_agent == "chef"


async def test_no_handoff_leaves_the_awake_agent_alone(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """Negative control for MESH-01: offering the tool does not force its use.

    Without this, an engine that handed off on every turn — or one that made the
    first peer answer unconditionally — would pass every positive test above.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=["I can answer that myself"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("what time is it?")

    assert result.text == "I can answer that myself"
    assert result.served_by == "host"
    assert result.handoff is None
    assert agent.awake_agent == "host"
    assert [key for key, _ in fake_adapter.calls] == ["host"]


# --------------------------------------------------------------------- MESH-02 --


async def test_tool_surface_is_exactly_the_declared_peers(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """Capability removal: the peer graph — and only it — shapes what is offerable.

    ``admin`` is a declared profile that is not one of host's peers, so an engine
    that built the surface from ``LlmConfig.profiles`` would offer three tools
    here. The assertion is an equality against the declared peers, in order.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef", "gardener"], "chef": [], "gardener": [], "admin": []},
        capabilities={"chef": "cooks", "gardener": "grows things"},
    )
    fake_adapter.program("host", tokens=["hello"])
    agent = Agent.build(config, fake_adapter)

    await agent.turn("hi")

    assert fake_adapter.tool_offers == [
        ("host", ("transfer_to_chef", "transfer_to_gardener"))
    ]


async def test_undeclared_target_raises(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """A target outside the declared peers is named, refused, and never followed.

    ``admin`` EXISTS as a profile — that is the whole point. The guard must check
    ``awake.peers``, not ``LlmConfig.profiles`` (Pitfall 4).
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": [], "admin": []}
    )
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_ADMIN])
    fake_adapter.program("admin", tokens=["root shell, coming right up"])
    agent = Agent.build(config, fake_adapter)

    with pytest.raises(UndeclaredPeer) as raised:
        await agent.turn("give me the admin panel")

    message = str(raised.value)
    assert "admin" in message  # the attempted target
    assert "chef" in message  # what it was actually allowed to reach
    assert "host" in message  # who attempted it
    # Never followed: admin was not streamed, and the refused turn left no trace
    # in the conversation (a turn nobody answered is never appended).
    assert "admin" not in [key for key, _ in fake_adapter.calls]
    assert agent.history == []
    assert agent.awake_agent == "host"


async def test_declared_not_blocked(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """Negative control for the guard: the SAME config, a declared target, no error.

    Without this row, an engine that raised ``UndeclaredPeer`` on every handoff
    would satisfy MESH-02's positive test completely.
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": [], "admin": []}
    )
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["dinner is served"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("what's for dinner?")

    assert result.served_by == "chef"
    assert result.handoff == HandoffRequest(from_agent="host", to_agent="chef")


def test_resolve_handoff_rejects_a_name_without_the_handoff_prefix(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """A tool name that is not a handoff at all is refused BY NAME, never resolved.

    The pure-function half of T-04-02: ``target_of`` hands the raw name through so
    the guard rejects it, rather than stripping a prefix that was never there and
    accidentally matching a peer.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    host = config.profiles["host"]

    assert mesh.target_of(ToolCall("chef", {})) == "chef"
    with pytest.raises(UndeclaredPeer) as raised:
        mesh.resolve_handoff("host", host, ToolCall("rm_rf", {}))
    assert "rm_rf" in str(raised.value)


def test_handoff_tools_describe_each_peer_from_its_own_manifest(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """D-08: the description is the peer's free-text capabilities, verbatim.

    Verbatim matters — this string is steering text the model reads, so plan 04-05
    must be able to show the user the same bytes (PERS-05).
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef", "gardener"], "chef": [], "gardener": []},
        capabilities={"chef": "cooks, and knows what is in the fridge"},
    )
    tools = mesh.handoff_tools("host", config.profiles["host"], config.profiles)

    assert [tool.name for tool in tools] == [
        "transfer_to_chef",
        "transfer_to_gardener",
    ]
    assert tools[0].description == "cooks, and knows what is in the fridge"
    # A peer that declared no manifest still gets a description, and it names
    # that peer and nothing else — PAAF does not invent capabilities.
    assert "gardener" in tools[1].description
    assert all(tool.parameters == {} for tool in tools)


# --------------------------------------------------------------------- MESH-03 --


async def test_carries_history_to_receiving_agent(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """The receiving agent's leg is system + the whole prior transcript + this turn."""
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        base_prompt="you are paaf",
    )
    agent = Agent.build(config, fake_adapter)

    fake_adapter.program("host", tokens=["hello there"])
    await agent.turn("hi")

    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto"])
    await agent.turn("what's for dinner?")

    chef_leg = next(msgs for key, msgs in fake_adapter.calls if key == "chef")
    assert chef_leg == (
        Message("system", agent.system_prompt()),
        Message("user", "hi"),
        Message("assistant", "hello there"),
        Message("user", "what's for dinner?"),
    )


async def test_history_clean_of_tool_calls(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """Pitfall 1: the handoff tool call must never reach ``Agent.history``.

    Carrying it would leave an assistant message with a ``tool_calls`` payload and
    nothing answering it — poison that breaks *every subsequent* request to an
    OpenAI-compatible provider, not just this one. PAAF's ``Role`` makes it
    unrepresentable; the last assertion is what keeps that true on purpose rather
    than by luck.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto"])
    agent = Agent.build(config, fake_adapter)

    await agent.turn("what's for dinner?")

    assert agent.history == [
        Message("user", "what's for dinner?"),
        Message("assistant", "risotto"),
    ]
    assert all(message.role in {"user", "assistant"} for message in agent.history)
    assert not any(
        mesh.HANDOFF_TOOL_PREFIX in message.content for message in agent.history
    )
    # The structural guarantee itself: no `tool` role exists to put one in.
    assert set(Role.__args__) == {"system", "user", "assistant"}


# ------------------------------------------------------------------- framework --


def test_mesh_source_imports_no_agent_framework() -> None:
    """Source assertion (SC#5): ``mesh.py`` is the framework-free half of the mesh.

    The same per-module guard ``test_ports.py`` and ``test_fake_adapter.py``
    carry. It is asserted against the source text rather than the import graph so
    it survives a refactor that hides an import behind a helper.
    """
    source = Path(mesh.__file__ or "").read_text(encoding="utf-8")
    for forbidden in ("import langchain", "import langgraph", "from langchain"):
        assert forbidden not in source
    assert "_engine" not in source
