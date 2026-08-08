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
    """A completed (or in-progress) run row: prompts, model, timings, tokens, TTFA.

    Also carries fallback provenance (MODEL-04, D-06, SC#4): ``served_by`` names the
    profile that ACTUALLY served the run, and ``fallback_trail`` is the JSON list of
    hops that preceded it. Both are appended LAST and default to ``None``, so existing
    positional construction and no-fallback runs are unaffected (backward compatible).
    """

    id: int | None = None
    prompts: str | None = None
    model: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    time_to_first_audio: float | None = None
    served_by: str | None = None
    fallback_trail: str | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            (
                "INSERT INTO runs "
                "(id, prompts, model, started_at, ended_at, "
                "prompt_tokens, completion_tokens, time_to_first_audio, "
                "served_by, fallback_trail) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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
                self.served_by,
                self.fallback_trail,
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
class TurnLegEvent:
    """One AGENT LEG of a possibly multi-agent turn (MESH-05, OQ-5, SC#4).

    A handed-off turn is several legs, each answered by a different agent and each with
    its OWN ``served_by`` and its OWN ``fallback_trail`` — per-agent fallback provenance
    is not reconstructible from a single per-turn row. Siblings are correlated by
    ``turn_id``, an engine-generated uuid4 hex string, never a database-assigned id: the
    fire-and-forget writer never surfaces ``lastrowid``, which is why this table carries
    no FK (see schema.sql).

    ``TraceStore`` needs no change to accept this: the writer is event-agnostic and just
    executes whatever ``as_sql()`` yields, so a new record type is a dataclass plus a
    ``CREATE TABLE``.
    """

    turn_id: str
    leg_seq: int
    agent: str | None = None
    served_by: str | None = None
    fallback_trail: str | None = None
    started_at: float | None = None
    ended_at: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            (
                "INSERT INTO turn_legs "
                "(turn_id, leg_seq, agent, served_by, fallback_trail, "
                "started_at, ended_at, prompt_tokens, completion_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                self.turn_id,
                self.leg_seq,
                self.agent,
                self.served_by,
                self.fallback_trail,
                self.started_at,
                self.ended_at,
                self.prompt_tokens,
                self.completion_tokens,
            ),
        )


@dataclass(slots=True)
class HandoffEvent:
    """One handoff ATTEMPT — accepted or rejected (MESH-05, T-04-07).

    Rejected attempts matter most: they produce no ``runs`` row and no ``turn_legs`` row,
    so without this table a wrong reroute leaves no trace at all. Everything except the
    correlation keys (``turn_id`` / ``seq``) therefore defaults to ``None``, so a bare
    rejection — no observer, no reroute, no timing — constructs cleanly.

    ``to_agent`` and ``detail`` carry model-influenced text. The INSERT is parameterized
    with an explicit column list and never interpolates (T-04-06); the placeholder/param
    balance test is what keeps a hand-built query from creeping in.

    ``TraceStore`` is unmodified — the writer is event-agnostic by design.
    """

    turn_id: str
    seq: int
    from_agent: str | None = None
    to_agent: str | None = None
    outcome: str | None = None
    observer_verdict: str | None = None
    observer_profile: str | None = None
    rerouted_to: str | None = None
    detail: str | None = None
    at: float | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        return (
            (
                "INSERT INTO handoffs "
                "(turn_id, seq, from_agent, to_agent, outcome, "
                "observer_verdict, observer_profile, rerouted_to, detail, at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                self.turn_id,
                self.seq,
                self.from_agent,
                self.to_agent,
                self.outcome,
                self.observer_verdict,
                self.observer_profile,
                self.rerouted_to,
                self.detail,
                self.at,
            ),
        )


@dataclass(slots=True)
class CustomEvent:
    """A custom or background log event (event_type, summary, payload, created_at)."""

    event_type: str
    summary: str | None = None
    payload: str | None = None
    created_at: float | None = None

    def as_sql(self) -> tuple[str, tuple[object, ...]]:
        import time
        created = self.created_at if self.created_at is not None else time.time()
        return (
            (
                "INSERT INTO custom_events (event_type, summary, payload, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (self.event_type, self.summary, self.payload, created),
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

    async def query_custom_events(
        self,
        event_type: str | None = None,
        since_seconds_ago: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        """Query custom_events table off the hot path."""
        import time
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT id, event_type, summary, payload, created_at FROM custom_events"
            conditions: list[str] = []
            params: list[object] = []
            if event_type:
                conditions.append("event_type = ?")
                params.append(event_type)
            if since_seconds_ago is not None:
                min_time = time.time() - since_seconds_ago
                conditions.append("created_at >= ?")
                params.append(min_time)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            async with db.execute(query, tuple(params)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

