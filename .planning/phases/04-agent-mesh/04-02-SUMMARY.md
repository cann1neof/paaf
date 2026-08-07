---
phase: 04-agent-mesh
plan: 02
subsystem: trace-store
status: complete
tags: [trace, schema, mesh, handoff, sqlite, pitfall-5, migration]
requirements: [MESH-05]

requires:
  - "paaf_trace.read_schema() (Phase 2) — the single source of truth both the writer and the schema tests apply"
  - "paaf_trace.store.TraceStore's event-agnostic writer (Phase 2) — unmodified by this plan, which is the point"
  - "paaf_trace.store.RunEvent.served_by / .fallback_trail (Phase 3, plan 03-06) — the denormalization precedent this design follows"
provides:
  - "SQL table turn_legs (turn_id, leg_seq, agent, served_by, fallback_trail, started_at, ended_at, prompt_tokens, completion_tokens)"
  - "SQL table handoffs (turn_id, seq, from_agent, to_agent, outcome, observer_verdict, observer_profile, rerouted_to, detail, at)"
  - "paaf_trace.store.TurnLegEvent"
  - "paaf_trace.store.HandoffEvent"
  - "packages/paaf-trace/tests/test_trace_handoff_schema.py (5 tests)"
  - "test_trace_schema.py::test_reopen_pre_phase4_database_gains_mesh_tables_and_loses_nothing"
affects:
  - "04-04 (one runs row per leg → emits TurnLegEvent per leg, correlated by 04-01's turn_id)"
  - "04-06 (per-agent fallback_chain → each leg's own fallback_trail lands in turn_legs)"
  - "04-07 (the observer writes observer_verdict / observer_profile / rerouted_to — already declared)"
  - "04-03 (budget_exhausted is a declared handoffs.outcome value)"

tech-stack:
  added: []
  patterns:
    - "New tables over new columns — the only additive change a migration-less executescript schema can make (Pitfall 5)"
    - "FK-free correlation by an engine-generated uuid4 turn_id, never lastrowid (Finding 5)"
    - "Declare the columns a later plan will need NOW, because there is no path to add them later"
    - "Reopen-a-real-file test as the only non-vacuous proof; the tmp_path fixture structurally cannot catch a missing migration"
    - "Inline literal of the OLD schema in the migration test, so it cannot go vacuous when the schema changes"

key-files:
  created:
    - packages/paaf-trace/tests/test_trace_handoff_schema.py
  modified:
    - packages/paaf-trace/src/paaf_trace/schema.sql
    - packages/paaf-trace/src/paaf_trace/store.py
    - packages/paaf-trace/src/paaf_trace/__init__.py
    - packages/paaf-trace/tests/test_trace_schema.py
    - .planning/phases/04-agent-mesh/deferred-items.md

decisions:
  - "turn_legs and handoffs are new tables, not columns on runs — CREATE TABLE IF NOT EXISTS makes an added column a silent no-op on an existing trace.db (Pitfall 5)"
  - "Neither table declares a FOREIGN KEY to runs: the fire-and-forget writer never surfaces lastrowid, so no producer could ever fill one, and with foreign_keys=ON every mesh insert would fail the constraint"
  - "All three observer columns are declared before the observer exists (04-07), because there is no mechanism to add them later"
  - "The reopen test builds the pre-Phase-4 database from an INLINE literal rather than from schema.sql — reading today's DDL would make the test compare the new schema to itself and go green in exactly the case it exists to catch"
  - "TraceStore is byte-unchanged: a new record type is a dataclass plus a CREATE TABLE, which is the event-agnostic writer's whole payoff"
  - "handoffs.outcome and .observer_verdict are free TEXT, not CHECK-constrained — a CHECK is a table-level constraint, and adding a new outcome value in a later plan would be unaddable for the same Pitfall-5 reason"

metrics:
  duration: ~35 min
  tasks: 2
  commits: 2
  files_changed: 6
  lines: +580 / -4
  tests_added: 6
  suite: 27 passed (paaf-trace) / 245 passed, 1 skipped (workspace)
  completed: 2026-08-07
---

# Phase 4 Plan 02: The Handoff Chain In The Trace Store Summary

A rejected handoff — the one kind of mesh event that produces no `runs` row at all — is now recordable and readable, and the proof is a round-trip against a `trace.db` that already existed rather than a fresh fixture.

## What Was Built

**Two new tables, and the fact that they are *tables* is the entire design.** `paaf-trace` applies its whole schema with one `executescript(read_schema())` over `CREATE TABLE IF NOT EXISTS`. There is no version table, no `ALTER TABLE`, and no migration runner anywhere in the repo. Under those rules an added *column* is a silent no-op on any database that already has the table — it works perfectly on a fresh DB, and every write naming it fails at runtime on the machine of anyone who has been using PAAF since Phase 3. `turn_legs` and `handoffs` are additive in the only way this schema step can be additive.

**`turn_legs` makes per-agent fallback provenance reconstructible.** OQ-5 resolves to one row per agent *leg*, not per turn, correlated by an engine-generated `turn_id`. That is the whole mechanism: SC#4's "each agent applies its own fallback chain" is not observable from a single per-turn row, because the second leg's `served_by` overwrites the first's. Two legs, two `served_by` values, two `fallback_trail` JSON blobs — and the round-trip test asserts they come back *distinct*, which is the assertion a per-turn design cannot satisfy.

**`handoffs` records attempts, not outcomes.** A rejected handoff produces no `runs` row and no `turn_legs` row. Without a table that records the attempt itself, a wrong reroute is not merely hard to reconstruct — it is invisible, and MESH-05 fails silently while looking fine (T-04-07). Every field except the two correlation keys defaults to `None`, so a bare rejection with no observer, no reroute and no timing constructs cleanly. The round-trip test asserts that specific shape: `observer_verdict`, `observer_profile` and `rerouted_to` all NULL, `detail` carrying the rejection message.

**Neither table has a foreign key, and that is deliberate rather than sloppy.** `PRAGMA foreign_keys=ON` is on and stays on. The writer is fire-and-forget and never surfaces `lastrowid`, so no producer can learn the run id — an FK to `runs` would be unfillable, and every mesh insert would fail the constraint. This is the same documented reason `fallback_trail` was denormalized onto `runs` in Phase 3, so the mesh follows a precedent rather than inventing an exception. `test_mesh_tables_carry_no_foreign_key` also re-asserts that `tool_calls`' real FK survives, so "FK-free" cannot quietly become "FKs disabled".

**Three columns exist for a thing that does not exist yet.** `observer_verdict`, `observer_profile` and `rerouted_to` belong to plan 04-07 and are written by nothing today. Declaring them now is not speculative generality — it is the only moment they *can* be declared, since 04-07 would face the exact no-op it is exempt from now. The column test asserts them by name for the same reason.

**`TraceStore` is byte-unchanged.** Not an accident worth glossing over: the Phase-2 writer takes `sql, params = event.as_sql()` and executes whatever it gets, so a new record type costs a dataclass and a `CREATE TABLE`. Two new event types entered the store with zero lines of writer change.

## Key Decisions

| Decision | Why |
|----------|-----|
| New tables, never a column on `runs` | The alternative is green in CI forever and broken on every existing install. `runs`' and `tool_calls`' `CREATE TABLE` blocks are byte-identical after this plan (verified in the diff). |
| No `FOREIGN KEY` on either table | Unfillable by construction — the writer never surfaces `lastrowid`. An FK plus `foreign_keys=ON` would reject every mesh insert, converting a design smell into a total outage. |
| Observer columns declared now | 04-07 has no way to add them. The cost of three unused nullable columns is nil; the cost of needing them later is a `paaf-trace` migration subsystem. |
| `outcome` / `observer_verdict` are plain TEXT, not `CHECK`-constrained | A `CHECK` is part of the table definition. Adding `budget_exhausted` (04-03) or a new verdict later would hit the identical Pitfall-5 wall the whole plan exists to avoid. The enumerations live in the SQL comment and in the events that write them. |
| The reopen test inlines the Phase-3 DDL | Building "the old database" from `read_schema()` would compare the new schema to itself. It would pass on the day the schema is wrong, which is the only day it matters. |
| Read back with stdlib `sqlite3`, not `aiosqlite` | A second, independent client proves the row is on disk and committed rather than visible only through the writer's own connection. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `read_schema()`'s docstring named a two-table schema**

- **Found during:** Task 1
- **Issue:** `paaf_trace/__init__.py`'s `read_schema()` docstring read *"Return the trace-store DDL (``runs`` + ``tool_calls``) as raw SQL text."* That became false the moment the mesh tables landed. It is the docstring on the single function that *is* the schema contract, so a stale one there is the most misleading place for it to be — and the plan's own file list did not include the file.
- **Fix:** rewrote it to name all four tables and to distinguish the Phase-3 pair from the Phase-4 FK-free pair. No behavior change.
- **Files modified:** `packages/paaf-trace/src/paaf_trace/__init__.py`
- **Commit:** `0d071a7`

**2. [Rule 3 - Blocking] The plan's `ruff format --check packages/paaf-trace` gate is red at baseline**

- **Found during:** Task 1
- **Issue:** `<verification>` lists `uv run ruff format --check packages/paaf-trace` as a gate. It reports four files that would be reformatted **before this plan touched anything** — `metrics.py`, `test_trace_no_egress.py`, `test_trace_queue.py`, `test_ttfa_regression.py`, none of them in this plan's file list. Same root cause as 04-01's deferred item: `ruff` is unpinned in the dev group and no CI job runs the check.
- **Fix:** applied the 04-01 precedent rather than reformatting four unrelated files inside a schema plan — every file this plan *touches* is verified format-clean individually (`ruff format --check` passes on all five). The pre-existing drift is recorded under the existing deferred item, now covering both packages.
- **Files modified:** `.planning/phases/04-agent-mesh/deferred-items.md`
- **Commit:** `0d071a7`

**3. [Rule 1 - Bug] Marking MESH-05 complete from this plan's frontmatter was premature — reverted**

- **Found during:** state updates
- **Issue:** the plan's frontmatter declares `requirements: [MESH-05]`, so the standard `requirements.mark-complete MESH-05` step flipped REQUIREMENTS.md to `- [x]` / `Complete`. But **04-06 and 04-09 also carry MESH-05**, and MESH-05 reads *"the trace **records** every handoff…"* — nothing writes to `handoffs` or `turn_legs` yet (04-04 and 04-06 own the emit sites). A `Complete` mark would let an audit read the requirement as satisfied while the recording path does not exist, which is precisely the vacuous-green failure this phase's brief warns about.
- **Fix:** reverted both the checkbox and the traceability row to `Pending`. 04-09, the last plan carrying MESH-05, is the correct place to mark it. This plan delivers the *substrate*, not the requirement.
- **Files modified:** `.planning/REQUIREMENTS.md`
- **Commit:** `bf3c688`

### Non-Vacuity Checks (per the wave-1 finding)

The plan prescribes one `-k` filter. It was checked for zero-selection before being reported:

| Command | Selected | Result |
|---------|----------|--------|
| `pytest packages/paaf-trace/tests/test_trace_schema.py -k reopen -x` | **1 of 5** (4 deselected), confirmed via `--collect-only -q` | passed |
| `pytest packages/paaf-trace/tests/test_trace_handoff_schema.py -q` | 5 collected (plan requires ≥ 4) | passed |

**The reopen test was additionally proved non-vacuous by falsification.** A scratch script built a DB with a `runs` table, then reopened it with a `CREATE TABLE IF NOT EXISTS runs (...)` that added a `turn_id` column. Result: `PRAGMA table_info` still reported the *two* original columns, and the insert raised `sqlite3.OperationalError: table runs has no column named turn_id`. Pitfall 5 is real, reproduced, and the reopen test's step-2 emits are what would hit it.

### Out of Scope — Logged, Not Fixed

**A SQL error inside `TraceStore._writer` kills the writer and deadlocks `stop()`.** Surfaced by the falsification above. The drain loop has no `except` around `await db.execute(...)`, so a rejected statement escapes the loop and the writer task dies; `finally: task_done()` releases only that one item, and every later event is never consumed, so `stop()`'s `await self._q.join()` waits forever. The failure mode is a hang, not an error — and `dropped` stays at `0`, because nothing was dropped, the writer simply stopped existing. Not fixed here: the plan explicitly holds `TraceStore` unmodified, and error handling on the single writer is a `paaf-trace` design change deserving its own plan. Recorded as deferred item 2 with a suggested `failed`-counter fix.

## Known Stubs

Each is a plan-assigned deferral. None blocks this plan's goal — the substrate is complete and nothing writes to it yet by design.

| Stub | File | Resolved by |
|------|------|-------------|
| Nothing in the engine emits `TurnLegEvent`; `Agent._drain` still writes one `runs` row per turn | `paaf_llm/agent.py` (other package) | 04-04 (one row per leg, correlated by 04-01's `turn_id`) |
| Nothing emits `HandoffEvent`; accepted and rejected attempts are not yet recorded at the call site | `paaf_llm/agent.py`, `mesh.py` | 04-04 |
| `observer_verdict`, `observer_profile`, `rerouted_to` are always NULL | `schema.sql` | 04-07 (the observer, D-05/D-07) |
| `handoffs.outcome = 'budget_exhausted'` is a declared value with no writer | `schema.sql` | 04-03 (hop budget, OQ-2) |
| `turn_legs.fallback_trail` will be identical across legs until per-agent chains exist | `schema.sql` | 04-06 (`ModelProfile.fallback_chain`, SC#4) |

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-06 Tampering (model-authored `to_agent` / `detail` reaching SQL) | mitigated | Both `as_sql()` implementations use a parameterized INSERT with an explicit column list and never interpolate; `test_mesh_events_are_placeholder_param_balanced` asserts `sql.count("?") == len(params)` for both event types and both the full and bare shapes, so an f-string-built query loses its inlined value from `params` and turns the suite red |
| T-04-07 Repudiation (rejected handoffs invisible) | mitigated | `handoffs` records attempts regardless of outcome; the round-trip test asserts the rejected row specifically, including that its three observer columns are NULL |
| T-04-08 DoS (silent no-op schema application) | mitigated | New tables only — `runs`' and `tool_calls`' `CREATE TABLE` blocks are byte-identical; `test_reopen_pre_phase4_database_gains_mesh_tables_and_loses_nothing` proves it against a real pre-existing file, and the failure mode was reproduced out-of-band to confirm the test bites |
| T-04-09 Info disclosure (trace contents) | accepted | Local-only; `test_trace_no_egress.py` re-run and green (2 passed), unaffected by the new tables |
| T-04-SC Dependency surface | accepted | Zero packages installed; `packages/paaf-trace/pyproject.toml` unchanged |

**Threat flags:** none. The plan's `<threat_model>` already names the schema change (T-04-08) as this plan's central surface; no *additional* endpoint, auth path, or trust boundary was introduced.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest packages/paaf-trace -q` | 27 passed (21 before this plan) |
| `uv run pytest -q` (workspace) | 245 passed, 1 skipped |
| `uv run pytest packages/paaf-trace/tests/test_ttfa_regression.py -q` | 5 passed — the Plan-09 TTFA gate is unaffected |
| `uv run pytest packages/paaf-trace/tests/test_trace_no_egress.py -x -q` | 2 passed — TRACE-05's no-egress control unaffected |
| `uv run ruff check packages/paaf-trace` | All checks passed |
| `uv run ruff format --check` (all five files this plan touches) | Clean (see deviation 2 for the pre-existing baseline drift) |
| `uv run lint-imports` | Contracts: 3 kept, 0 broken — `.importlinter` unchanged |
| All four of Task 1's inline `python -c` acceptance commands | exit 0 |
| Task 2's inline-literal check (`'CREATE TABLE IF NOT EXISTS runs' in test_trace_schema.py`) | exit 0 |

**Phase invariants re-checked at commit time:**

1. **No `ALTER TABLE`, no new column on `runs`** — `grep -rn "ALTER TABLE" packages/` returns only a docstring mention in the reopen test; the `runs` and `tool_calls` `CREATE TABLE` blocks have zero removed or changed lines in the diff (only the file header comment changed).
2. **`force-include`** — not applicable: `packages/paaf-trace/pyproject.toml` has no `[tool.hatch.build.targets.wheel.force-include]` section and ships no test set (only `paaf-llm` does, for the clean-venv gate). `pyproject.toml` is unchanged.
3. **`compose()` byte-exact** — `packages/paaf-llm` untouched (0 lines).
4. **`paaf prompt` default output** — `cli.py` untouched (0 lines).
5. **No handoff tool call in `Agent.history`; `Role` not widened** — no `paaf-llm` change.
6. **`langchain*` confined to `paaf_llm._engine`** — `lint-imports` green, `.importlinter` unchanged, no new carve-out.
7. **OQ-5 honoured** — one row per agent leg in `turn_legs`, correlated by the engine-generated `turn_id` (the schema comment states explicitly that it is never a `lastrowid`), plus the FK-free `handoffs` table recording REJECTED attempts.

**04-VALIDATION.md rows:** `reopen` is green here, selected by its documented `-k` command and confirmed to select exactly one test. The `legs` / `attempts` substrate is in place for 04-06.

## Self-Check: PASSED

- `packages/paaf-trace/tests/test_trace_handoff_schema.py` — FOUND
- `packages/paaf-trace/src/paaf_trace/schema.sql` — FOUND
- `packages/paaf-trace/src/paaf_trace/store.py` — FOUND
- Commit `0d071a7` — FOUND in `git log`
- Commit `34bab4e` — FOUND in `git log`
