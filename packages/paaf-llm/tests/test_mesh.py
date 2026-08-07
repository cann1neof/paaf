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

import sqlite3
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner
from paaf_llm import cli, mesh
from paaf_llm.agent import PRE_HANDOFF_JOINER, Agent
from paaf_llm.cli import (
    FALLBACK_NOTICE,
    MESH_LIMITS,
    MESH_LIVE_NOTE,
    NO_HOME_AGENT,
    main,
)
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
from paaf_trace.store import TraceStore

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
    # Every leg of this runaway is scripted to SPEAK before handing off, and
    # `keep_pre_handoff_prose` defaults to keeping it (D-11), so the reply is all
    # four legs joined. What matters here is the shape of the wall, not the
    # prose: `served_by` names the leg that ended the turn.
    assert result.text == PRE_HANDOFF_JOINER.join(
        ["a speaking", "b speaking", "a speaking", "b speaking"]
    )
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

    # One question in, one answer out (D-10) — the hops left no residue. Four
    # legs, and still exactly two history entries.
    assert agent.history == [
        Message("user", "keep going"),
        Message("assistant", result.text),
    ]
    assert len(agent.history) == 2


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
    # The three hopping legs spoke before handing off and the default keeps that
    # (D-11); the home agent's own words are the last of the four.
    assert result.text == PRE_HANDOFF_JOINER.join(
        ["a speaking", "b speaking", "a speaking", "home speaking"]
    )
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

    # The transcript half of "does not restart" — identical for all three legs.
    # The SYSTEM message is deliberately excluded from this comparison and
    # asserted separately below: as of MESH-04 each leg carries the RECEIVING
    # agent's own prompt, so demanding one identical tuple here would demand the
    # thing D-17 exists to forbid.
    transcript = (
        Message("user", "hi"),
        Message("assistant", "hello there"),
        Message("user", "what's for dinner?"),
    )
    turn_two = [messages for _key, messages in mesh_adapter.calls[1:]]
    assert [messages[1:] for messages in turn_two] == [transcript] * 3
    assert [messages[0] for messages in turn_two] == [
        Message("system", agent.system_prompt("a")),
        Message("system", agent.system_prompt("b")),
        Message("system", agent.system_prompt("a")),
    ]

    # ONE reply for three legs, and exactly two new history entries (D-10).
    assert agent.history == [
        Message("user", "hi"),
        Message("assistant", "hello there"),
        Message("user", "what's for dinner?"),
        Message("assistant", "risotto, obviously"),
    ]
    # The wall was never reached, so nothing announced that it was.
    assert signals.of_kind(MeshSignalKind.BUDGET_EXHAUSTED) == []


# ------------------------------------------------------------------- D-11 --
#
# What happens to a "let me get the cook" line an agent emitted just before it
# handed off. Three facts sit next to each other and none of them is the whole
# story on its own:
#
#   1. The generated explainer DISCOURAGES the style in prose (plan 04-05).
#   2. The user's setting decides whether such a line reaches them (below).
#   3. Mechanical enforcement — refusing or stripping a leg that spoke before
#      calling handoff — is a deliberate v2 item the founder flagged as really
#      important, NOT an oversight in this phase. Nothing here enforces it.


async def test_pre_handoff_prose_is_kept_by_default(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """The default is to SHOW what the model said, because PAAF does not edit it.

    A user who reads "let me get the cook" and then the cook's answer has an
    accurate picture of what happened. A user who reads only the cook has a
    tidier one that PAAF manufactured — and D-10's silence about routing is
    about not NARRATING the hop, not about deleting the agent's own words.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    assert config.keep_pre_handoff_prose is True  # the schema's default, read here
    fake_adapter.program(
        "host", tokens=["let me ", "get the cook"], tool_calls=[_TRANSFER_TO_CHEF]
    )
    fake_adapter.program("chef", tokens=["risotto, obviously"])
    agent = Agent.build(config, fake_adapter)

    result = await agent.turn("what's for dinner?")

    assert result.text == f"let me get the cook{PRE_HANDOFF_JOINER}risotto, obviously"
    # The final agent still answered, and is still the one credited.
    assert result.served_by == "chef"
    # One question in, one answer out (D-10) — kept prose is part of THE reply,
    # not a second assistant turn, so history grows by exactly two.
    assert len(agent.history) == 2
    assert agent.history[1] == Message("assistant", result.text)


async def test_pre_handoff_prose_dropped_is_still_recoverable_from_the_trace(
    fake_adapter: FakeAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """D-11 off: the user chose not to SEE it, which is not the same as losing it.

    The trace assertion is the load-bearing half and the reason this test is not
    just ``assert "let me" not in result.text``. A drop test that only checked
    absence would pass against a genuinely lossy implementation — one where the
    text the model produced is gone from every record the user owns — and that
    is a hidden edit rather than a presentation choice (T-04-31).

    It is asserted against the ``handoffs`` row rather than the leg's ``runs``
    row because the trace has never carried completion text: ``runs.prompts``
    records what was SENT, and there is no column for what came back. The attempt
    row is where the prose belongs anyway — it is the handoff that discarded it.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        keep_pre_handoff_prose=False,
    )
    fake_adapter.program(
        "host", tokens=["let me ", "get the cook"], tool_calls=[_TRANSFER_TO_CHEF]
    )
    fake_adapter.program("chef", tokens=["risotto, obviously"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    result = await agent.turn("what's for dinner?")

    assert result.text == "risotto, obviously"
    assert "let me get the cook" not in result.text
    assert len(agent.history) == 2
    assert agent.history[1] == Message("assistant", "risotto, obviously")

    await trace_store.stop()
    assert trace_store.dropped == 0
    connection = sqlite3.connect(str(tmp_path / "trace.db"))
    try:
        details = [
            row[0]
            for row in connection.execute("SELECT detail FROM handoffs ORDER BY seq")
        ]
    finally:
        connection.close()

    assert details == ["let me get the cook"]


async def test_a_silent_handoff_adds_no_separator_to_the_reply(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """The common case, and the one the joining code must not disfigure.

    Plan 04-04 measured both gate models and found they emit the handoff tool
    call with ZERO accompanying prose, so an empty pre-handoff leg is the normal
    turn rather than an edge case. An implementation that joined unconditionally
    would prefix every single handed-off reply with a blank line — visible on the
    headline command, and passing every assertion written about the kept case.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto, obviously"])

    result = await Agent.build(config, fake_adapter).turn("what's for dinner?")

    assert result.text == "risotto, obviously"


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


# --------------------------------------------------------------------- MESH-04 --
#
# The explainer, generated from THIS agent's manifest and THIS agent's peers, and
# the per-agent prompt layer it rides in (D-16 layer 3, D-17, D-18). The prompt
# INSPECTOR's half of MESH-04 lives in ``test_inspector.py``; what is proved here
# is that the text exists, is built from the user's own bytes, and is overridable.


def test_explainer_names_each_peer_and_quotes_its_manifest_verbatim() -> None:
    """MESH-04: the explainer is generated from the manifest and the peer graph.

    Verbatim is the whole contract. A summarized or re-worded manifest would put
    words the user never wrote in front of the model while ``paaf prompt`` showed
    the original — the exact divergence PERS-05 exists to prevent, and one that
    would be invisible until routing went somewhere surprising.

    The peer that declared NO manifest is in this test on purpose: it gets the
    same neutral one-liner its handoff tool's description gets, from the same
    :func:`mesh._describe`. Two derivations of a peer's description would let the
    explainer and the tool surface disagree about the same agent.
    """
    profiles = {
        "chef": ModelProfile(
            provider="ollama",
            model="chef",
            capabilities="cooking, recipes, and the kitchen timers",
        ),
        "clerk": ModelProfile(provider="ollama", model="clerk"),
    }
    host = ModelProfile(provider="ollama", model="host", peers=["chef", "clerk"])

    explainer = mesh.explainer_for("host", host, profiles)

    assert "chef" in explainer
    assert "cooking, recipes, and the kitchen timers" in explainer
    # The manifest-less peer is described exactly as its tool describes it.
    tools = {
        tool.name: tool.description
        for tool in mesh.handoff_tools("host", host, profiles)
    }
    for peer in host.peers:
        assert tools[f"{mesh.HANDOFF_TOOL_PREFIX}{peer}"] in explainer
    # Declared order is the user's, here as everywhere else in the mesh.
    assert explainer.index("chef") < explainer.index("clerk")


def test_explainer_is_empty_when_the_agent_declares_no_peers() -> None:
    """No peers, no fragment — an empty labelled segment is noise in the inspector.

    Returning ``""`` rather than a template with an empty list is what keeps the
    ``--provenance`` view honest: a ``mesh:explainer`` heading over nothing would
    say the agent was told something about handing off, and it was not.
    """
    lonely = ModelProfile(provider="ollama", model="lonely")

    assert mesh.explainer_for("lonely", lonely, {}) == ""


def test_explainer_override_precedence_per_agent_beats_global_beats_default() -> None:
    """D-18: generated by default, overridable globally, overridable per agent.

    Three configurations of the same agent, so the ordering is asserted as an
    ordering rather than as three unrelated facts. The per-agent override is used
    VERBATIM — no template is rendered around it — because a user who wrote the
    explainer themselves did not ask PAAF to add a paragraph to it.
    """
    profiles = {"chef": ModelProfile(provider="ollama", model="chef")}
    generated = mesh.explainer_for(
        "host",
        ModelProfile(provider="ollama", model="host", peers=["chef"]),
        profiles,
    )
    global_template = (
        "House rules: you may pass this to " + mesh.EXPLAINER_PEERS_PLACEHOLDER
    )
    with_global = mesh.explainer_for(
        "host",
        ModelProfile(provider="ollama", model="host", peers=["chef"]),
        profiles,
        template=global_template,
    )
    with_both = mesh.explainer_for(
        "host",
        ModelProfile(
            provider="ollama",
            model="host",
            peers=["chef"],
            handoff_explainer="Ask chef about food. Nothing else.",
        ),
        profiles,
        template=global_template,
    )

    assert generated.startswith(mesh.DEFAULT_EXPLAINER_TEMPLATE[:20])
    assert with_global.startswith("House rules:")
    assert "chef" in with_global  # the peer list still lands in the override
    assert with_both == "Ask chef about food. Nothing else."


def test_a_template_without_the_placeholder_is_used_as_written() -> None:
    """A user override is text, not a format string — arbitrary braces are safe.

    Rendering with ``str.format`` would turn a stray ``{oven}`` in the user's own
    prose into a ``KeyError`` at prompt-composition time, which is a crash in the
    one code path that must always be able to show the user what was sent. The
    placeholder is substituted, and everything else is left exactly as written.
    """
    profiles = {"chef": ModelProfile(provider="ollama", model="chef")}
    host = ModelProfile(provider="ollama", model="host", peers=["chef"])

    rendered = mesh.explainer_for(
        "host", host, profiles, template="Set the {oven} to 200C. Peers: {peers}"
    )

    assert (
        rendered
        == "Set the {oven} to 200C. Peers: - chef: Hand the conversation to chef."
    )


def test_default_explainer_states_no_routing_rule(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """T-04-22 / MESH-01: a routing DSL written in English is still a routing DSL.

    The generated explainer is the one piece of steering text PAAF *writes*, so
    it is the one place a routing rule could be smuggled in without any config
    key to reject. It names the peers and quotes their manifests; it states no
    condition under which a handoff should happen, because the moment it did,
    PAAF would be deciding routing and calling it prose.

    A token scan is a smoke check on the template PAAF ships, not a proof about
    anything the user writes — the user is free to write an if-then override, and
    that is their assistant to steer.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        capabilities={"chef": "cooking"},
    )
    explainer = mesh.explainer_for(
        "host", config.profiles["host"], config.profiles
    ).lower()

    for rule_shaped in (
        " if ",
        "whenever",
        "must hand",
        "always hand",
        "score",
        "keyword",
        "matches",
    ):
        assert rule_shaped not in explainer, rule_shaped


def test_default_explainer_discourages_pre_handoff_prose() -> None:
    """D-11: discouraged in the explainer, NOT mechanically enforced in Phase 4.

    The discouragement is prose because Phase 4 deliberately ships no mechanism
    that strips it — that is the v2 item the founder marked as really important,
    and the absence must not read as an oversight.

    Worth knowing while reading this: plan 04-04 measured both gate models and
    found they emit the handoff tool call with *zero* accompanying prose. So this
    paragraph is currently reinforcing what the models already do, rather than
    correcting them, and the code below it must be correct when the prose is
    empty — which is the common case, not the edge case.
    """
    template = mesh.DEFAULT_EXPLAINER_TEMPLATE.lower()

    assert "silent" in template
    assert mesh.EXPLAINER_PEERS_PLACEHOLDER in mesh.DEFAULT_EXPLAINER_TEMPLATE


def test_base_prompt_for_falls_back_to_the_shared_base(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """A4: per-agent prompts are ADDITIVE; the global base stays the shared one."""
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        base_prompt="You are PAAF.",
        system_prompts={"chef": "You are the cook."},
    )

    assert mesh.base_prompt_for(config.profiles["host"], config) == "You are PAAF."
    assert mesh.base_prompt_for(config.profiles["chef"], config) == "You are the cook."


def test_mesh_fragments_omit_what_the_agent_did_not_declare(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """Persona then explainer, in that fixed order, and neither invented.

    Order is fixed rather than incidental because it is part of the composed
    bytes. Omission matters just as much: an agent with no persona must not get
    an empty ``mesh:persona`` segment, or ``--provenance`` would show a heading
    over nothing and imply PAAF said something it did not.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        personas={"host": "Warm and brief."},
    )

    host = mesh.mesh_fragments_for("host", config.profiles["host"], config)
    chef = mesh.mesh_fragments_for("chef", config.profiles["chef"], config)

    assert [source for source, _text in host] == [
        mesh.MESH_PERSONA_SOURCE,
        mesh.MESH_EXPLAINER_SOURCE,
    ]
    assert host[0][1] == "Warm and brief."
    # chef has neither a persona nor a peer, so it contributes no mesh layer.
    assert chef == []


def test_system_prompt_reads_any_declared_agent_awake_or_not(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """D-19's engine half: the one composer can be aimed at a non-awake agent.

    ``paaf prompt --agent chef`` is only honest if it asks the SAME derivation
    the turn loop asks (D-02). This is that derivation, taking a name — which is
    the only way to read the prompt of an agent that is not currently awake, and
    later the only way to read the observer's, since the observer is never awake.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        base_prompt="You are PAAF.",
        system_prompts={"chef": "You are the cook."},
        personas={"chef": "Blunt."},
    )
    agent = Agent.build(config, fake_adapter)

    assert agent.awake_agent == "host"
    # No argument is still the awake agent — no Phase-3 caller changed meaning.
    assert agent.system_prompt() == agent.system_prompt("host")
    assert agent.system_prompt().startswith("You are PAAF.")

    chef_prompt = agent.system_prompt("chef")
    assert chef_prompt.startswith("You are the cook.")
    assert "Blunt." in chef_prompt
    assert chef_prompt != agent.system_prompt()


async def test_each_leg_carries_the_receiving_agents_own_prompt(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """D-17 through the turn loop: the prompt follows the handoff.

    Asserted off ``FakeAdapter.calls`` rather than off ``system_prompt``, because
    the failure this catches is precisely an engine that composes the right
    prompt and then sends the awake agent's one anyway. The two profiles are
    given different prompts AND different personas so a leg carrying the wrong
    one cannot look right by coincidence.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        base_prompt="You are PAAF.",
        system_prompts={"host": "You are the host.", "chef": "You are the cook."},
        personas={"host": "Warm.", "chef": "Blunt."},
    )
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto"])
    agent = Agent.build(config, fake_adapter)

    await agent.turn("what's for dinner?")

    sent = {key: messages[0].content for key, messages in fake_adapter.calls}
    assert sent["host"].startswith("You are the host.")
    assert sent["chef"].startswith("You are the cook.")
    assert "Warm." in sent["host"] and "Warm." not in sent["chef"]
    assert "Blunt." in sent["chef"] and "Blunt." not in sent["host"]
    # host can reach chef, chef can reach nobody: only host is told about peers.
    assert "cooking" not in sent["chef"]


# ------------------------------------------------------------------- the CLI --
#
# The mesh's terminal surface lives here rather than in ``test_inspector.py`` so
# that plan 04-05 can own the inspector module without a merge conflict. These
# two are about MESH-02 and D-08/D-09 reaching the user, not about the prompt.


def _write_mesh_config(tmp_path: Path, config: LlmConfig) -> str:
    """Serialize a validated config to YAML and return its path.

    Round-tripping the model rather than hand-writing YAML means the file the
    CLI reads and the object the test built cannot drift apart.
    """
    path = tmp_path / "paaf.yaml"
    path.write_text(yaml.safe_dump(config.model_dump(mode="json")), encoding="utf-8")
    return str(path)


def test_cli_surfaces_a_routing_violation_and_stays_silent_about_handoffs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """MESH-02 at the terminal, paired with D-10's silence — both in one run.

    The refusal half: a model naming a target its agent was never given exits
    non-zero with a message naming the attempted target AND the declared peers,
    not a traceback. MESH-02 says the violation is "a catchable error rather
    than silently followed"; the library already refuses, and this is what makes
    the refusal *visible*, which is the half a user can act on.

    The silence half is the negative control, and it is the one that would rot
    first. D-10 makes handoff silent in the reply stream: no per-hop notice, and
    specifically not ``_print_fallback_trail``'s ``↳`` shape, which was
    considered for handoffs and declined. A successful A→B turn must therefore
    print one reply and say nothing about the routing that produced it.
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": [], "admin": []}
    )
    path = _write_mesh_config(tmp_path, config)
    arrow = FALLBACK_NOTICE.format(to="", reason="")[0]

    # 1. A handoff that IS allowed: one reply, and not a word about the hop.
    healthy = FakeAdapter()
    healthy.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    healthy.program("chef", tokens=["risotto, obviously"])
    monkeypatch.setattr(
        cli, "_default_adapter", lambda _config, secret_store=None: healthy
    )

    served = CliRunner().invoke(main, ["chat", "--config", path], input="dinner?\n")

    assert served.exit_code == 0, served.output
    assert "chef> risotto, obviously" in served.output
    assert arrow not in served.output  # no fell-back-to trail, and none faked
    assert mesh.HANDOFF_TOOL_PREFIX not in served.output
    assert "handed off" not in served.output.lower()

    # 2. The same config, a target outside host's peers: named and refused.
    violating = FakeAdapter()
    violating.program("host", tokens=[], tool_calls=[_TRANSFER_TO_ADMIN])
    violating.program("admin", tokens=["root shell, coming right up"])
    monkeypatch.setattr(
        cli, "_default_adapter", lambda _config, secret_store=None: violating
    )

    refused = CliRunner().invoke(main, ["chat", "--config", path], input="admin?\n")

    assert refused.exit_code != 0
    assert "admin" in refused.output  # what was attempted
    assert "chef" in refused.output  # what was actually reachable
    assert "Traceback" not in refused.output
    # Never followed: admin was not streamed even though it is a real profile.
    assert "admin" not in [key for key, _ in violating.calls]


def test_cli_profiles_reports_the_hop_budget_and_the_home_agent(
    tmp_path: Path, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """D-08/D-09 reach the user: a peer graph alone does not predict a turn.

    Run twice against the same graph — once with a home agent declared and once
    without — because the second is where the surface could quietly lie. An
    undeclared ``default_agent`` is not a missing value; it is OQ-2's "whoever
    is awake answers", and printing a blank there would read as the former.
    """
    declared = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        hop_budget=5,
        default_agent="host",
    )
    result = CliRunner().invoke(
        main, ["profiles", "--config", _write_mesh_config(tmp_path, declared)]
    )

    assert result.exit_code == 0, result.output
    assert MESH_LIMITS.format(budget=5, home="host") in result.output
    assert MESH_LIVE_NOTE in result.output
    # The graph itself is still shown, unchanged.
    assert "peers: chef" in result.output

    bare = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    result = CliRunner().invoke(
        main, ["profiles", "--config", _write_mesh_config(tmp_path, bare)]
    )

    assert result.exit_code == 0, result.output
    assert MESH_LIMITS.format(budget=3, home=NO_HOME_AGENT) in result.output


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
