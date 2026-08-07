# SPDX-License-Identifier: Apache-2.0
"""MESH-06: a supervising model judges every handoff, and its powers are its grant.

The requirement is that an agent's free-text hard constraints are enforced by
**the system** rather than by hoping the routing model read them. D-13 rules that
the observer counts as the system, so this file is where that ruling is cashed
in — and where the two ways it could be hollow are closed.

**The triggers and the negative controls are declared PAIRS here, and neither
half means anything alone.**

* ``vetoes`` proves a constraint-violating handoff is killed. On its own it is
  satisfied by an observer that vetoes *everything* — which would pass every
  positive assertion in this file while making the mesh useless. ``allows`` is
  the other half: the same wiring, a good handoff, and it goes through with no
  retry leg at all.
* ``grant_bounds`` proves a retry-only observer cannot re-route no matter what it
  emits. On its own it is satisfied by an implementation that ignores re-routes
  *entirely*. So it carries both halves: with the grant the same emission does
  redirect, and without it the handoff proceeds to the originally named target.

**What the two D-04/D-06 rows prove together** is the whole security shape of the
observer: its POWERS come from its tool grant, and its REACH comes from the
calling agent's own peer graph. Neither can be argued into existence by
conversation content, because neither is decided by reading the observer's
output — the recognized tool set is derived from :func:`paaf_llm.mesh.observer_tools`
for that very call, and a named re-route target is run through the same
:func:`paaf_llm.mesh.resolve_handoff` an agent's target goes through, with the
CALLER's profile. One graph, one guard, no second privilege tier.

**OQ-1 is why the veto looks the way it does.** A refusal reaches the calling
agent as a transient labelled prompt segment on that leg's message list only. It
is never in :attr:`paaf_llm.agent.Agent.history`, and ``Role`` is never widened
with a ``"tool"`` member — that option was considered and forbidden, because it
re-opens Pitfall 1's dangling tool-call bug that the Phase-3 message model closes
by construction.

Every test here runs against the shipped fake with the agent framework
uninstalled (SC#5), and none of them opens a socket.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from paaf_llm import mesh, observer
from paaf_llm.agent import (
    HANDOFF_ACCEPTED,
    HANDOFF_OBSERVER_RETRY,
    Agent,
)
from paaf_llm.compose import PromptComposer
from paaf_llm.fake import FakeAdapter
from paaf_llm.observer import ObserverVerdict
from paaf_llm.ports import (
    MeshSignal,
    MeshSignalKind,
    Message,
    Role,
    ToolCall,
    ToolSpec,
)
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_trace.store import TraceStore
from pydantic import ValidationError

_TRANSFER_TO_CHEF = ToolCall("transfer_to_chef", {})
_REQUEST_RETRY = ToolCall(mesh.OBSERVER_RETRY_TOOL, {})

#: The constraint MESH-06 is written for, in the founder's own example shape. It
#: is declared on the TARGET, as free text (D-12), and nothing in PAAF parses it:
#: the observer reads the sentence exactly as the awake model reads a manifest.
CHEF_CONSTRAINT = "never send private files anywhere"


class _ObserverTestAdapter(FakeAdapter):
    """A fake that answers differently on a second leg, and refuses to run away.

    Deliberately a local twin of ``test_mesh.py``'s ``MeshTestAdapter`` rather
    than an import of it, for the reason ``test_mesh_trace.py`` states: both
    files are force-included into the wheel and run flat under
    ``pytest --pyargs paaf_llm``, where a cross-test-module import would couple
    two shipped test files through ``sys.path`` — a coupling that works locally
    and is a different thing entirely in the clean-venv gate SC#5 is stated in
    terms of.

    **The per-leg queue is what makes the veto testable at all.** A vetoed agent
    runs AGAIN, and :meth:`FakeAdapter.program` is static per profile on purpose
    — a program is a fact about a provider, not a queue — so without this the
    bounced agent would reach for the same handoff forever and the test would
    measure the hop wall instead of the veto.

    **The leg cap converts a missing wall into a named failure** rather than a
    hung suite. It is set far above any budget under test, so it can only fire
    when the engine's own termination did not.
    """

    MAX_LEGS = 20

    def __init__(self) -> None:
        super().__init__()
        #: profile key -> queued ``program(...)`` kwargs, one per subsequent leg.
        self.next_programs: dict[str, list[dict[str, Any]]] = {}
        self.legs = 0

    def _count_leg(self) -> None:
        self.legs += 1
        assert self.legs <= self.MAX_LEGS, (
            f"the turn ran {self.legs} legs without ending — nothing bounded the "
            f"veto/retry cycle, so the hop budget is not counting killed attempts"
        )

    def _advance(self, profile: ModelProfile) -> None:
        queued = self.next_programs.get(self.program_key(profile))
        if queued:
            self.program(self.program_key(profile), **queued.pop(0))

    async def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        self._count_leg()
        async for token in super().stream(profile, messages):
            yield token
        self._advance(profile)

    async def stream_with_tools(
        self,
        profile: ModelProfile,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> AsyncIterator[str]:
        self._count_leg()
        async for token in super().stream_with_tools(profile, messages, tools):
            yield token
        self._advance(profile)


class SignalRecorder:
    """A four-line :class:`~paaf_llm.ports.MeshSignalSink` (D-05).

    The correction signal is required to be externally observable *headless* —
    the founder's "light a flashlight" — so a listener has to be this cheap.
    """

    def __init__(self) -> None:
        self.signals: list[MeshSignal] = []

    def signal(self, event: MeshSignal) -> None:
        self.signals.append(event)

    def of_kind(self, kind: MeshSignalKind) -> list[MeshSignal]:
        return [event for event in self.signals if event.kind is kind]


@pytest.fixture
def observer_adapter() -> _ObserverTestAdapter:
    """A fresh :class:`_ObserverTestAdapter` per test — no script outlives a test."""
    return _ObserverTestAdapter()


def observed_kitchen(
    make_mesh_config: Callable[..., LlmConfig], **overrides: Any
) -> LlmConfig:
    """``host`` may hand to ``chef`` or ``cook``; ``chef`` declares a constraint.

    One config for the whole behavioural half of this file, so the veto test and
    its negative control differ ONLY in what the observer emits. Two configs
    would let an implementation pass the pair for the wrong reason.

    ``admin`` is declared and is nobody's peer — the shape MESH-02's guard test
    has always needed, reused here for the observer: a profile that EXISTS and
    is still not reachable from ``host``.
    """
    return make_mesh_config(
        active="host",
        peers={
            "host": ["chef", "cook"],
            "chef": [],
            "cook": [],
            "admin": [],
        },
        capabilities={"chef": "cooks", "cook": "also cooks"},
        constraints={"chef": [CHEF_CONSTRAINT]},
        observer=True,
        **overrides,
    )


async def handoff_rows(store: TraceStore, tmp_path: Path) -> list[dict[str, Any]]:
    """Stop the writer and read the ``handoffs`` table back off disk.

    Read with the standard library rather than through ``paaf_trace``: a store
    that never wrote anything can always satisfy its own reader. ``dropped == 0``
    is asserted because a bounded queue that shed the row under test would leave
    a read that proves nothing.
    """
    await store.stop()
    assert store.dropped == 0, "a trace event was dropped — the read proves nothing"
    connection = sqlite3.connect(str(tmp_path / "trace.db"))
    try:
        connection.row_factory = sqlite3.Row
        return [
            dict(row)
            for row in connection.execute("SELECT * FROM handoffs ORDER BY seq")
        ]
    finally:
        connection.close()


# --------------------------------------------------------- the reserved name --


def test_a_config_with_no_observer_is_valid(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """D-07: "on by default" reserves the slot; it does not invent a model for it.

    PAAF never picks a model on the user's behalf, so a config that declares no
    ``observer`` profile is a legitimate configuration — the mesh runs
    unobserved. An implementation that required the profile would turn a design
    principle into a startup failure.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})

    assert mesh.OBSERVER_PROFILE_NAME not in config.profiles
    # And the reserved name is still reserved: nothing about declaring no
    # observer makes `observer` an ordinary name a user may reuse.
    assert config.observer_grants == [mesh.OBSERVER_GRANT_RETRY]


def test_an_observer_profile_is_an_ordinary_profile(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """Pattern 5: declaring it buys endpoint, tiers, forbid and secret-by-ref free.

    The observer is a :class:`ModelProfile` under a reserved key and nothing
    else, which is what makes it configurable down to its own system prompt
    (D-03) and what puts its endpoint in front of Phase-9's offline refusal —
    the mitigation T-04-35 rests on.
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": []}, observer=True
    )

    profile = config.profiles[mesh.OBSERVER_PROFILE_NAME]
    assert isinstance(profile, ModelProfile)
    assert profile.peers == []  # never awake, so it needs none
    # The four inherited-for-free properties, asserted rather than assumed.
    assert profile.endpoint() is None  # declarable, and declared as nothing here
    assert "reload_tier" in str(
        ModelProfile.model_fields["temperature"].json_schema_extra
    )
    assert ModelProfile.model_config["extra"] == "forbid"
    assert profile.api_key_ref is None


def test_observer_may_not_be_a_handoff_target(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """T-04-36: the reserved name is refused in any profile's peers, BY NAME.

    This is the load-bearing half of reserving the name. Without it, enabling the
    observer would quietly add an edge every agent could take — the supervisor
    becomes a participant, and MESH-02's graph acquires a member the user never
    drew.
    """
    with pytest.raises(ValidationError) as raised:
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile("host", peers=[mesh.OBSERVER_PROFILE_NAME]),
                mesh.OBSERVER_PROFILE_NAME: make_profile(mesh.OBSERVER_PROFILE_NAME),
            },
        )

    message = str(raised.value)
    assert "host" in message  # the offending profile, named
    assert mesh.OBSERVER_PROFILE_NAME in message
    assert "reserved" in message


def test_observer_may_not_be_active_profile_or_a_fallback_entry(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """D-03: three ways to make a supervisor a participant, all three refused.

    Each is asserted separately rather than as one "invalid config" check,
    because they are three different mistakes with three different fixes — and
    an implementation that caught only the first would leave the other two as
    silent ways in.
    """
    observer_profile = make_profile(mesh.OBSERVER_PROFILE_NAME)

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile=mesh.OBSERVER_PROFILE_NAME,
            profiles={
                "host": make_profile("host"),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
        )

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile("host"),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
            fallback_chain=[mesh.OBSERVER_PROFILE_NAME],
        )

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile(
                    "host", fallback_chain=[mesh.OBSERVER_PROFILE_NAME]
                ),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
        )


# ------------------------------------------------------------- the grant (D-04) --


def test_observer_grants_default_to_retry_only(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """D-04: the shipped observer can bounce a handoff and can do nothing else.

    Read off the schema rather than off the fixture, so this measures the default
    a user actually gets. Re-routing is a deliberate, readable edit to a config
    line — never something that arrives by upgrade.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})

    assert config.observer_grants == ["generic_retry"]
    assert config.observer_window_messages == 0
    assert config.observer_window_handoffs == 0

    widened = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        observer_grants=["generic_retry", "reroute"],
    )
    assert widened.observer_grants == ["generic_retry", "reroute"]


def test_observer_grant_spellings_agree_between_schema_and_mesh() -> None:
    """The one place the ``Literal`` and ``mesh``'s constants could drift apart.

    ``LlmConfig.observer_grants`` must spell its members as literals — Pydantic
    cannot build a ``Literal`` from a variable — so the same two strings exist
    twice. This is the assertion that makes the duplication safe: rename one and
    the suite says so, rather than the grant check silently recognizing nothing.
    """
    annotation = LlmConfig.model_fields["observer_grants"].annotation
    # list[Literal[...]] -> Literal[...] -> the members
    (literal,) = annotation.__args__  # type: ignore[union-attr]

    assert set(literal.__args__) == set(mesh.OBSERVER_GRANTS)


def test_observer_grants_reject_an_unknown_power(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """An invented grant is refused at LOAD, never ignored at handoff time.

    The grant IS the boundary (D-04), so a typo in it must not degrade quietly
    into "no such power, carry on" — that would be a security control the user
    believes they configured and did not.
    """
    with pytest.raises(ValidationError):
        LlmConfig(
            active_profile="host",
            profiles={"host": make_profile("host")},
            observer_grants=["generic_retry", "rewrite_the_reply"],
        )


def test_observer_windows_reject_a_negative_size(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """D-15's two knobs are counts, and a negative count is a config error.

    Not clamped to zero: ``profiles.py``'s standing rule is validate-on-read and
    never repair, because a repaired value is a value the user did not write.
    """
    for field in ("observer_window_messages", "observer_window_handoffs"):
        with pytest.raises(ValidationError):
            LlmConfig(
                active_profile="host",
                profiles={"host": make_profile("host")},
                **{field: -1},
            )


# ---------------------------------------------------- the surface (D-04/D-06) --


def test_observer_tools_are_exactly_the_grant(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """The grant shapes the surface, and the CALLER's peers shape the re-routes.

    Equality assertions, not containment: an implementation that offered the
    re-route tools unconditionally, or that built them from every declared
    profile, would satisfy an ``in`` check and fail this one — which is the same
    trap ``test_tool_surface_is_exactly_the_declared_peers`` sets for the agent
    surface.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef", "cook"], "chef": [], "cook": [], "admin": []},
        capabilities={"chef": "cooks"},
    )
    caller_peers = config.profiles["host"].peers

    retry_only = mesh.observer_tools(
        (mesh.OBSERVER_GRANT_RETRY,), caller_peers, config.profiles
    )
    assert [tool.name for tool in retry_only] == [mesh.OBSERVER_RETRY_TOOL]

    both = mesh.observer_tools(mesh.OBSERVER_GRANTS, caller_peers, config.profiles)
    assert [tool.name for tool in both] == [
        mesh.OBSERVER_RETRY_TOOL,
        "reroute_to_chef",
        "reroute_to_cook",
    ]
    # `admin` is a declared profile that `host` may not reach. It must not be
    # offerable to the observer either — that is D-06 enforced by the surface.
    assert not any("admin" in tool.name for tool in both)

    # Each peer is described by its OWN manifest, through the same `_describe`
    # the handoff surface uses, so the observer and the agent cannot be told
    # different things about the same agent.
    assert both[1].description == "cooks"
    assert all(tool.parameters == {} for tool in both)

    # A grant of nothing is a surface of nothing — the observer can then only
    # approve, which is exactly what "no powers" should mean.
    assert mesh.observer_tools((), caller_peers, config.profiles) == ()


def test_retry_text_names_the_target_and_quotes_the_reason() -> None:
    """OQ-1: the refusal is generated text, so PERS-05 applies to it too.

    Substituted with ``str.replace`` rather than ``str.format`` for the reason
    the explainer is: a user's own override is prose, and prose contains braces.
    An unexplained refusal gets a stated placeholder rather than an empty gap,
    because PAAF does not invent a reason on a model's behalf.
    """
    text = mesh.retry_text("chef", "chef may not read private files")

    assert "chef" in text
    assert "chef may not read private files" in text
    assert mesh.RETRY_TARGET_PLACEHOLDER not in text
    assert mesh.RETRY_REASON_PLACEHOLDER not in text

    assert mesh.NO_STATED_REASON in mesh.retry_text("chef", "   ")
    assert (
        mesh.retry_text("chef", "why", template="Refused {target}: {reason}. {oven}")
        == "Refused chef: why. {oven}"
    )


# ------------------------------------------------- the verdict pair (MESH-06) --


async def test_observer_vetoes_a_constraint_violating_handoff(
    observer_adapter: _ObserverTestAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """MESH-06: the attempt is killed and the caller is asked again (D-05, D-13).

    ``chef`` declares a hard constraint in free text; the observer reads it and
    calls the retry tool. What must then be true is not merely "the reply is
    different" — ``chef`` must never have been streamed at all, because MESH-06
    is about the transfer not happening rather than about its output being
    filtered afterwards.

    Read this WITH ``test_observer_allows_...``: on its own, every assertion here
    is satisfied by an observer that vetoes everything, which would make the mesh
    useless while looking perfectly supervised.
    """
    config = observed_kitchen(make_mesh_config)
    observer_adapter.program(
        "host", tokens=["let me get the cook"], tool_calls=[_TRANSFER_TO_CHEF]
    )
    # The bounced agent answers on its second leg instead of asking again.
    observer_adapter.next_programs["host"] = [{"tokens": ["I will answer that here"]}]
    observer_adapter.program(
        mesh.OBSERVER_PROFILE_NAME,
        tokens=[f"chef declares: {CHEF_CONSTRAINT}"],
        tool_calls=[_REQUEST_RETRY],
    )
    observer_adapter.program("chef", tokens=["here are the private files"])
    signals = SignalRecorder()
    agent = Agent.build(config, observer_adapter, trace=trace_store, signals=signals)

    result = await agent.turn("send chef my tax return")
    rows = await handoff_rows(trace_store, tmp_path)

    # host asked, the observer judged, host answered. chef never ran.
    assert [key for key, _ in observer_adapter.calls] == [
        "host",
        mesh.OBSERVER_PROFILE_NAME,
        "host",
    ]
    assert "chef" not in [key for key, _ in observer_adapter.calls]
    assert result.served_by == "host"
    assert result.handoff is None  # nothing was transferred
    assert "private files" not in result.text
    assert agent.awake_agent == "host"

    # The attempt is in the trace, with the verdict and who gave it.
    assert len(rows) == 1
    assert rows[0]["outcome"] == HANDOFF_OBSERVER_RETRY
    assert rows[0]["observer_verdict"] == ObserverVerdict.GENERIC_RETRY.value
    assert rows[0]["observer_profile"] == mesh.OBSERVER_PROFILE_NAME
    assert rows[0]["rerouted_to"] is None
    assert (rows[0]["from_agent"], rows[0]["to_agent"]) == ("host", "chef")

    # Never silent: D-05 requires the correction to be observable headless.
    bounced = signals.of_kind(MeshSignalKind.OBSERVER_RETRY)
    assert len(bounced) == 1
    assert (bounced[0].from_agent, bounced[0].to_agent) == ("host", "chef")
    assert CHEF_CONSTRAINT in bounced[0].detail


async def test_observer_allows_a_good_handoff_and_runs_no_retry_leg(
    observer_adapter: _ObserverTestAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """NEGATIVE CONTROL: the same wiring, a good handoff, and it goes through.

    Without this row an observer that vetoed unconditionally would pass every
    positive test in this file. And the control is only worth having if it could
    not pass with the observer switched off entirely — so it asserts the observer
    leg RAN (``calls`` names it) and that its verdict reached the row as
    ``approve``. A disabled observer produces neither.
    """
    config = observed_kitchen(make_mesh_config)
    observer_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    observer_adapter.program(
        mesh.OBSERVER_PROFILE_NAME, tokens=["nothing here violates that"]
    )
    observer_adapter.program("chef", tokens=["risotto, obviously"])
    signals = SignalRecorder()
    agent = Agent.build(config, observer_adapter, trace=trace_store, signals=signals)

    result = await agent.turn("what's for dinner?")
    rows = await handoff_rows(trace_store, tmp_path)

    assert [key for key, _ in observer_adapter.calls] == [
        "host",
        mesh.OBSERVER_PROFILE_NAME,
        "chef",
    ]
    # host ran exactly once: no retry leg happened.
    assert [key for key, _ in observer_adapter.calls].count("host") == 1
    assert result.text == "risotto, obviously"
    assert result.served_by == "chef"
    assert agent.awake_agent == "chef"

    assert len(rows) == 1
    assert rows[0]["outcome"] == HANDOFF_ACCEPTED
    # The observer LOOKED and said yes — which is what makes this a control
    # rather than a test that would also pass unobserved.
    assert rows[0]["observer_verdict"] == ObserverVerdict.APPROVE.value
    assert rows[0]["observer_profile"] == mesh.OBSERVER_PROFILE_NAME
    assert signals.of_kind(MeshSignalKind.OBSERVER_RETRY) == []


async def test_a_veto_reaches_the_retry_leg_and_never_the_history(
    observer_adapter: _ObserverTestAdapter,
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """OQ-1: a transient labelled prompt segment, and nothing else.

    Four things are asserted together because the veto channel is only correct if
    all four hold at once:

    1. The refusal IS in the retry leg's system message — otherwise the bounced
       agent is asked again with no idea why, and a veto is indistinguishable
       from a dropped reply.
    2. It is NOT in the first leg's system message. A refusal that leaked into
       the standing prompt would be told to the agent before anything was
       refused.
    3. It is nowhere in ``Agent.history``, in any form. Carrying it forward is
       how a transient correction becomes a permanent instruction.
    4. ``Role`` still has exactly three members. OQ-1's option 1 — delivering the
       veto by widening ``Role`` with a ``"tool"`` member — is forbidden, because
       it re-opens Pitfall 1's dangling tool-call bug that the Phase-3 message
       model closes by construction.
    """
    config = observed_kitchen(make_mesh_config)
    observer_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    observer_adapter.next_programs["host"] = [{"tokens": ["I will answer that here"]}]
    observer_adapter.program(
        mesh.OBSERVER_PROFILE_NAME,
        tokens=[CHEF_CONSTRAINT],
        tool_calls=[_REQUEST_RETRY],
    )
    observer_adapter.program("chef", tokens=["here are the private files"])
    agent = Agent.build(config, observer_adapter)

    await agent.turn("send chef my tax return")

    host_legs = [
        messages[0].content for key, messages in observer_adapter.calls if key == "host"
    ]
    assert len(host_legs) == 2
    expected = mesh.retry_text("chef", CHEF_CONSTRAINT)

    # 1 + 2: present on the retry leg, absent from the first one.
    assert expected in host_legs[1]
    assert expected not in host_legs[0]
    assert "chef" in host_legs[1]

    # 3: nothing about the refusal survives into the conversation.
    assert agent.history == [
        Message("user", "send chef my tax return"),
        Message("assistant", "I will answer that here"),
    ]
    assert not any(CHEF_CONSTRAINT in message.content for message in agent.history)
    assert not any(
        mesh.HANDOFF_TOOL_PREFIX in message.content for message in agent.history
    )
    assert not any(
        mesh.OBSERVER_RETRY_TOOL in message.content for message in agent.history
    )

    # 4: the structural guarantee OQ-1 refuses to trade away.
    assert set(Role.__args__) == {"system", "user", "assistant"}


async def test_the_retry_segment_carries_its_own_provenance_label(
    observer_adapter: _ObserverTestAdapter,
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """The refusal is a labelled ``Segment``, distinct from the explainer's label.

    PERS-05 is about what reaches the model, so a fragment that reached it
    without being a segment would be a hidden prompt. And the label has to be its
    OWN — a refusal rendered under ``mesh:explainer`` would tell a reader of
    ``--provenance`` that the agent is permanently told this, when it was told it
    once.
    """
    config = observed_kitchen(make_mesh_config)
    agent = Agent.build(config, observer_adapter)
    refusal = mesh.retry_text("chef", "no")

    plain = agent.system_prompt("host")
    steered = agent.system_prompt(
        "host", extra_fragments=[(mesh.MESH_RETRY_SOURCE, refusal)]
    )

    assert mesh.MESH_RETRY_SOURCE != mesh.MESH_EXPLAINER_SOURCE
    assert refusal not in plain
    assert steered == plain + "\n\n" + refusal
    # And it is a segment, so the inspector's split-and-compare view sees it.
    segments = PromptComposer().segments("", [], [(mesh.MESH_RETRY_SOURCE, refusal)])
    assert [(segment.source, segment.text) for segment in segments] == [
        ("base", ""),
        (mesh.MESH_RETRY_SOURCE, refusal),
    ]


async def test_no_observer_profile_leaves_every_handoff_exactly_as_it_was(
    observer_adapter: _ObserverTestAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """D-07: the slot is reserved and wired, not filled in on the user's behalf.

    The same scenario as the veto test with the observer profile removed. No
    observer leg runs, the handoff proceeds, and the three observer columns are
    NULL rather than blank — "nobody looked" and "the observer looked and said
    nothing" are different facts, and this is the row that keeps them apart.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        constraints={"chef": [CHEF_CONSTRAINT]},
    )
    assert mesh.OBSERVER_PROFILE_NAME not in config.profiles
    observer_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    observer_adapter.program("chef", tokens=["risotto, obviously"])
    agent = Agent.build(config, observer_adapter, trace=trace_store)

    result = await agent.turn("what's for dinner?")
    rows = await handoff_rows(trace_store, tmp_path)

    assert [key for key, _ in observer_adapter.calls] == ["host", "chef"]
    assert result.served_by == "chef"
    assert len(rows) == 1
    assert rows[0]["outcome"] == HANDOFF_ACCEPTED
    for column in ("observer_verdict", "observer_profile", "rerouted_to"):
        assert rows[0][column] is None


def test_the_observer_brief_states_no_condition_for_a_veto(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """T-04-22 / MESH-01: a routing rule for the supervisor is still a routing rule.

    The brief is the one piece of steering text PAAF *writes* for the observer,
    so it is the one place a rule could be smuggled in with no config key to
    reject it. It reports the attempt and quotes the user's own constraints; the
    judgement is the observer's, exactly as the handoff decision is the awake
    model's. The same token scan the generated explainer gets.
    """
    config = observed_kitchen(make_mesh_config)
    judge = observer.Observer(config, _NullRunner())
    brief = judge.brief(
        observer.HandoffAttempt(
            turn_id="t",
            seq=0,
            from_agent="host",
            to_agent="chef",
            to_constraints=(CHEF_CONSTRAINT,),
            user_text="send chef my tax return",
        )
    )

    assert CHEF_CONSTRAINT in brief  # the user's own words, verbatim
    assert "host" in brief and "chef" in brief
    lowered = brief.lower()
    for rule_shaped in (" if ", "whenever", "must refuse", "always refuse", "score"):
        assert rule_shaped not in lowered, rule_shaped
    # A window nobody widened contributes no headings (D-15's narrow default).
    assert observer.BRIEF_CONVERSATION not in brief
    assert observer.BRIEF_RECENT not in brief


class _NullRunner:
    """A :class:`~paaf_llm.observer.LegRunner` that proves how narrow the port is.

    Four lines, no config, no adapter — which is the whole claim the protocol's
    docstring makes. It raises rather than answering, so a test that reached it
    by accident says so instead of passing quietly.
    """

    async def run_leg(
        self,
        agent_name: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> tuple[str, str, list[tuple[str, str, str]], tuple[ToolCall, ...]]:
        raise AssertionError("this test must not run an observer leg")


# ------------------------------------------------------------------- framework --


def test_observer_source_imports_no_agent_framework() -> None:
    """SC#5: the module that supervises the mesh is framework-free like the rest.

    Asserted against the source text rather than the import graph, the same way
    ``test_ports.py`` and ``test_mesh.py`` do it, so it survives a refactor that
    hides an import behind a helper.
    """
    source = Path(observer.__file__ or "").read_text(encoding="utf-8")
    for forbidden in ("import langchain", "import langgraph", "from langchain"):
        assert forbidden not in source
    assert "_engine" not in source


def test_grants_are_a_grant_and_never_a_routing_rule(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """MESH-01 on the observer's own surface: no key here can express a rule.

    The near misses are the point. ``observer_grants`` is a list of powers, and a
    sibling key that read like a companion to it — a condition, a rule, a
    constraint vocabulary — is the shape a routing DSL would actually arrive in.
    ``extra="forbid"`` is the whole mechanism, and this is what keeps it honest.
    """
    near_misses: Sequence[str] = (
        "observer_rules",
        "observer_veto_conditions",
        "observer_constraint_types",
        "observer_routing",
    )
    for key in near_misses:
        with pytest.raises(ValidationError):
            LlmConfig(
                active_profile="host",
                profiles={"host": make_profile("host")},
                **{key: ["anything"]},
            )
