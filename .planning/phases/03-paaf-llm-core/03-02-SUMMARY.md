---
phase: 03-paaf-llm-core
plan: 02
subsystem: database
tags: [sqlite, aiosqlite, raw-sql, schema, trace, observability, fallback, provenance]

# Dependency graph
requires:
  - phase: 02-core-software
    provides: "paaf-trace TraceStore (WAL + single fire-and-forget writer), schema.sql, RunEvent/as_sql() event contract, read_schema()"
provides:
  - "runs.served_by TEXT — the profile that ACTUALLY served a run (SC#4)"
  - "runs.fallback_trail TEXT — JSON list of fallback hops [{from,to,reason}] (D-06)"
  - "RunEvent.served_by / RunEvent.fallback_trail fields with a widened 10-column INSERT"
  - "test_trace_fallback_schema.py — column presence, as_sql() balance, round-trip, and a backward-compat control"
affects: [03-06-fallback-engine, 03-agent-loop, desktop-logs-page, phase-4-handoff-tracing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Denormalized provenance columns on runs instead of an FK child table (writer stays fire-and-forget)"
    - "Additive, nullable DDL — new columns appended last so positional RunEvent construction is unaffected"
key-files:
  created:
    - packages/paaf-trace/tests/test_trace_fallback_schema.py
  modified:
    - packages/paaf-trace/src/paaf_trace/schema.sql
    - packages/paaf-trace/src/paaf_trace/store.py

key-decisions:
  - "Denormalized served_by + fallback_trail columns on runs, NOT a child fallbacks table — TraceStore._writer is fire-and-forget and never surfaces lastrowid, so an FK child would have forced a writer redesign (RESEARCH Pitfall 5)"
  - "fallback_trail stored as JSON text, not structured columns — the trail is variable-length and append-mostly; no ORM (CLAUDE.md)"
  - "New RunEvent fields appended LAST and defaulted to None, so existing positional construction and no-fallback runs keep working unchanged"

patterns-established:
  - "Additive trace DDL: extend runs with nullable columns + widen RunEvent.as_sql() in lockstep; never touch PRAGMAS/emit()/_writer()/stop()"
  - "Backward-compat control test: construct the event POSITIONALLY over the pre-change field set to prove new fields were appended, not inserted mid-list"

requirements-completed: [MODEL-04]

coverage:
  - id: D1
    description: "runs table carries served_by and fallback_trail, both declared TEXT"
    requirement: "MODEL-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_fallback_schema.py#test_fallback_columns_exist"
        status: pass
    human_judgment: false
  - id: D2
    description: "RunEvent carries served_by + fallback_trail and its INSERT is widened consistently (columns == placeholders == params)"
    requirement: "MODEL-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_trace_fallback_schema.py#test_run_event_sql_widened_consistently"
        status: pass
    human_judgment: false
  - id: D3
    description: "A run's served_by and fallback trail JSON survive a real TraceStore write and read back intact"
    requirement: "MODEL-04"
    verification:
      - kind: integration
        ref: "packages/paaf-trace/tests/test_trace_fallback_schema.py#test_fallback_trail_roundtrip"
        status: pass
    human_judgment: false
  - id: D4
    description: "Backward compatibility — a run inserted with the old field set (no fallback) still writes, with the new columns NULL"
    requirement: "MODEL-04"
    verification:
      - kind: integration
        ref: "packages/paaf-trace/tests/test_trace_fallback_schema.py#test_run_without_fallback_still_writes"
        status: pass
    human_judgment: false
  - id: D5
    description: "The fire-and-forget hot-path writer contract is preserved (PRAGMAS, emit, _writer, stop unchanged)"
    verification:
      - kind: unit
        ref: "uv run pytest packages/paaf-trace -q (21 passed, incl. test_trace_queue/test_trace_no_egress/test_ttfa_regression)"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 02: Fallback Provenance Trace Seam Summary

**Additive `served_by` + `fallback_trail` (JSON) columns on `runs`, with `RunEvent` widened to a 10-column INSERT — the D-06 authoritative record the fallback engine drains into, landed without touching the fire-and-forget writer.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-08-05T15:38:00+03:00
- **Completed:** 2026-08-05T15:46:00+03:00
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `runs` now records **which profile actually served each turn** (`served_by`) and **every fallback hop that preceded it** (`fallback_trail`, JSON `[{from,to,reason}]`) — the "nothing hidden" provenance record for MODEL-03/04 (D-06, SC#4).
- `RunEvent` carries both fields and its INSERT widened from 8 to 10 columns, verified balanced (columns == `?` placeholders == params length).
- The hot-path writer contract is **byte-unchanged**: `PRAGMAS`, `emit()`, `_writer()` and `stop()` were not touched. The diff is confined to the `RunEvent` dataclass and the DDL.
- A backward-compatibility control proves the change is genuinely additive: a `RunEvent` built **positionally** over the original eight fields still writes, with both new columns NULL.

## Task Commits

Each task was committed atomically:

1. **Task 1: Additive columns + RunEvent extension (TDD)** — `33528ea` (test, RED) → `504a838` (feat, GREEN). No refactor commit: the change was two field additions and a widened tuple, with nothing to clean up.
2. **Task 2: Round-trip + backward-compat control tests** — `909175c` (test)

_Note: Task 1 was a TDD task — the RED commit lands the failing assertions, the GREEN commit the implementation._

## Files Created/Modified

- `packages/paaf-trace/src/paaf_trace/schema.sql` — `runs` gains `served_by TEXT` and `fallback_trail TEXT`, each with a comment naming its requirement and the Pitfall-5 rationale for the denormalized shape.
- `packages/paaf-trace/src/paaf_trace/store.py` — `RunEvent` gains the two fields (appended last, default `None`) and widens its `as_sql()` INSERT to 10 columns/placeholders/params. Docstring records the backward-compat intent.
- `packages/paaf-trace/tests/test_trace_fallback_schema.py` (new) — four tests: column presence + declared type, `as_sql()` balance, a real-store round-trip, and the positional backward-compat control.

## Decisions Made

- **Denormalized columns on `runs`, not a `fallbacks` child table.** `TraceStore._writer` is deliberately fire-and-forget and never surfaces `lastrowid`, so FK child rows would have required extending the writer to return/assign ids — a hot-path change this phase does not need (RESEARCH Pitfall 5, plan `key_links`).
- **`fallback_trail` as JSON text.** The trail is variable-length and append-mostly; structured columns would either cap the hop count or demand a child table. Raw SQL + JSON text, no ORM (CLAUDE.md).
- **New fields appended last with `None` defaults.** This is what makes the change backward compatible, and it is what `test_run_without_fallback_still_writes` pins by constructing positionally.
- **Round-trip test asserts `store.dropped == 0`.** Without it, a dropped event would leave the row count assertion as the only guard; the explicit drop check stops the queue from silently turning the round-trip into a no-op pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Combined nested `async with` to satisfy ruff SIM117**

- **Found during:** Task 2 (round-trip test helper)
- **Issue:** The `aiosqlite.connect(...)` / `db.execute(...)` pair was directly nested with no statement between them, which ruff flags as `SIM117`. This would have failed CI lint. (The existing `test_trace_schema.py` escapes the rule only because it has an `executescript` call between the two context managers.)
- **Fix:** Rewrote as a single parenthesized `async with` binding both contexts.
- **Files modified:** `packages/paaf-trace/tests/test_trace_fallback_schema.py`
- **Verification:** `uv run ruff check` on the file — all checks passed; the 4 tests still pass.
- **Committed in:** `909175c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking / lint)
**Impact on plan:** Cosmetic lint conformance only. No behavior change, no scope creep.

## Issues Encountered

None. The plan's chosen shape (denormalized columns) turned out to be exactly right — no writer changes were needed and no existing test required modification.

Out-of-scope note: the pre-existing ruff `I001` failure at `packages/paaf-llm/tests/test_wheel_smoke.py:13` was left untouched as instructed; it is already logged in `deferred-items.md`.

## Verification Results

- `uv run pytest packages/paaf-trace -q` → **21 passed** (19 pre-existing + 2 new; 4 total in the new file, 2 of which landed in the RED commit).
- `uv run pytest -q` (full repo) → **76 passed**, no regressions.
- `uv run lint-imports` → **3 contracts kept, 0 broken** (`voice-and-llm-are-independent`, `langchain-confined-to-adapter`, `no-network-client-in-framework`).
- `uv run ruff check` + `ruff format --check` on all three touched files → clean.
- `uv run mypy packages/paaf-trace/src/paaf_trace/store.py` → no issues.
- `git diff` on `store.py` confirms only the `RunEvent` dataclass changed — `emit()`, `_writer()`, `stop()` and `PRAGMAS` untouched.

## TDD Gate Compliance

Task 1 followed the full cycle with both gates present in git history:

- **RED** — `33528ea` `test(03-02)`: both assertions failed for the right reasons (`served_by` absent from `PRAGMA table_info(runs)`; `RunEvent.__init__() got an unexpected keyword argument 'served_by'`).
- **GREEN** — `504a838` `feat(03-02)`: implementation landed, suite green.
- **REFACTOR** — not required; no cleanup opportunity existed in a two-field additive change.

## Threat Model Coverage

- **T-03-05 (Repudiation, `mitigate`)** — mitigated as specified. `served_by` + `fallback_trail` make every served-by choice and fallback hop an after-the-fact auditable fact in the local trace, so a wrong reroute cannot be silently denied.
- **T-03-06 (Information Disclosure, `accept`)** — unchanged. The new columns are text provenance (profile names and reason codes); no secrets are written to a run row, and `test_trace_no_egress.py` still passes under the network-blocked test config.

No new threat surface introduced: no network endpoints, no auth paths, no new file access. The change is two nullable text columns on an existing local-only SQLite table.

## Known Stubs

None. Both columns are real, populated end-to-end in the round-trip test, and consumed by nothing yet only because their consumer (the fallback engine) is plan 03-06 — that is the intended seam, not a stub.

## User Setup Required

None — no external service configuration required. The DDL is applied automatically by the store's existing `read_schema()` call on `start()`; no migration command exists or is needed (PAAF has no ORM).

## Next Phase Readiness

- **Ready for plan 03-06 (fallback engine):** the trace seam exists. The engine records provenance by constructing `RunEvent(..., served_by=<winning profile name>, fallback_trail=json.dumps([{"from":…,"to":…,"reason":…}]))` and calling the unchanged `trace.emit(...)`.
- **Ready for the CLI `--provenance` surface (D-06):** `served_by` is the field the inline `↳ fell back to <profile> (<reason>)` notice and the desktop Logs page will read.
- **Note for the consumer:** `fallback_trail` is JSON *text*, not a parsed structure — readers must `json.loads` it. Serialization is the writer's responsibility; the store deliberately stays schema-first raw SQL.
- **No blockers.**

## Self-Check: PASSED

- All four claimed files exist on disk (`03-02-SUMMARY.md`, `test_trace_fallback_schema.py`, `schema.sql`, `store.py`).
- All four claimed commits exist in git history (`33528ea`, `504a838`, `909175c`, `c411bc6`).
- Working tree clean — nothing uncommitted.

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
