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
  * ``RunEvent.as_sql()`` widened consistently (columns == placeholders == params).
"""

from __future__ import annotations

import aiosqlite
from paaf_trace import read_schema
from paaf_trace.store import RunEvent


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
