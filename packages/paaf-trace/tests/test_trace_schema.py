# SPDX-License-Identifier: Apache-2.0
"""Schema tests (TRACE-02, TRACE-03).

Apply ``schema.sql`` to a fresh in-memory aiosqlite DB and interrogate the resulting
tables via ``PRAGMA table_info``. These assertions pin the durable trace contract the
desktop Logs page and the Plan 09 TTFA gate both depend on:
  * ``runs.time_to_first_audio`` exists and is declared REAL (first-class metric).
  * every TRACE-02 column (prompts, model, timings, both token counts) is present.
  * ``tool_calls`` carries name/args/results plus a run foreign key.
"""

from __future__ import annotations

import aiosqlite

from paaf_trace import read_schema


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
