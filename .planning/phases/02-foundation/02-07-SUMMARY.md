---
phase: 02-foundation
plan: 07
subsystem: trace
tags: [aiosqlite, sqlite, wal, asyncio, trace-store, time-to-first-audio, no-egress, raw-sql]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "paaf-trace package skeleton (aiosqlite dep, workspace dep on paaf-core), --disable-socket test default, deterministic FrozenClock fixture (Plan 01)"
  - phase: 02-foundation
    provides: "no-network-client-in-framework import-linter contract + its negative control (Plan 02)"
provides:
  - "paaf_trace.schema.sql: runs table (prompts, model, timings, prompt/completion tokens, time_to_first_audio REAL) + tool_calls table (name, args, results, run_id FK) — raw SQL, no ORM"
  - "paaf_trace.store.TraceStore: WAL SQLite, single writer task owning the connection, synchronous emit() with put_nowait + drop-counter (off the hot path)"
  - "paaf_trace.metrics: compute_time_to_first_audio (pure) + record_time_to_first_audio (emits TtfaUpdate through the writer)"
  - "runtime no-egress proof for the trace store (TRACE-05) complementing the Plan 02 static contract"
  - "--allow-unix-socket added to the suite addopts so async tests run under --disable-socket while AF_INET egress stays blocked"
affects: [02-09 ttfa gate, phase-3 llm engine trace draining, desktop logs page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-writer SQLite behind a bounded asyncio.Queue: one _writer task owns the aiosqlite connection; WAL + synchronous=NORMAL + busy_timeout avoid writer-lock contention"
    - "Hot-path-safe producer: emit() is a SYNCHRONOUS put_nowait with a _dropped counter on QueueFull — never awaits, so realtime audio never stalls behind disk I/O"
    - "Event dataclasses expose as_sql() -> (sql, params); the writer is event-agnostic (raw SQL, no ORM)"
    - "read_schema() single source of truth for the DDL, shared by the writer and the schema tests"
    - "--disable-socket + --allow-unix-socket: block network egress (AF_INET) while permitting asyncio's local AF_UNIX self-pipe"

key-files:
  created:
    - packages/paaf-trace/src/paaf_trace/schema.sql
    - packages/paaf-trace/src/paaf_trace/store.py
    - packages/paaf-trace/src/paaf_trace/metrics.py
    - packages/paaf-trace/tests/test_trace_schema.py
    - packages/paaf-trace/tests/test_trace_queue.py
    - packages/paaf-trace/tests/test_trace_no_egress.py
  modified:
    - packages/paaf-trace/src/paaf_trace/__init__.py
    - pyproject.toml

key-decisions:
  - "emit() is a plain sync method (asserted via asyncio.iscoroutinefunction is False) — the hot-path guarantee is mechanically enforced, not just documented"
  - "stop() drains via asyncio.Queue.join() then pushes a _SHUTDOWN sentinel, guaranteeing every emitted event is written+committed before the connection closes"
  - "TtfaUpdate is a first-class event so time_to_first_audio can be recorded after the run row exists, still off the hot path"
  - "--allow-unix-socket added to root addopts (Rule 3 blocking fix): asyncio's event-loop self-pipe is an AF_UNIX socketpair; network egress (AF_INET) remains blocked so TRACE-05 holds"

patterns-established:
  - "Single-writer-queue trace store (Pattern 6 / Pitfall 5): WAL, one connection owner, bounded queue, put_nowait + drop-counter"
  - "Negative controls per guarantee: emit-not-coroutine, overflow-drops-without-blocking, and emit->write->read passing under --disable-socket"

requirements-completed: [TRACE-01, TRACE-02, TRACE-03, TRACE-05]

coverage:
  - id: D1
    description: "Trace schema records prompts, selected model, timings, token counts (runs) and tool calls with args+results (tool_calls) — raw SQL, no ORM (TRACE-02)"
    requirement: "TRACE-02"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_schema.py::test_runs_trace02_columns"
        status: pass
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_schema.py::test_tool_calls_columns_and_fk"
        status: pass
    human_judgment: false
  - id: D2
    description: "time_to_first_audio is a first-class REAL column on runs (TRACE-03)"
    requirement: "TRACE-03"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_schema.py::test_ttfa_column"
        status: pass
    human_judgment: false
  - id: D3
    description: "TraceStore is WAL + single-writer + bounded queue; emit() never awaits and drops with a counter on overflow (TRACE-01)"
    requirement: "TRACE-01"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_queue.py::test_emit_is_not_a_coroutine"
        status: pass
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_queue.py::test_emit_drops_on_overflow_without_blocking"
        status: pass
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_queue.py::test_run_round_trip_with_ttfa"
        status: pass
    human_judgment: false
  - id: D4
    description: "metrics helpers compute and record time_to_first_audio through the single writer"
    requirement: "TRACE-03"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_queue.py::test_metrics_records_ttfa_on_run"
        status: pass
    human_judgment: false
  - id: D5
    description: "The trace store performs no network egress: full emit->write->read runs under --disable-socket and no HTTP client is in the import graph (TRACE-05)"
    requirement: "TRACE-05"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_no_egress.py::test_full_path_runs_with_no_network"
        status: pass
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_no_egress.py::test_no_http_client_in_import_graph"
        status: pass
      - kind: other
        ref: "uv run lint-imports (no-network-client-in-framework KEPT)"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 07: Local SQLite Trace Store Summary

**WAL SQLite trace store in `paaf-trace` — a single writer task owning the connection behind a bounded `asyncio.Queue`, a synchronous `emit()` that put_nowait's and drops-with-a-counter so audio never stalls, a `runs`/`tool_calls` schema with `time_to_first_audio` as a first-class REAL column, and a runtime proof (under `--disable-socket`) that nothing leaves the device. Raw SQL + aiosqlite, no ORM.**

## Performance

- **Duration:** ~25 min (across a session-limit resume)
- **Completed:** 2026-07-25
- **Tasks:** 3
- **Files created:** 6 (2 modified: `__init__.py`, `pyproject.toml`)

## Accomplishments
- `schema.sql` (raw SQL, no ORM) defines `runs` (prompts, model, started_at/ended_at, prompt_tokens/completion_tokens, `time_to_first_audio REAL`) and `tool_calls` (name, args, results, `run_id` FK) — the durable contract the desktop Logs page and the Plan 09 TTFA gate both depend on.
- `TraceStore` implements Pattern 6 / Pitfall 5: one `_writer` task owns the aiosqlite connection with `PRAGMAS` (WAL, synchronous=NORMAL, foreign_keys=ON, busy_timeout=5000); producers call a **synchronous** `emit()` that `put_nowait`'s and increments `_dropped` on `QueueFull` — the load-bearing off-hot-path guarantee, mechanically proven by `asyncio.iscoroutinefunction(TraceStore.emit) is False` and an overflow negative control.
- `metrics.py`: `compute_time_to_first_audio(started_at, first_audio_at)` (pure, rejects negative latency) and `record_time_to_first_audio(store, run_id, seconds)` (emits a `TtfaUpdate` through the writer, still off the hot path).
- TRACE-05 runtime proof: the full emit→write→read path passes under `--disable-socket` (any AF_INET egress raises `SocketBlockedError`), and no `httpx`/`requests`/`aiohttp` appears in `sys.modules` after importing `paaf_trace`. The Plan 02 `no-network-client-in-framework` import-linter contract still reports **KEPT**.
- Full workspace suite: **67 passed** (12 in paaf-trace), no regressions; import-linter 3/3 contracts kept; mypy clean on the new sources.

## Task Commits

Each task was committed atomically:

1. **Task 1: Trace schema — runs + tool_calls with first-class time_to_first_audio** - `11df8cc` (feat)
2. **Task 2: TraceStore — WAL single-writer bounded queue off the hot path** - `f8e043b` (feat)
3. **Task 3: Prove the trace store never leaves the device (TRACE-05)** - `bed3830` (test)
4. **Ruff/ISC cleanup on paaf-trace** - `adfbaa4` (style)

_Note: the `pyproject.toml --allow-unix-socket` deviation is folded into Task 1's commit (`11df8cc`) — the first commit whose async test needs it._

## Files Created/Modified
- `packages/paaf-trace/src/paaf_trace/schema.sql` - Raw-SQL DDL: `runs` + `tool_calls`, `time_to_first_audio REAL` first-class
- `packages/paaf-trace/src/paaf_trace/store.py` - `PRAGMAS`, `TraceStore` (emit/start/stop/_writer), `RunEvent`/`ToolCallEvent`/`TtfaUpdate` with `as_sql()`
- `packages/paaf-trace/src/paaf_trace/metrics.py` - TTFA compute + record helpers
- `packages/paaf-trace/src/paaf_trace/__init__.py` - Added `SCHEMA_PATH` + `read_schema()` (shared DDL source)
- `packages/paaf-trace/tests/test_trace_schema.py` - PRAGMA table_info assertions incl. `test_ttfa_column`
- `packages/paaf-trace/tests/test_trace_queue.py` - emit-not-coroutine, overflow-drops, WAL round-trip, metrics round-trip
- `packages/paaf-trace/tests/test_trace_no_egress.py` - Runtime no-egress control (TRACE-05)
- `pyproject.toml` - Added `--allow-unix-socket` to addopts (see Deviations)

## Decisions Made
- **`emit()` is a plain sync method**, not a coroutine — the hot-path non-blocking guarantee is enforced by a test (`asyncio.iscoroutinefunction(... ) is False`), not just prose.
- **`stop()` uses `Queue.join()` then a `_SHUTDOWN` sentinel** — every emitted event is written and committed before the connection closes, so round-trip reads are deterministic.
- **`TtfaUpdate` is a first-class event** so `time_to_first_audio` can be recorded after the run row exists while staying off the hot path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `--allow-unix-socket` to the suite addopts**
- **Found during:** Task 1 (running the first async test in the repo)
- **Issue:** These are the first `async def` tests in the workspace. Under the existing `--disable-socket` default, pytest-socket blocks `socket.socketpair()`, which asyncio's event loop needs for its internal self-pipe — every async test errored at event-loop construction (`AttributeError: ... has no attribute '_ssock'`).
- **Fix:** Added `--allow-unix-socket` to `[tool.pytest.ini_options] addopts`. This permits ONLY local AF_UNIX sockets (asyncio's self-pipe); network egress uses AF_INET/AF_INET6 and stays blocked. Verified with an ephemeral control that `socket.socket(AF_INET, ...)` still raises `SocketBlockedError` under the combined flags, so the TRACE-05 no-egress guarantee is preserved (unix sockets are local IPC and cannot leave the device).
- **Files modified:** pyproject.toml
- **Verification:** `uv run pytest packages/paaf-trace -q` → 12 passed; full suite → 67 passed; ephemeral AF_INET negative control still blocks.
- **Committed in:** `11df8cc` (Task 1 commit)

**2. [Rule 1 - Bug] Float-equality tolerance in the TTFA compute assertion**
- **Found during:** Task 2 (running `test_metrics_records_ttfa_on_run`)
- **Issue:** `compute_time_to_first_audio(10.0, 10.6)` returns `0.5999999999999996` (IEEE-754), so an exact `== 0.6` assertion failed.
- **Fix:** Used `pytest.approx(0.6)` for the pure-compute assertion. (The stored/round-tripped value uses the passed-in `0.6` directly, so its `== 0.6` check remains exact.)
- **Files modified:** packages/paaf-trace/tests/test_trace_queue.py
- **Verification:** `test_metrics_records_ttfa_on_run` passes.
- **Committed in:** `f8e043b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 test bug)
**Impact on plan:** Both fixes are test-infra/precision corrections with no scope or design change. The `--allow-unix-socket` change is a workspace-wide test-config unblock that every future async test needs; the network-egress block (and thus TRACE-05) is provably intact.

## Issues Encountered
- Ruff 0.16.0 surfaces newer lint rules (RUF022/ISC004/SIM117/I001) that the pre-existing committed code (`paaf-core/secrets/__init__.py`) also trips, so ruff is not a hard project gate. Still applied the safe auto-fixes plus a manual ISC004 parenthesization to keep the new package clean (commit `adfbaa4`); all paaf-trace files now pass `ruff check`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 09's TTFA CI gate has its substrate: `runs.time_to_first_audio` is a first-class REAL column and `metrics.compute_time_to_first_audio` + `record_time_to_first_audio` exist for the fake-TTS accounting-accuracy assertion (the deterministic `frozen_clock` fixture from Plan 01 pairs with it).
- Phase 3's LLM engine can drain runs into this store via `TraceStore.emit(RunEvent(...))` / `emit(ToolCallEvent(...))` off the hot path.
- The no-egress guarantee is proven at runtime here and statically by the Plan 02 import-linter contract.

## Self-Check: PASSED

- All 6 created files + 2 modified files verified present on disk.
- All four commits (`11df8cc`, `f8e043b`, `bed3830`, `adfbaa4`) verified in git log.
- paaf-trace suite: 12 passed; full workspace suite: 67 passed; import-linter: 3/3 KEPT; mypy: clean.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
