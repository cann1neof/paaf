# SPDX-License-Identifier: Apache-2.0
"""Fallback-provenance schema tests (MODEL-04, D-06, SC#4).

The fallback engine (plan 03-06) needs an authoritative, after-the-fact record of
*which profile actually served a run* and *every fallback hop that preceded it* — so a
wrong reroute or a silently-degraded provider is observable in the user's own local
trace, never hidden.

Shape under test: two DENORMALIZED columns on ``runs`` (``served_by`` + ``fallback_trail``),
not a child ``fallbacks`` table. The Phase-2 writer is fire-and-forget and never surfaces
``lastrowid`` (RESEARCH Pitfall 5), so an FK child table would force a writer redesign.

These assertions pin:
  * both columns exist on ``runs`` and are declared TEXT;
  * ``RunEvent.as_sql()`` widened consistently (columns == placeholders == params);
  * a populated trail survives a real TraceStore write/read round-trip;
  * a run that NEVER fell back is still writable (the backward-compat control — the
    additive columns must not make the pre-existing RunEvent shape unwritable).
"""

from __future__ import annotations

import aiosqlite
from paaf_trace import read_schema
from paaf_trace.store import RunEvent, TraceStore

_TRAIL = '[{"from": "kitchen-local", "to": "cloud", "reason": "http_5xx"}]'


async def _table_columns(table: str) -> dict[str, str]:
    """Return {column_name: declared_type_upper} for ``table`` under the schema."""
    async with aiosqlite.connect(":memory:") as db:
        await db.executescript(read_schema())
        async with db.execute(f"PRAGMA table_info({table})") as cur:
            rows = await cur.fetchall()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    return {row[1]: (row[2] or "").upper() for row in rows}


async def test_fallback_columns_exist() -> None:
    """runs carries served_by and fallback_trail, both declared TEXT (D-06/SC#4)."""
    cols = await _table_columns("runs")
    for required in ("served_by", "fallback_trail"):
        assert required in cols, f"runs missing fallback-provenance column: {required}"
        assert cols[required] == "TEXT", (
            f"runs.{required} declared {cols[required]!r}, expected TEXT"
        )


def test_run_event_sql_widened_consistently() -> None:
    """RunEvent.as_sql() names both new columns and stays placeholder/param balanced."""
    sql, params = RunEvent(
        id=1,
        served_by="cloud",
        fallback_trail='[{"from":"kitchen-local","to":"cloud","reason":"http_5xx"}]',
    ).as_sql()
    assert "served_by" in sql
    assert "fallback_trail" in sql
    assert sql.count("?") == len(params)


async def _write_and_read(tmp_path, event: RunEvent) -> tuple[object, object]:
    """Emit ``event`` through a real TraceStore, then read (served_by, fallback_trail)."""
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()
    store.emit(event)
    await store.stop()
    assert store.dropped == 0, "event was dropped — the round-trip proves nothing"

    async with (
        aiosqlite.connect(db_path) as db,
        db.execute("SELECT served_by, fallback_trail FROM runs") as cur,
    ):
        rows = await cur.fetchall()
    assert len(rows) == 1, f"expected exactly one run row, got {len(rows)}"
    return rows[0][0], rows[0][1]


async def test_fallback_trail_roundtrip(tmp_path) -> None:
    """served_by + the trail JSON survive a real store write and read back intact."""
    served_by, trail = await _write_and_read(
        tmp_path,
        RunEvent(
            prompts="hello",
            model="cloud-model",
            served_by="cloud",
            fallback_trail=_TRAIL,
        ),
    )
    assert served_by == "cloud"
    assert trail == _TRAIL


async def test_run_without_fallback_still_writes(tmp_path) -> None:
    """Backward-compat control: a run that never fell back is still recordable.

    The additive columns must not break the pre-existing RunEvent shape. Constructed
    POSITIONALLY over the original eight fields — if the new fields had been inserted
    anywhere but last, this call would bind them wrongly or raise.
    """
    served_by, trail = await _write_and_read(
        tmp_path,
        RunEvent(None, "hello", "local-model", 1.0, 2.0, 11, 22, 0.5),
    )
    assert served_by is None, "a no-fallback run must leave served_by NULL"
    assert trail is None
