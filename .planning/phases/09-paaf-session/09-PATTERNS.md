# Phase 09: paaf-session - Pattern Map

**Mapped:** 2026-08-09
**Files analyzed:** 7
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/paaf-session/src/paaf_session/orchestrator.py` | controller | event-driven | `packages/paaf-trace/src/paaf_trace/store.py` | partial |
| `packages/paaf-session/src/paaf_session/history.py` | utility | transform | `packages/paaf-voice/src/paaf_voice/aggregator.py` | role-match |
| `packages/paaf-session/src/paaf_session/audio_queue.py` | component | queue | `packages/paaf-trace/src/paaf_trace/store.py` | role-match |
| `packages/paaf-session/tests/test_state_machine.py` | test | event-driven | `packages/paaf-trace/tests/test_trace_queue.py` | partial |
| `packages/paaf-session/tests/test_barge_in.py` | test | event-driven | `packages/paaf-trace/tests/test_trace_queue.py` | partial |
| `packages/paaf-session/tests/test_audio_arbitration.py` | test | queue | `packages/paaf-trace/tests/test_trace_queue.py` | partial |
| `packages/paaf-session/tests/test_fakes.py` | test | event-driven | `packages/paaf-voice/src/paaf_voice/testing/fakes.py` | role-match |

## Pattern Assignments

### `packages/paaf-session/src/paaf_session/orchestrator.py` (controller, event-driven)

**Analog:** `packages/paaf-trace/src/paaf_trace/store.py`
*Note: No exact `asyncio.TaskGroup` state machine analog exists in the codebase. Use RESEARCH.md Pattern 1 for `TaskGroup` state machine structures. This analog shows the project's approach to background `asyncio` task management.*

**Background loop pattern** (lines 273-291):
```python
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
```

**Task creation pattern** (lines 266-271):
```python
    async def start(self) -> None:
        """Start the single writer task and wait until the schema is applied."""
        if self._writer_task is not None:
            return
        self._writer_task = asyncio.create_task(self._writer())
        await self._ready.wait()
```

---

### `packages/paaf-session/src/paaf_session/history.py` (utility, transform)

**Analog:** `packages/paaf-voice/src/paaf_voice/aggregator.py`

**Async generator transform pattern** (lines 108-118):
```python
    async def aggregate_stream(
        self, token_stream: AsyncIterable[str]
    ) -> AsyncIterator[str]:
        """Consume an async stream of LLM tokens and yield sentence chunks."""
        async for token in token_stream:
            for chunk in self.add_token(token):
                yield chunk

        for chunk in self.flush():
            yield chunk
```

---

### `packages/paaf-session/src/paaf_session/audio_queue.py` (component, queue)

**Analog:** `packages/paaf-trace/src/paaf_trace/store.py`

**Non-blocking async queue pattern** (lines 254-264):
```python
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
```

---

### `packages/paaf-session/tests/test_state_machine.py`, `test_barge_in.py`, `test_audio_arbitration.py` (test, event-driven/queue)

**Analog:** `packages/paaf-trace/tests/test_trace_queue.py`

**Async test pattern** (lines 27-34):
```python
async def test_emit_drops_on_overflow_without_blocking() -> None:
    """Overflowing the bounded queue increments _dropped and never blocks/raises."""
    store = TraceStore(":memory:", maxsize=2)  # writer not started: queue can fill
    for _ in range(5):
        store.emit(RunEvent(prompts="x", model="m"))
    # 2 buffered, 3 dropped — emit returned immediately every time (no await/block).
    assert store.dropped == 3
    assert store._q.qsize() == 2
```

---

### `packages/paaf-session/tests/test_fakes.py` (test, request-response)

**Analog:** `packages/paaf-voice/src/paaf_voice/testing/fakes.py`

**Fake audio device state tracking pattern** (lines 23-40):
```python
class FakeAudioSink(AudioSink):
    """Test double for AudioSink hardware playback.

    Supports virtual playhead tracking ('instant', '1x', 'stepped') and
    reference tap extraction for Acoustic Echo Cancellation (AEC).
    """

    def __init__(self, mode: Literal["instant", "1x", "stepped"] = "instant") -> None:
        self.mode = mode
        self.recorded_frames: list[AudioFrame] = []
        self._start_wall_time: float | None = None
        self._stepped_time_s: float = 0.0

    def write_frame(self, frame: AudioFrame) -> None:
        """Record an incoming audio frame."""
        self.recorded_frames.append(frame)
        if self.mode == "1x" and self._start_wall_time is None:
            self._start_wall_time = time.monotonic()
```

## Shared Patterns

### Async Event Management
**Source:** `packages/paaf-trace/src/paaf_trace/store.py`
**Apply to:** `paaf_session` components
```python
        self._ready = asyncio.Event()
        # ...
        self._ready.set()
        # ...
        await self._ready.wait()
```

## No Analog Found

Files with no exact match in the codebase (planner should use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `packages/paaf-session/src/paaf_session/orchestrator.py` | controller | event-driven | No `asyncio.TaskGroup` based state machine exists in the codebase yet. See RESEARCH.md Pattern 1. |

## Metadata

**Analog search scope:** `packages/`
**Files scanned:** 7
**Pattern extraction date:** 2026-08-09
