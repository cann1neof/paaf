# SPDX-License-Identifier: Apache-2.0
"""Schema tests (TRACE-02, TRACE-03).

Apply ``schema.sql`` to a fresh in-memory aiosqlite DB and interrogate the resulting
tables via ``PRAGMA table_info``. These assertions pin the durable trace contract the
desktop Logs page and the Plan 09 TTFA gate both depend on:
  * ``runs.time_to_first_audio`` exists and is declared REAL (first-class metric).
  * every TRACE-02 column (prompts, model, timings, both token counts) is present.
  * ``tool_calls`` carries name/args/results plus a run foreign key.

Plus the Phase-4 reopen case (MESH-05, RESEARCH Pitfall 5): applying today's schema to a
database file that was created BEFORE Phase 4 must add the new tables and lose nothing.
"""

from __future__ import annotations

import sqlite3

import aiosqlite
from paaf_trace import read_schema
from paaf_trace.store import HandoffEvent, RunEvent, TraceStore, TurnLegEvent

# The Phase-3 schema, verbatim and INLINE. Deliberately not read from schema.sql: a test
# that builds "the old database" out of today's DDL would silently start testing the new
# schema against itself the moment the schema changes, and would go green precisely in
# the case it exists to catch.
_PHASE3_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prompts             TEXT,
    model               TEXT,
    started_at          REAL,
    ended_at            REAL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    time_to_first_audio REAL,
    served_by           TEXT,
    fallback_trail      TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id),
    name    TEXT NOT NULL,
    args    TEXT,
    results TEXT
);
"""


async def _table_columns(table: str) -> dict[str, str]:
    """Return {column_name: declared_type_upper} for ``table`` under the schema."""
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        async with db.execute(f"PRAGMA table_info({table})") as cur:
            rows = await cur.fetchall()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return {row[1]: (row[2] or "").upper() for row in rows}


async def test_ttfa_column() -> None:
    """runs has a column named exactly ``time_to_first_audio`` of declared type REAL."""
    cols = await _table_columns("runs")
    assert "time_to_first_audio" in cols
    assert cols["time_to_first_audio"] == "REAL"


async def test_runs_trace02_columns() -> None:
    """runs records prompts, model, timings, and both token counts (TRACE-02)."""
    cols = await _table_columns("runs")
    for required in (
        "prompts",
        "model",
        "started_at",
        "ended_at",
        "prompt_tokens",
        "completion_tokens",
    ):
        assert required in cols, f"runs missing TRACE-02 column: {required}"


async def test_tool_calls_columns_and_fk() -> None:
    """tool_calls records name/args/results and carries a run foreign key (TRACE-02)."""
    cols = await _table_columns("tool_calls")
    for required in ("name", "args", "results", "run_id"):
        assert required in cols, f"tool_calls missing column: {required}"

    # The FK to runs is declared (PRAGMA foreign_key_list reports the edge).
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        async with db.execute("PRAGMA foreign_key_list(tool_calls)") as cur:
            fks = await cur.fetchall()
    # foreign_key_list columns: (id, seq, table, from, to, ...)
    assert any(fk[2] == "runs" and fk[3] == "run_id" for fk in fks)


async def test_both_tables_exist() -> None:
    """Applying the schema creates both the runs and tool_calls tables."""
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ) as cur:
            names = {row[0] for row in await cur.fetchall()}
    assert {"runs", "tool_calls"} <= names


async def test_reopen_pre_phase4_database_gains_mesh_tables_and_loses_nothing(
    tmp_path,
) -> None:
    """A trace.db that already exists gains handoffs + turn_legs and keeps its rows.

    This is the ONLY test in the suite that can catch RESEARCH Pitfall 5. Every other
    trace test starts from ``tmp_path``, so every other test opens a database that never
    existed before — and ``CREATE TABLE IF NOT EXISTS`` always succeeds on a fresh file.
    The store's whole schema step is one ``executescript(read_schema())``: there is no
    version table, no ``ALTER TABLE``, and no migration runner. On a database that
    already has a ``runs`` table, an added COLUMN is therefore a silent no-op, and every
    write naming it fails at runtime with ``no column named ...`` on the user's machine
    while CI stays green. New TABLES do not have that failure mode, and this test is the
    proof — run against a real pre-Phase-4 file, not a fixture.
    """
    db_path = str(tmp_path / "trace.db")

    # 1. Build the pre-Phase-4 database by hand and put a row in it.
    old = sqlite3.connect(db_path)
    try:
        old.executescript(_PHASE3_SCHEMA)
        old.execute(
            "INSERT INTO runs (id, prompts, model, served_by) VALUES (?, ?, ?, ?)",
            (1, "a run from before phase 4", "qwen3", "kitchen-local"),
        )
        old.commit()
        tables_before = {
            row[0]
            for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        old.close()
    assert "handoffs" not in tables_before and "turn_legs" not in tables_before, (
        "the pre-Phase-4 fixture already had the mesh tables — it is not pre-Phase-4"
    )

    # 2. Open the SAME path with today's store and write all three record types.
    store = TraceStore(db_path)
    await store.start()
    store.emit(RunEvent(id=2, prompts="a run from after", model="qwen3"))
    store.emit(
        TurnLegEvent(turn_id="t0", leg_seq=0, agent="host", served_by="host-cloud")
    )
    store.emit(
        HandoffEvent(
            turn_id="t0", seq=0, from_agent="host", to_agent="chef", outcome="accepted"
        )
    )
    await store.stop()
    assert store.dropped == 0, "an event was dropped — the reopen proves nothing"

    # 3. Nothing lost, both new tables present, all three new records readable.
    db = sqlite3.connect(db_path)
    try:
        tables_after = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        runs = list(db.execute("SELECT id, prompts, served_by FROM runs ORDER BY id"))
        legs = list(
            db.execute("SELECT turn_id, leg_seq, agent, served_by FROM turn_legs")
        )
        attempts = list(
            db.execute("SELECT turn_id, seq, to_agent, outcome FROM handoffs")
        )
    finally:
        db.close()

    assert {"handoffs", "turn_legs"} <= tables_after
    assert runs[0] == (1, "a run from before phase 4", "kitchen-local"), (
        "the pre-existing run row was altered or lost by applying the Phase-4 schema"
    )
    assert runs[1] == (2, "a run from after", None)
    assert legs == [("t0", 0, "host", "host-cloud")]
    assert attempts == [("t0", 0, "chef", "accepted")]
