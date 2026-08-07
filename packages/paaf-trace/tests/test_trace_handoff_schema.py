# SPDX-License-Identifier: Apache-2.0
"""Handoff-chain schema tests (MESH-05, OQ-5, SC#4).

A multi-agent turn is several legs. Each leg is answered by a different agent, each
applies its OWN fallback chain, and some handoff attempts are REJECTED and produce no
answering leg at all. MESH-05 says all of that has to be readable afterwards out of the
user's own local trace — so a wrong reroute is observable rather than a thing they have
to take on faith.

Shape under test: two NEW tables (``turn_legs``, ``handoffs``), both FK-free, correlated
by an engine-generated ``turn_id``. New tables rather than new columns on ``runs``
because the store's entire schema step is one ``executescript`` of
``CREATE TABLE IF NOT EXISTS`` with no version table and no migration runner — a widened
table is a silent no-op on a DB that already exists (RESEARCH Pitfall 5). FK-free because
the fire-and-forget writer never surfaces ``lastrowid``, the same documented reason
``fallback_trail`` was denormalized onto ``runs`` in Phase 3.

**The round-trip matters more than the column list.** A column-presence assertion proves
the DDL parses; it does not prove a record survives the queue, the writer, and the commit.
Pitfall 5's failure mode is precisely one where the columns look right and every emit is
silently dropped — so every round-trip here also asserts ``store.dropped == 0``, without
which a queue that ate the record would still read green.
"""

from __future__ import annotations

import sqlite3

import aiosqlite
from paaf_trace import read_schema
from paaf_trace.store import HandoffEvent, RunEvent, TraceStore, TurnLegEvent

_TURN = "9f2c1ab34d5e4f6789ab0123456789cd"  # an engine uuid4 hex, never a rowid
_HOST_TRAIL = '[{"from": "host-local", "to": "host-cloud", "reason": "http_5xx"}]'
_CHEF_TRAIL = '[{"from": "chef-local", "to": "chef-cloud", "reason": "timeout"}]'


async def _table_columns(table: str) -> dict[str, str]:
    """Return {column_name: declared_type_upper} for ``table`` under the schema."""
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        async with db.execute(f"PRAGMA table_info({table})") as cur:
            rows = await cur.fetchall()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return {row[1]: (row[2] or "").upper() for row in rows}


async def test_mesh_tables_declare_every_column_the_phase_will_need() -> None:
    """turn_legs and handoffs carry every declared column, with the declared type.

    Exhaustive on purpose. The observer columns (``observer_verdict``,
    ``observer_profile``, ``rerouted_to``) belong to plan 04-07 and are unused today;
    they are asserted here because there is no path to add them later — a column added
    to an existing table is a no-op under ``CREATE TABLE IF NOT EXISTS``.
    """
    legs = await _table_columns("turn_legs")
    for name, declared in {
        "turn_id": "TEXT",
        "leg_seq": "INTEGER",
        "agent": "TEXT",
        "served_by": "TEXT",
        "fallback_trail": "TEXT",
        "started_at": "REAL",
        "ended_at": "REAL",
        "prompt_tokens": "INTEGER",
        "completion_tokens": "INTEGER",
    }.items():
        assert name in legs, f"turn_legs missing MESH-05 column: {name}"
        assert legs[name] == declared, (
            f"turn_legs.{name} declared {legs[name]!r}, expected {declared!r}"
        )

    attempts = await _table_columns("handoffs")
    for name, declared in {
        "turn_id": "TEXT",
        "seq": "INTEGER",
        "from_agent": "TEXT",
        "to_agent": "TEXT",
        "outcome": "TEXT",
        "observer_verdict": "TEXT",
        "observer_profile": "TEXT",
        "rerouted_to": "TEXT",
        "detail": "TEXT",
        "at": "REAL",
    }.items():
        assert name in attempts, f"handoffs missing MESH-05 column: {name}"
        assert attempts[name] == declared, (
            f"handoffs.{name} declared {attempts[name]!r}, expected {declared!r}"
        )


async def test_mesh_tables_carry_no_foreign_key() -> None:
    """Neither new table references runs — the writer never surfaces lastrowid.

    An FK to ``runs`` would be unfillable (no producer can learn the run id) and, with
    ``PRAGMA foreign_keys=ON``, every mesh insert would fail the constraint. Correlation
    is by ``turn_id`` instead. A rejected attempt has no ``runs`` row to point at at all.
    """
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        for table in ("handoffs", "turn_legs"):
            async with db.execute(f"PRAGMA foreign_key_list({table})") as cur:
                assert await cur.fetchall() == [], (
                    f"{table} declares a FOREIGN KEY; the fire-and-forget writer "
                    "cannot fill one (RESEARCH Finding 5 / Pitfall 5)"
                )
        # The FK the store DOES rely on is untouched.
        async with db.execute("PRAGMA foreign_key_list(tool_calls)") as cur:
            assert await cur.fetchall() != []


def test_mesh_events_are_placeholder_param_balanced() -> None:
    """Both event types name their columns explicitly and never interpolate (T-04-06).

    ``to_agent`` and ``detail`` carry model-influenced text straight into SQL. If someone
    ever builds one of these queries by f-string, the inlined value disappears from
    ``params`` and this balance check goes red. The bare rejected shape is included
    because that is the construction with the most defaulted fields and therefore the
    one most likely to drift out of alignment with the column list.
    """
    sql, params = HandoffEvent(
        turn_id=_TURN,
        seq=1,
        from_agent="host",
        to_agent="admin",
        outcome="undeclared_peer",
        detail="admin is not a declared peer of host",
        at=1234.5,
    ).as_sql()
    assert sql.count("?") == len(params)
    for column in ("turn_id", "seq", "outcome", "observer_verdict", "rerouted_to"):
        assert column in sql

    # A bare rejection: no observer, no reroute, no timing.
    bare_sql, bare_params = HandoffEvent(turn_id=_TURN, seq=0).as_sql()
    assert bare_sql.count("?") == len(bare_params)
    assert bare_params.count(None) == len(bare_params) - 2  # only the two keys are set

    leg_sql, leg_params = TurnLegEvent(
        turn_id=_TURN,
        leg_seq=1,
        agent="chef",
        served_by="chef-cloud",
        fallback_trail="[]",
    ).as_sql()
    assert leg_sql.count("?") == len(leg_params)
    for column in ("turn_id", "leg_seq", "agent", "served_by", "fallback_trail"):
        assert column in leg_sql

    bare_leg_sql, bare_leg_params = TurnLegEvent(turn_id=_TURN, leg_seq=0).as_sql()
    assert bare_leg_sql.count("?") == len(bare_leg_params)


async def test_handoff_chain_roundtrips_through_a_real_store(tmp_path) -> None:
    """A whole turn — two legs, one accepted and one rejected attempt — reads back.

    This is the assertion the column list cannot make: the records survive the bounded
    queue, the single writer, and the commit. ``store.dropped == 0`` is load-bearing —
    an overflow that silently ate every record would otherwise leave a passing test.
    """
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()
    store.emit(
        HandoffEvent(
            turn_id=_TURN,
            seq=0,
            from_agent="host",
            to_agent="chef",
            outcome="accepted",
            at=1000.0,
        )
    )
    store.emit(
        HandoffEvent(
            turn_id=_TURN,
            seq=1,
            from_agent="chef",
            to_agent="admin",
            outcome="undeclared_peer",
            detail="admin is not a declared peer of chef",
            at=1001.0,
        )
    )
    store.emit(
        TurnLegEvent(
            turn_id=_TURN,
            leg_seq=0,
            agent="host",
            served_by="host-cloud",
            fallback_trail=_HOST_TRAIL,
            prompt_tokens=11,
        )
    )
    store.emit(
        TurnLegEvent(
            turn_id=_TURN,
            leg_seq=1,
            agent="chef",
            served_by="chef-cloud",
            fallback_trail=_CHEF_TRAIL,
            prompt_tokens=22,
        )
    )
    await store.stop()
    assert store.dropped == 0, "an event was dropped — the round-trip proves nothing"

    db = sqlite3.connect(db_path)
    try:
        attempts = list(
            db.execute(
                "SELECT seq, from_agent, to_agent, outcome, observer_verdict, "
                "observer_profile, rerouted_to, detail FROM handoffs "
                "WHERE turn_id = ? ORDER BY seq",
                (_TURN,),
            )
        )
        legs = list(
            db.execute(
                "SELECT leg_seq, agent, served_by, fallback_trail, prompt_tokens "
                "FROM turn_legs WHERE turn_id = ? ORDER BY leg_seq",
                (_TURN,),
            )
        )
    finally:
        db.close()

    assert len(attempts) == 2
    accepted, rejected = attempts
    assert accepted[:4] == (0, "host", "chef", "accepted")

    # The rejected attempt is the whole point of the table: it produced no runs row and
    # no turn_legs row, so without this it would be invisible (T-04-07).
    assert rejected[:4] == (1, "chef", "admin", "undeclared_peer")
    assert rejected[4] is None, "observer_verdict must be NULL when unobserved (D-07)"
    assert rejected[5] is None, "observer_profile must be NULL when unobserved"
    assert rejected[6] is None, "a rejection nobody corrected has no rerouted_to (D-05)"
    assert rejected[7] == "admin is not a declared peer of chef"

    # Per-agent fallback provenance: two legs of ONE turn, each with its own trail (SC#4).
    assert [row[0] for row in legs] == [0, 1], "legs must read back in leg_seq order"
    assert [row[1] for row in legs] == ["host", "chef"]
    assert legs[0][2] != legs[1][2], "each leg records the profile that served IT"
    assert (legs[0][2], legs[1][2]) == ("host-cloud", "chef-cloud")
    assert legs[0][3] != legs[1][3], "a per-turn trail would collapse these into one"
    assert (legs[0][3], legs[1][3]) == (_HOST_TRAIL, _CHEF_TRAIL)
    assert (legs[0][4], legs[1][4]) == (11, 22)


async def test_phase3_run_event_still_writes_unchanged(tmp_path) -> None:
    """Backward-compat control: a Phase-3 RunEvent is unaffected by the new tables.

    Constructed POSITIONALLY over the ten fields Phase 3 ended with. The mesh tables were
    added beside ``runs``, not to it — if anything in this plan had reached into the
    ``runs`` block or into ``RunEvent``'s field order, this binds wrongly or raises.
    """
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()
    store.emit(RunEvent(1, "hello", "local-model", 1.0, 2.0, 11, 22, 0.5, None, None))
    await store.stop()
    assert store.dropped == 0

    db = sqlite3.connect(db_path)
    try:
        rows = list(
            db.execute(
                "SELECT prompts, model, time_to_first_audio, served_by, fallback_trail "
                "FROM runs WHERE id = 1"
            )
        )
    finally:
        db.close()
    assert rows == [("hello", "local-model", 0.5, None, None)]
