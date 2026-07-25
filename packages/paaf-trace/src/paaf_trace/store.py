# SPDX-License-Identifier: Apache-2.0
"""Local SQLite trace store: WAL + a single writer task behind a bounded queue.

Design (TRACE-01, Pattern 6 / Pitfall 5):

* Exactly ONE writer task owns the ``aiosqlite`` connection. WAL mode +
  ``synchronous=NORMAL`` + ``busy_timeout`` sidestep SQLite writer-lock contention
  while multiple readers (the desktop Logs page, later) proceed concurrently.
* Producers on the audio hot path call the SYNCHRONOUS :meth:`TraceStore.emit`, which
  uses ``put_nowait`` and increments a drop counter on overflow. It MUST NOT await or
  block — audio must never stall behind disk I/O (Anti-Pattern: awaiting the queue).

Events are small dataclasses exposing ``as_sql()`` → ``(sql, params)``; the writer is
event-agnostic and just executes whatever raw SQL each event yields (no ORM — CLAUDE.md).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

import aiosqlite

from . import read_schema

# WAL + single-writer durability/throughput tradeoff. foreign_keys=ON enforces the
# tool_calls -> runs FK; busy_timeout bounds any transient lock wait.
PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA synchronous=NORMAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA busy_timeout=5000;",
)


@dataclass(slots=True)
class RunEvent:
    """A completed (or in-progress) run row: prompts, model, timings, tokens, TTFA."""

    id: int | None = None
    prompts: str | None = None
    model: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    time_to_first_audio: float | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            (
                "INSERT INTO runs "
                "(id, prompts, model, started_at, ended_at, "
                "prompt_tokens, completion_tokens, time_to_first_audio) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                self.id,
                self.prompts,
                self.model,
                self.started_at,
                self.ended_at,
                self.prompt_tokens,
                self.completion_tokens,
                self.time_to_first_audio,
            ),
        )


@dataclass(slots=True)
class ToolCallEvent:
    """A single tool invocation belonging to a run: name, args, results."""

    run_id: int
    name: str
    args: str | None = None
    results: str | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            "INSERT INTO tool_calls (run_id, name, args, results) VALUES (?, ?, ?, ?)",
            (self.run_id, self.name, self.args, self.results),
        )


@dataclass(slots=True)
class TtfaUpdate:
    """Record time_to_first_audio for an existing run row (see metrics.py)."""

    run_id: int
    seconds: float

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            "UPDATE runs SET time_to_first_audio = ? WHERE id = ?",
            (self.seconds, self.run_id),
        )


# Sentinel pushed by stop() to unblock the writer's queue.get() promptly.
_SHUTDOWN = object()


class TraceStore:
    """WAL SQLite trace store with a single writer task fed by a bounded queue.

    ``emit`` is synchronous and non-blocking; the writer task (started by
    :meth:`start`) owns the connection and drains the queue.
    """

    def __init__(self, path: str, maxsize: int = 1000) -> None:
        self._path = path
        self._q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._dropped = 0
        self._writer_task: asyncio.Task | None = None
        self._ready = asyncio.Event()

    @property
    def dropped(self) -> int:
        """Number of events dropped because the bounded queue was full."""
        return self._dropped

    def emit(self, event: object) -> None:
        """Hand an event to the writer WITHOUT blocking (hot-path safe).

        Synchronous by contract: it never awaits. On queue overflow it increments the
        drop counter instead of blocking, so realtime audio is never stalled by disk
        I/O (the load-bearing off-hot-path guarantee, TRACE-01).
        """
        try:
            self._q.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped += 1

    async def start(self) -> None:
        """Start the single writer task and wait until the schema is applied."""
        if self._writer_task is not None:
            return
        self._writer_task = asyncio.create_task(self._writer())
        await self._ready.wait()

    async def _writer(self) -> None:
        """Own the connection, apply pragmas + schema, then drain the queue forever."""
        async with aiosqlite.connect(self._path) as db:
            for pragma in PRAGMAS:
                await db.execute(pragma)
            await db.executescript(read_schema())
            await db.commit()
            self._ready.set()
            while True:
                event = await self._q.get()
                try:
                    if event is _SHUTDOWN:
                        return
                    sql, params = event.as_sql()  # type: ignore[attr-defined]
                    await db.execute(sql, params)
                    await db.commit()
                finally:
                    self._q.task_done()

    async def stop(self) -> None:
        """Flush all emitted events, then stop and close the writer's connection."""
        if self._writer_task is None:
            return
        await self._q.join()  # every emitted event has been written + committed
        self._q.put_nowait(_SHUTDOWN)  # promptly unblock the writer's get()
        with contextlib.suppress(asyncio.CancelledError):
            await self._writer_task
        self._writer_task = None
        self._ready.clear()
