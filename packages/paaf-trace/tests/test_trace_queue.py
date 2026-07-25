# SPDX-License-Identifier: Apache-2.0
"""TraceStore tests (TRACE-01, TRACE-03).

Three guarantees, each with its own negative control:
  * emit is synchronous — it is NOT a coroutine function and never awaits.
  * on bounded-queue overflow, emit DROPS (increments a counter) instead of blocking
    the hot path (the load-bearing off-hot-path control).
  * a run emitted then drained round-trips out of SQLite with its fields intact,
    including a recorded time_to_first_audio.
"""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest
from paaf_trace.metrics import compute_time_to_first_audio, record_time_to_first_audio
from paaf_trace.store import RunEvent, ToolCallEvent, TraceStore


def test_emit_is_not_a_coroutine() -> None:
    """emit must be a plain sync method — it can never await on the hot path."""
    assert asyncio.iscoroutinefunction(TraceStore.emit) is False


async def test_emit_drops_on_overflow_without_blocking() -> None:
    """Overflowing the bounded queue increments _dropped and never blocks/raises."""
    store = TraceStore(":memory:", maxsize=2)  # writer not started: queue can fill
    for _ in range(5):
        store.emit(RunEvent(prompts="x", model="m"))
    # 2 buffered, 3 dropped — emit returned immediately every time (no await/block).
    assert store.dropped == 3
    assert store._q.qsize() == 2


async def test_pragmas_declared() -> None:
    """The WAL + synchronous=NORMAL tradeoff is declared in PRAGMAS."""
    from paaf_trace.store import PRAGMAS

    joined = " ".join(PRAGMAS)
    assert "journal_mode=WAL" in joined
    assert "synchronous=NORMAL" in joined
    assert "foreign_keys=ON" in joined
    assert "busy_timeout" in joined


async def test_run_round_trip_with_ttfa(tmp_path) -> None:
    """A run emitted then drained is retrievable with all fields, including TTFA."""
    db_path = tmp_path / "trace.db"
    store = TraceStore(str(db_path))
    await store.start()
    store.emit(
        RunEvent(
            id=1,
            prompts="hello",
            model="qwen3",
            started_at=0.0,
            ended_at=1.5,
            prompt_tokens=11,
            completion_tokens=22,
            time_to_first_audio=0.42,
        )
    )
    store.emit(ToolCallEvent(run_id=1, name="get_weather", args="{}", results="sunny"))
    await store.stop()

    async with aiosqlite.connect(str(db_path)) as db:
        async with db.execute(
            "SELECT prompts, model, started_at, ended_at, prompt_tokens, "
            "completion_tokens, time_to_first_audio FROM runs WHERE id = 1"
        ) as cur:
            row = await cur.fetchone()
        async with db.execute(
            "SELECT name, args, results FROM tool_calls WHERE run_id = 1"
        ) as cur:
            tool_row = await cur.fetchone()

    assert row == ("hello", "qwen3", 0.0, 1.5, 11, 22, 0.42)
    assert tool_row == ("get_weather", "{}", "sunny")


async def test_metrics_records_ttfa_on_run(tmp_path) -> None:
    """record_time_to_first_audio updates the run row via the single writer."""
    assert compute_time_to_first_audio(10.0, 10.6) == pytest.approx(0.6)

    db_path = tmp_path / "trace.db"
    store = TraceStore(str(db_path))
    await store.start()
    store.emit(RunEvent(id=7, prompts="p", model="m"))
    record_time_to_first_audio(store, run_id=7, seconds=0.6)
    await store.stop()

    async with aiosqlite.connect(str(db_path)) as db, db.execute(
        "SELECT time_to_first_audio FROM runs WHERE id = 7"
    ) as cur:
        (ttfa,) = await cur.fetchone()
    assert ttfa == 0.6
