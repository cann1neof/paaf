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

**The budget test and the hand-back test are a PAIR, and neither means much
alone** (D-08 / MESH-03). An engine with no wall at all passes
``test_hand_back_to_prior_agent_does_not_restart`` perfectly. An engine that
walls at one hop passes ``test_budget_stops_a_loop_and_withdraws_the_tool``
perfectly. Only an engine whose wall stands *above* the legitimate A→B→A
hand-back — which is why the floor is 3 and not 1 — passes both. Read them
together or not at all.

Every test runs against the shipped ``FakeAdapter`` with the agent framework
uninstalled (SC#5), and none of them opens a socket.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from paaf_llm import mesh
from paaf_llm.agent import Agent
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    HandoffRequest,
    MeshSignal,
    MeshSignalKind,
    Message,
    Role,
    ToolCall,
    ToolSpec,
    UndeclaredPeer,
)
from paaf_llm.profiles import LlmConfig, ModelProfile

_TRANSFER_TO_CHEF = ToolCall("transfer_to_chef", {})
_TRANSFER_TO_ADMIN = ToolCall("transfer_to_admin", {})
_TRANSFER_TO_A = ToolCall("transfer_to_a", {})
_TRANSFER_TO_B = ToolCall("transfer_to_b", {})


class SignalRecorder:
    """A four-line :class:`~paaf_llm.ports.MeshSignalSink` (D-05).

    The port is narrow precisely so a listener can be this cheap — Phase 10's
    WebSocket channel and this list satisfy the same contract.
    """

    def __init__(self) -> None:
        self.signals: list[MeshSignal] = []

    def signal(self, event: MeshSignal) -> None:
        self.signals.append(event)

    def of_kind(self, kind: MeshSignalKind) -> list[MeshSignal]:
        return [event for event in self.signals if event.kind is kind]


class MeshTestAdapter(FakeAdapter):
    """A :class:`FakeAdapter` with the two things a multi-LEG turn needs.

    **A hard leg cap.** The budget tests script a mesh that hands off forever,
    so an engine that failed to withdraw the tools would not fail them — it
    would never return, and a hung suite reads as an infrastructure problem
    rather than as the missing wall it actually is. The cap converts that into
    a named assertion. It is set far above any budget under test, so it can
    only fire when the engine's own wall did not.

    **A per-leg script queue.** :meth:`FakeAdapter.program` is static per
    profile on purpose — a program is a fact about a provider, not a queue —
    but a WITHIN-TURN hand-back needs ``a`` to hand off on its first leg and to
    *answer* on its second, which is the whole shape of A→B→A. Rather than give
    the shipped fake a stateful-script feature no production code would want,
    the statefulness lives here. The re-program lands AFTER the leg has fully
    drained, so the tool calls that leg published are the ones it was scripted
    with.
    """

    #: Generous on purpose: it must never be the thing that ends a turn a
    #: correct engine would have ended itself.
    MAX_LEGS = 20

    def __init__(self) -> None:
        super().__init__()
        #: profile key -> queued ``program(...)`` kwargs, one per subsequent leg.
        self.next_programs: dict[str, list[dict[str, Any]]] = {}
        self.legs = 0

    def _count_leg(self, profile: ModelProfile) -> None:
        self.legs += 1
        assert self.legs <= self.MAX_LEGS, (
            f"the turn ran {self.legs} legs without ending — the engine never "
            f"withdrew the handoff tools, so the hop budget is not a wall"
        )

    def _advance(self, profile: ModelProfile) -> None:
        queued = self.next_programs.get(self.program_key(profile))
        if queued:
            self.program(self.program_key(profile), **queued.pop(0))

    async def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        self._count_leg(profile)
        async for token in super().stream(profile, messages):
            yield token
        self._advance(profile)

    async def stream_with_tools(
        self,
        profile: ModelProfile,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> AsyncIterator[str]:
        self._count_leg(profile)
        async for token in super().stream_with_tools(profile, messages, tools):
            yield token
        self._advance(profile)


@pytest.fixture
def mesh_adapter() -> MeshTestAdapter:
    """A fresh :class:`MeshTestAdapter` per test, for the same reason as the fake."""
    return MeshTestAdapter()


def _loop_forever(adapter: FakeAdapter) -> None:
    """Script ``a`` and ``b`` to hand off to each other on every single leg.

    The runaway mesh, expressed as four lines. Every leg that is offered a
    handoff tool calls it, so nothing but the engine's own wall can end the
    turn — which is what makes the budget tests non-vacuous: an engine that
    forgot to withdraw the tools does not fail these tests, it never returns.
    """
    adapter.program("a", tokens=["a speaking"], tool_calls=[_TRANSFER_TO_B])
    adapter.program("b", tokens=["b speaking"], tool_calls=[_TRANSFER_TO_A])


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


# ------------------------------------------------------- D-08 / D-09 / OQ-2 --


def test_tools_for_leg_withdraws_the_surface_at_the_wall(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """The withdrawal rule as a pure function — one place decides it (D-08).

    Unit-testable without driving a turn, and the engine has exactly one place
    that asks. The positive half is the negative control: a predicate that
    returned ``()`` always would satisfy the wall assertion completely.
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]})
    profile = config.profiles["a"]
    args = ("a", profile, config.profiles)

    # Below the wall: the declared peers, in the user's order.
    assert [tool.name for tool in mesh.tools_for_leg(*args, 0, 3)] == ["transfer_to_b"]
    assert [tool.name for tool in mesh.tools_for_leg(*args, 2, 3)] == ["transfer_to_b"]
    # At it and past it: nothing. Not a smaller set, not a flag — nothing.
    assert mesh.tools_for_leg(*args, 3, 3) == ()
    assert mesh.tools_for_leg(*args, 9, 3) == ()


async def test_budget_stops_a_loop_and_withdraws_the_tool(
    mesh_adapter: MeshTestAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """D-08 / T-04-10: a runaway mesh terminates because the tool is taken away.

    Both agents are scripted to hand off on every leg they are offered a tool,
    so nothing inside the model's control ends this turn. The engine's own count
    does — by *withdrawing* the surface, not by instructing anything. The empty
    tuple in ``tool_offers`` is the evidence: the final leg ran, and it was
    offered zero moves.
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]}, hop_budget=3)
    _loop_forever(mesh_adapter)
    signals = SignalRecorder()
    agent = Agent.build(config, mesh_adapter, signals=signals)

    result = await agent.turn("keep going")

    # Exactly three hops, so four legs: A→B→A→B, and B answers with no tool.
    assert [key for key, _ in mesh_adapter.calls] == ["a", "b", "a", "b"]
    assert result.text == "b speaking"
    assert result.served_by == "b"

    # The wall, stated as capability removal rather than as a count.
    assert mesh_adapter.tool_offers[-1] == ("b", ())
    assert [names for _key, names in mesh_adapter.tool_offers[:-1]] == [
        ("transfer_to_b",),
        ("transfer_to_a",),
        ("transfer_to_b",),
    ]

    # Never silent (OQ-2), and never noisy either — once for the turn.
    exhausted = signals.of_kind(MeshSignalKind.BUDGET_EXHAUSTED)
    assert len(exhausted) == 1
    assert exhausted[0].detail == "3"
    assert exhausted[0].turn_id

    # One question in, one answer out (D-10) — the hops left no residue.
    assert agent.history == [
        Message("user", "keep going"),
        Message("assistant", "b speaking"),
    ]


async def test_budget_exhaustion_hands_to_declared_home_agent(
    mesh_adapter: MeshTestAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """D-09: the user named who speaks when the mesh runs out of moves.

    ``home`` declares a peer of its OWN, and that is load-bearing rather than
    scenery. If the home agent had an empty peer list, its leg would be offered
    nothing whether or not the wall existed, and the withdrawal assertion below
    would be green against an engine with no budget at all. With a peer
    declared, an empty offer can only mean the wall.

    Nobody lists ``home`` as a peer, though: declaring a home agent grants no
    handoff edge (T-04-12). ``test_profiles.py`` asserts that half directly.
    """
    config = make_mesh_config(
        active="a",
        peers={"a": ["b"], "b": ["a"], "home": ["a"]},
        hop_budget=3,
        default_agent="home",
    )
    _loop_forever(mesh_adapter)
    mesh_adapter.program("home", tokens=["home speaking"])
    signals = SignalRecorder()
    agent = Agent.build(config, mesh_adapter, signals=signals)

    result = await agent.turn("keep going")

    assert [key for key, _ in mesh_adapter.calls] == ["a", "b", "a", "home"]
    assert result.served_by == "home"
    assert result.text == "home speaking"
    # The home agent is now awake — it holds the conversation it just answered.
    assert agent.awake_agent == "home"
    # Withdrawn for the home agent too: the terminator terminates.
    assert mesh_adapter.tool_offers[-1] == ("home", ())

    exhausted = signals.of_kind(MeshSignalKind.BUDGET_EXHAUSTED)
    assert len(exhausted) == 1
    assert (exhausted[0].from_agent, exhausted[0].to_agent) == ("b", "home")


async def test_exhaustion_no_default_agent_awake_answers(
    mesh_adapter: MeshTestAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """OQ-2: with no home agent declared, whoever is awake answers — no guess.

    ``active_profile`` is ``a`` and the agent awake at the wall is ``b``, so the
    two differ *by construction*. That is the whole design of this test: falling
    back to ``active_profile`` is the natural wrong implementation and D-09
    rejects it outright, but with a==b it would pass unnoticed.
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]}, hop_budget=3)
    assert config.default_agent is None
    _loop_forever(mesh_adapter)
    signals = SignalRecorder()
    agent = Agent.build(config, mesh_adapter, signals=signals)

    result = await agent.turn("keep going")

    assert result.served_by == "b"
    assert result.served_by != config.active_profile  # not a guess, an absence
    assert agent.awake_agent == "b"
    assert mesh_adapter.tool_offers[-1] == ("b", ())

    exhausted = signals.of_kind(MeshSignalKind.BUDGET_EXHAUSTED)
    assert len(exhausted) == 1
    # from and to are the same agent: nobody took over, the moves simply ran out.
    assert (exhausted[0].from_agent, exhausted[0].to_agent) == ("b", "b")


async def test_hand_back_to_prior_agent_does_not_restart(
    mesh_adapter: MeshTestAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """MESH-03, and the budget's negative control: A→B→A inside the wall.

    Two hops, under a floor of three. An engine that walled at one hop would
    pass ``test_budget_stops_a_loop_and_withdraws_the_tool`` and fail here,
    which is the pairing the module docstring describes.

    "Does not restart" is asserted at the strongest available point: all three
    legs of the turn were handed the IDENTICAL message list. Not a similar one —
    the same tuple. A conversation that restarted, or an engine that gave the
    receiving agent a trimmed transcript, could not produce that.
    """
    config = make_mesh_config(
        active="a",
        peers={"a": ["b"], "b": ["a"]},
        base_prompt="you are paaf",
        hop_budget=3,
    )
    signals = SignalRecorder()
    agent = Agent.build(config, mesh_adapter, signals=signals)

    # A prior turn, so "the whole prior conversation" is a non-empty thing.
    mesh_adapter.program("a", tokens=["hello there"])
    await agent.turn("hi")

    # a hands off on its first leg of the NEXT turn and answers on its second.
    mesh_adapter.program("a", tokens=[], tool_calls=[_TRANSFER_TO_B])
    mesh_adapter.next_programs["a"] = [{"tokens": ["risotto, obviously"]}]
    mesh_adapter.program("b", tokens=[], tool_calls=[_TRANSFER_TO_A])

    result = await agent.turn("what's for dinner?")

    assert [key for key, _ in mesh_adapter.calls] == ["a", "a", "b", "a"]
    assert result.text == "risotto, obviously"
    assert result.served_by == "a"
    assert result.handoff == HandoffRequest(from_agent="b", to_agent="a")
    assert agent.awake_agent == "a"

    expected = (
        Message("system", agent.system_prompt()),
        Message("user", "hi"),
        Message("assistant", "hello there"),
        Message("user", "what's for dinner?"),
    )
    turn_two = [messages for _key, messages in mesh_adapter.calls[1:]]
    assert turn_two == [expected, expected, expected]

    # ONE reply for three legs, and exactly two new history entries (D-10).
    assert agent.history == [
        Message("user", "hi"),
        Message("assistant", "hello there"),
        Message("user", "what's for dinner?"),
        Message("assistant", "risotto, obviously"),
    ]
    # The wall was never reached, so nothing announced that it was.
    assert signals.of_kind(MeshSignalKind.BUDGET_EXHAUSTED) == []


async def test_awake_agent_is_sticky_across_turns(
    mesh_adapter: MeshTestAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """MESH-03 / Assumption A3: the agent that ended a turn awake starts the next.

    Sticky WITHIN the process and deliberately not persisted — Phase-3 history is
    already ephemeral (D-01), so a persisted awake agent would come back
    remembering nothing that was said to it.

    The second turn scripts no handoff at all, so ``b`` streaming first is only
    explicable by stickiness: an engine that reset to ``active_profile`` would
    show ``a`` streaming and handing off again.
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]})
    mesh_adapter.program("a", tokens=[], tool_calls=[_TRANSFER_TO_B])
    mesh_adapter.program("b", tokens=["b answers"])
    agent = Agent.build(config, mesh_adapter)

    await agent.turn("first question")
    assert agent.awake_agent == "b"

    result = await agent.turn("second question")

    assert [key for key, _ in mesh_adapter.calls] == ["a", "b", "b"]
    assert result.served_by == "b"
    assert result.handoff is None  # nobody handed off; b was simply already up
    assert agent.awake_agent == "b"


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
