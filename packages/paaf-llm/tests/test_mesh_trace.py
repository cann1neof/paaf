# SPDX-License-Identifier: Apache-2.0
"""MESH-05 / SC#4: the handoff chain is RECONSTRUCTIBLE from the local trace.

The claim under test is not "some rows were written". It is that a user who
opens their own `trace.db` after a turn that bounced through three agents can
answer three questions the moment matters:

* **Who was awake on each leg?** One ``turn_legs`` row per agent leg, ordered by
  ``leg_seq``, all correlated by one engine-generated ``turn_id``.
* **Was any leg quietly served by a fallback?** Each leg carries its OWN
  ``served_by`` and its OWN ``fallback_trail`` (SC#4). The per-leg test asserts
  two legs of one turn hold *different* trails — an assertion a single per-turn
  row structurally cannot satisfy, which is what stops a global-trail
  implementation from passing (T-04-27).
* **What was attempted, including what was refused?** A rejected handoff
  produces no ``runs`` row and no ``turn_legs`` row at all, so without the
  ``handoffs`` table a wrong reroute is not merely hard to find — it is invisible,
  in exactly the case MESH-05 was written for (T-04-26).

**Why correlation lives in ``turn_legs`` rather than in a ``runs.turn_id``
column.** ``paaf-trace`` applies its whole schema with one ``executescript`` of
``CREATE TABLE IF NOT EXISTS``; there is no version table and no migration
runner. A column added to ``runs`` is therefore a silent no-op on any database
that already has that table — perfect on a fresh DB, and every mesh write failing
with ``no column named turn_id`` on the machine of anyone who has run ``paaf
chat`` since Phase 3 (RESEARCH Pitfall 5, reproduced out-of-band by plan 04-02).

Every row here is read back with the **standard library** ``sqlite3``, not
through ``paaf_trace``: a store that never wrote anything can always satisfy its
own reader. And ``store.dropped == 0`` is asserted on every path, because a
bounded queue that silently shed the event under test would leave a read that
proves nothing.

Every test runs against the shipped fake with the agent framework uninstalled
(SC#5), and none of them opens a socket.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from paaf_llm.agent import Agent
from paaf_llm.fake import FakeAdapter
from paaf_llm.ports import (
    Message,
    ServerError,
    ToolCall,
    ToolSpec,
    UndeclaredPeer,
)
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_trace.store import TraceStore

_TRANSFER_TO_A = ToolCall("transfer_to_a", {})
_TRANSFER_TO_B = ToolCall("transfer_to_b", {})
_TRANSFER_TO_CHEF = ToolCall("transfer_to_chef", {})
_TRANSFER_TO_ADMIN = ToolCall("transfer_to_admin", {})

#: The three tables one turn can touch, each with the order its rows are MEANT
#: to be read in. Spelled out as literal statements rather than built from a
#: table name, so nothing here can ever interpolate into SQL — and so the set of
#: tables this module claims to cover is stated in one place.
_QUERIES = {
    "runs": "SELECT * FROM runs ORDER BY id",
    "turn_legs": "SELECT * FROM turn_legs ORDER BY leg_seq",
    "handoffs": "SELECT * FROM handoffs ORDER BY seq",
}

#: Columns plan 04-07's observer fills. Until it exists they must be NULL rather
#: than an empty string: "nobody looked at this handoff" and "the observer looked
#: and said nothing" are different facts, and D-07 turns on the difference.
OBSERVER_COLUMNS = ("observer_verdict", "observer_profile", "rerouted_to")


class _LegScriptedAdapter(FakeAdapter):
    """A fake that can answer differently on a SECOND leg, and refuses to run away.

    Deliberately a local twin of ``test_mesh.py``'s ``MeshTestAdapter`` rather
    than an import of it. Both files are force-included into the wheel and run
    flat under ``pytest --pyargs paaf_llm``, where a cross-test-module import
    would couple two shipped test files through ``sys.path`` — a coupling that
    works locally and is a different thing entirely in the clean-venv gate that
    SC#5 is stated in terms of.

    Two behaviors, both required by the scenarios below:

    **A per-leg script queue.** :meth:`FakeAdapter.program` is static per profile
    on purpose — a program is a fact about a provider, not a queue — but A→B→A
    needs ``a`` to hand off on its first leg and to *answer* on its second. The
    re-program lands AFTER the leg fully drained, so the tool calls that leg
    published are the ones it was scripted with.

    **A hard leg cap.** The exhaustion test scripts a mesh that hands off
    forever. An engine that failed to withdraw the tools would not fail that
    test — it would never return, and a hung suite reads as an infrastructure
    problem rather than as the missing wall it actually is.
    """

    #: Far above any budget under test: it must never be the thing that ends a
    #: turn a correct engine would have ended itself.
    MAX_LEGS = 20

    def __init__(self) -> None:
        super().__init__()
        #: profile key -> queued ``program(...)`` kwargs, one per subsequent leg.
        self.next_programs: dict[str, list[dict[str, Any]]] = {}
        self.legs = 0

    def _count_leg(self) -> None:
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


@pytest.fixture
def leg_adapter() -> _LegScriptedAdapter:
    """A fresh :class:`_LegScriptedAdapter` per test — no script outlives a test."""
    return _LegScriptedAdapter()


async def drained(store: TraceStore, tmp_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Stop the writer, then read all three tables back off disk.

    ``stop()`` flushes the bounded queue and is idempotent, so the ``trace_store``
    fixture's own teardown stays safe. That the rows are readable AFTER it
    returned is itself the proof the writer drained rather than being abandoned.
    """
    await store.stop()
    assert store.dropped == 0, "a trace event was dropped — the read proves nothing"
    connection = sqlite3.connect(str(tmp_path / "trace.db"))
    try:
        connection.row_factory = sqlite3.Row
        return {
            table: [dict(row) for row in connection.execute(query).fetchall()]
            for table, query in _QUERIES.items()
        }
    finally:
        connection.close()


def assert_engine_generated(turn_id: object) -> None:
    """Assert ``turn_id`` is a uuid4 hex string and could not be a row id.

    Finding 5, asserted rather than trusted. The fire-and-forget writer never
    surfaces ``lastrowid``, so correlating on one would force a writer redesign —
    and the wrong implementation (``turn_id`` = ``1``, ``2``, ``3``) looks
    perfectly plausible in a single-turn test. 32 hex characters cannot be one.
    """
    assert isinstance(turn_id, str)
    assert len(turn_id) == 32
    int(turn_id, 16)  # raises if it is not hex


def one_turn_id(rows: list[dict[str, Any]]) -> str:
    """Return the single ``turn_id`` shared by ``rows``, asserting there is one."""
    ids = {row["turn_id"] for row in rows}
    assert len(ids) == 1, f"expected one correlated turn, got {sorted(ids)}"
    turn_id = ids.pop()
    assert_engine_generated(turn_id)
    return turn_id


def loop_forever(adapter: FakeAdapter) -> None:
    """Script ``a`` and ``b`` to hand off to each other on every leg they can."""
    adapter.program("a", tokens=["a speaking"], tool_calls=[_TRANSFER_TO_B])
    adapter.program("b", tokens=["b speaking"], tool_calls=[_TRANSFER_TO_A])


# --------------------------------------------------------------------- legs --


async def test_legs_of_a_single_agent_turn_are_one_row_with_no_attempt(
    fake_adapter: FakeAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """The control: a turn with no handoff is Phase-3 behavior plus correlation.

    One leg is one ``runs`` row — the Phase-3 contract, unmoved — plus one
    ``turn_legs`` row that says who that leg belonged to. Zero ``handoffs`` rows,
    because nothing was attempted: a design that wrote an attempt row per turn
    would make "every handoff is recorded" true and useless.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=["I can answer that myself"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    await agent.turn("what time is it?")
    rows = await drained(trace_store, tmp_path)

    assert len(rows["runs"]) == 1
    assert len(rows["turn_legs"]) == 1
    assert rows["handoffs"] == []

    leg = rows["turn_legs"][0]
    assert (leg["leg_seq"], leg["agent"], leg["served_by"]) == (0, "host", "host")
    # An empty trail writes "[]" rather than NULL — "its own profile served it"
    # is a fact worth recording, not an absence. Same rule `runs` already keeps.
    assert leg["fallback_trail"] == "[]"
    assert rows["runs"][0]["served_by"] == "host"
    assert_engine_generated(leg["turn_id"])


async def test_legs_share_one_turn_id_and_are_ordered_by_leg_seq(
    leg_adapter: _LegScriptedAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """A→B→A is three legs, three rows, one turn, in order (MESH-05, OQ-5).

    ``a`` appearing at ``leg_seq`` 0 and 2 is the load-bearing shape: it is what
    makes "which agent was awake" a per-LEG question rather than a per-turn one,
    and an implementation keyed on the agent name instead of the ordinal would
    collapse the two rows into one story.
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]})
    leg_adapter.program("a", tokens=[], tool_calls=[_TRANSFER_TO_B])
    leg_adapter.next_programs["a"] = [{"tokens": ["risotto, obviously"]}]
    leg_adapter.program("b", tokens=[], tool_calls=[_TRANSFER_TO_A])
    agent = Agent.build(config, leg_adapter, trace=trace_store)

    result = await agent.turn("what's for dinner?")
    rows = await drained(trace_store, tmp_path)

    assert result.served_by == "a"
    assert [key for key, _messages in leg_adapter.calls] == ["a", "b", "a"]

    # One runs row per LEG, not per turn — the Phase-3 row multiplied by legs.
    assert len(rows["runs"]) == 3
    legs = rows["turn_legs"]
    assert [leg["leg_seq"] for leg in legs] == [0, 1, 2]
    assert [leg["agent"] for leg in legs] == ["a", "b", "a"]
    assert [leg["served_by"] for leg in legs] == ["a", "b", "a"]

    # One turn, and the attempts that produced it hang off the same id.
    turn_id = one_turn_id(legs)
    assert one_turn_id(rows["handoffs"]) == turn_id
    assert [leg["ended_at"] >= leg["started_at"] for leg in legs] == [True] * 3


async def test_legs_carry_their_own_per_agent_fallback_trail(
    fake_adapter: FakeAdapter,
    make_profile: Callable[..., ModelProfile],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """SC#4 in the trace: two legs of one turn hold DIFFERENT trails (T-04-27).

    This is the assertion a per-turn row structurally cannot satisfy. ``a`` is
    degraded and is rescued by its own chain; ``b`` answers on the first try. An
    implementation that wrote one row for the turn would attribute ``a``'s
    fallback to the whole conversation — or, worse, lose it entirely, because the
    answering leg is ``b`` and ``b`` never fell back. Either way the wrong reroute
    stops being attributable, which is the whole of what MESH-05 buys.
    """
    config = LlmConfig(
        active_profile="a",
        profiles={
            "a": make_profile("a", peers=["b"], fallback_chain=["a_backup"]),
            "a_backup": make_profile("a_backup", peers=["b"]),
            "b": make_profile("b"),
        },
    )
    fake_adapter.program("a", fail=ServerError)
    fake_adapter.program("a_backup", tokens=[], tool_calls=[_TRANSFER_TO_B])
    fake_adapter.program("b", tokens=["b answers"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    await agent.turn("hi")
    rows = await drained(trace_store, tmp_path)

    legs = rows["turn_legs"]
    assert [leg["agent"] for leg in legs] == ["a", "b"]
    assert [leg["served_by"] for leg in legs] == ["a_backup", "b"]

    # The trails are per-leg, and they DIFFER — the point of the whole table.
    assert json.loads(legs[0]["fallback_trail"]) == [
        {"from": "a", "to": "a_backup", "reason": "http_5xx"}
    ]
    assert json.loads(legs[1]["fallback_trail"]) == []
    assert legs[0]["fallback_trail"] != legs[1]["fallback_trail"]

    # The `runs` rows say the same thing from the other side of the join.
    assert [run["served_by"] for run in rows["runs"]] == ["a_backup", "b"]
    assert [run["fallback_trail"] for run in rows["runs"]] == [
        legs[0]["fallback_trail"],
        legs[1]["fallback_trail"],
    ]


# ----------------------------------------------------------------- attempts --


async def test_attempts_record_each_accepted_handoff_in_order(
    leg_adapter: _LegScriptedAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """Two hops, two attempt rows, in the order they happened (MESH-05).

    The observer columns are asserted NULL rather than ignored: plan 04-07 fills
    them, and until it does, a row that carried an empty string there would read
    as "the observer looked and said nothing" instead of "nobody looked" (D-07).
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]})
    leg_adapter.program("a", tokens=[], tool_calls=[_TRANSFER_TO_B])
    leg_adapter.next_programs["a"] = [{"tokens": ["risotto, obviously"]}]
    leg_adapter.program("b", tokens=[], tool_calls=[_TRANSFER_TO_A])
    agent = Agent.build(config, leg_adapter, trace=trace_store)

    await agent.turn("what's for dinner?")
    rows = await drained(trace_store, tmp_path)

    attempts = rows["handoffs"]
    assert [attempt["seq"] for attempt in attempts] == [0, 1]
    assert [attempt["from_agent"] for attempt in attempts] == ["a", "b"]
    assert [attempt["to_agent"] for attempt in attempts] == ["b", "a"]
    assert [attempt["outcome"] for attempt in attempts] == ["accepted", "accepted"]
    for attempt in attempts:
        assert all(attempt[column] is None for column in OBSERVER_COLUMNS)
        assert attempt["at"] is not None
    assert one_turn_id(attempts) == one_turn_id(rows["turn_legs"])


async def test_attempts_record_a_rejected_target_with_null_observer_columns(
    fake_adapter: FakeAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """T-04-26: the refused handoff is the one that would otherwise vanish.

    ``admin`` is a declared profile that ``host`` may not reach, so the guard
    refuses it and no leg for ``admin`` ever runs — which means no ``runs`` row
    and no ``turn_legs`` row exists to record that anything was tried. Without
    this attempt row the user's own trace of the turn would be indistinguishable
    from a turn on which the model never tried to hand off at all.

    The row is written BEFORE ``UndeclaredPeer`` is re-raised, which is the only
    ordering that survives the exception.
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": [], "admin": []}
    )
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_ADMIN])
    fake_adapter.program("admin", tokens=["root shell, coming right up"])
    agent = Agent.build(config, fake_adapter, trace=trace_store)

    with pytest.raises(UndeclaredPeer):
        await agent.turn("give me the admin panel")
    rows = await drained(trace_store, tmp_path)

    assert len(rows["handoffs"]) == 1
    attempt = rows["handoffs"][0]
    assert attempt["seq"] == 0
    assert attempt["from_agent"] == "host"
    # The target the MODEL named, not a target the graph allowed.
    assert attempt["to_agent"] == "admin"
    assert attempt["outcome"] == "undeclared_peer"
    assert "admin" in attempt["detail"]  # what was attempted
    assert "chef" in attempt["detail"]  # what was actually reachable
    assert all(attempt[column] is None for column in OBSERVER_COLUMNS)

    # The leg that never ran left no row — and the leg that DID ran is there,
    # correlated to the attempt, so the refusal is readable in context.
    assert [leg["agent"] for leg in rows["turn_legs"]] == ["host"]
    assert len(rows["runs"]) == 1
    assert attempt["turn_id"] == rows["turn_legs"][0]["turn_id"]


async def test_attempts_record_the_budget_exhaustion_at_the_wall(
    leg_adapter: _LegScriptedAdapter,
    make_mesh_config: Callable[..., LlmConfig],
    trace_store: TraceStore,
    tmp_path: Path,
) -> None:
    """D-08 / T-04-13: hitting the wall is an attempt-shaped fact, not a silence.

    A turn that quietly stopped hopping is indistinguishable, in a trace, from
    one that never wanted to hop again — so the wall writes its own row, after
    the accepted attempt that spent the last of the budget. ``from_agent`` and
    ``to_agent`` are the same agent because nobody took over: with no
    ``default_agent`` declared, the moves simply ran out (OQ-2).
    """
    config = make_mesh_config(active="a", peers={"a": ["b"], "b": ["a"]}, hop_budget=3)
    assert config.default_agent is None
    loop_forever(leg_adapter)
    agent = Agent.build(config, leg_adapter, trace=trace_store)

    await agent.turn("keep going")
    rows = await drained(trace_store, tmp_path)

    # Four legs (a, b, a, b): three hops, then the final leg with no moves left.
    assert [leg["agent"] for leg in rows["turn_legs"]] == ["a", "b", "a", "b"]
    assert len(rows["runs"]) == 4

    attempts = rows["handoffs"]
    assert [attempt["outcome"] for attempt in attempts] == [
        "accepted",
        "accepted",
        "accepted",
        "budget_exhausted",
    ]
    assert [attempt["seq"] for attempt in attempts] == [0, 1, 2, 3]

    wall = attempts[-1]
    assert (wall["from_agent"], wall["to_agent"]) == ("b", "b")
    assert wall["detail"] == "3"  # the budget that was spent, named
    assert all(wall[column] is None for column in OBSERVER_COLUMNS)
    assert one_turn_id(attempts) == one_turn_id(rows["turn_legs"])


async def test_attempts_and_legs_are_absent_without_a_trace_store(
    fake_adapter: FakeAdapter, make_mesh_config: Callable[..., LlmConfig]
) -> None:
    """Tracing stays opt-in: an agent built without a sink serves a mesh turn.

    The ``if self._trace is None: return`` guard covers three emit sites now
    rather than one, and a turn that raised because one of them assumed a store
    would be a headline regression on the shipped ``paaf chat`` path, which runs
    with no ``--trace-db`` by default.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})
    fake_adapter.program("host", tokens=[], tool_calls=[_TRANSFER_TO_CHEF])
    fake_adapter.program("chef", tokens=["risotto"])

    result = await Agent.build(config, fake_adapter).turn("dinner?")

    assert result.text == "risotto"
    assert result.served_by == "chef"
