---
phase: 03-paaf-llm-core
plan: 13
subsystem: llm-core
tags: [python, cli, trace, sqlite, asyncio, tdd, gap-closure]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "paaf_trace.store.TraceStore (02) — WAL SQLite, bounded queue, single writer task; Agent._drain + RunEvent.served_by/fallback_trail (06); ports.EngineError as a framework-free catchable type and the chat error handlers (10); cli._default_adapter's secret_store keyword and open_secret_store (11)"
provides:
  - "paaf chat --trace-db PATH — the shipped command now writes a real runs row per served turn"
  - "cli._chat_session — a session coroutine that owns the trace store's lifecycle inside the running loop"
  - "The first assertions in the repo that read the trace database back with the stdlib sqlite3 module"
  - "Gap 4 of 03-VERIFICATION closed: the cli -> TraceStore -> Agent._drain -> runs data flow is connected"
affects: [04-agent-mesh, 09-embedded-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A resource whose lifetime is an asyncio task belongs to a coroutine, not to a parameter: the store, and therefore the agent handed it as a sink, are constructed inside asyncio.run"
    - "stop() in a finally is the difference between a trace and a trace-when-things-went-well"
    - "Read the artifact back with the standard library, not through the code that wrote it — a store that never wrote can still satisfy its own reader"
    - "A CLI does not invent a filesystem path: an opt-in flag makes a sink real and testable without PAAF choosing a location on the user's behalf"

key-files:
  created: []
  modified:
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/test_inspector.py

key-decisions:
  - "The trace file is NAMED BY THE USER, not defaulted. A CLI that created a database at an invented path would be writing files nobody asked for, and Phase 9 (APP-*) owns filesystem conventions for the daemon. This is the same call 03-11 made when it refused to invent a default secrets path, and it is kept consistent deliberately."
  - "build_agent moved into a new _chat_session coroutine rather than gaining a trace= parameter at the call site. TraceStore owns a writer task and a bounded asyncio.Queue, both of which bind to the running loop; a store constructed before asyncio.run would bind its queue to a loop that never runs it, and the agent cannot be handed a sink that has not started."
  - "03-10's `except EngineError -> _config_failure` handler moved down with build_agent, unchanged. Leaving it in `chat` would have made it unreachable while still looking correct — the most misleading possible outcome for the plan that exists to fix an unreachable code path."
  - "The recorded `prompts` column is asserted against the system message the ADAPTER received (adapter.calls[0][1][0].content), not against a re-composition. That is the same standard the byte-exact inspector tests at the top of the file hold themselves to, and it is what makes the trace incapable of understating what was sent (T-03-17/18)."
  - "Task 2's RED is a mutation check, not a pre-implementation failure — it adds only tests against behavior Task 1 implemented. Three mutations were introduced and observed to turn the suite red, then reverted (03-11/03-12 precedent)."

patterns-established:
  - "Stdlib read-back for on-disk artifacts: assert the file exists and holds rows using sqlite3, independent of paaf_trace"
  - "A lifecycle negative control replaces the CONSTRUCTOR with a failing callable, not just the write path — 'created a store and wrote nothing' and 'created no store' are different products"

requirements-completed: [MODEL-04]

coverage:
  - id: D1
    description: "paaf chat --trace-db writes exactly one committed runs row per served turn, carrying the prompt that crossed the port, the serving profile, and an empty trail"
    requirement: MODEL-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_chat_with_a_trace_db_writes_a_run_row"
        status: pass
      - kind: other
        ref: "mutation A — build_agent given trace=None (the shipped Gap-4 defect); 3 trace tests failed; reverted"
        status: pass
    human_judgment: false
  - id: D2
    description: "The fallback hop the user SAW is recoverable from the database with the same reason string (D-06)"
    requirement: MODEL-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_the_trace_row_records_the_fallback_trail_the_user_was_shown"
        status: pass
    human_judgment: false
  - id: D3
    description: "Without --trace-db no store is constructed and no file is written anywhere"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_chat_without_a_trace_db_writes_nothing (cli.TraceStore replaced with a failing callable + a tmp_path listing comparison)"
        status: pass
      - kind: other
        ref: "mutation C — TraceStore(trace_db_path or 'paaf-trace.db'); the control failed with 'a trace store was constructed for a run with no --trace-db'; reverted"
        status: pass
    human_judgment: false
  - id: D4
    description: "A session that ends in a readable error still flushes the rows it had (Constraint 5, T-03-42)"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_failing_session_still_flushes_its_rows"
        status: pass
      - kind: other
        ref: "mutation B — store.stop() moved out of the finally onto the happy path; only that control failed (assert 0 >= 1); reverted"
        status: pass
    human_judgment: false
  - id: D5
    description: "build_agent left the chat command body and lives in _chat_session, decidably (parsed, not counted)"
    verification:
      - kind: other
        ref: "ast acceptance check: 'build_agent(' not in chat, 'asyncio.run(_chat_session' in chat, 'build_agent(' in _chat_session — prints ok"
        status: pass
    human_judgment: false
  - id: D6
    description: "The phase gate holds with all four gap-closure plans merged: the full shipped suite passes in a clean off-repo venv with langchain and langgraph genuinely unimportable"
    verification:
      - kind: other
        ref: "bash scripts/check_framework_uninstalled.sh — PASS, 128 passed, 11 fake-adapter test files shipped"
        status: pass
    human_judgment: false

# Metrics
duration: 32min
completed: 2026-08-06
status: complete
---

# Phase 3 Plan 13: The Trace Became a File on Disk Summary

**`paaf chat --trace-db` now leaves a real, committed `runs` row per turn — carrying the exact prompt that crossed the port, which profile served it, and every fallback hop with the same reason string the user watched scroll past**

## Performance

- **Duration:** ~32 min of active execution
- **Tasks:** 2 (Task 1 TDD RED → GREEN; Task 2 test-only, mutation-checked)
- **Files modified:** 2
- **Files created:** 0

## Accomplishments

- **Closed Gap 4 of `03-VERIFICATION.md`.** Both sides of the seam were built and verified — plan 03-02 added `served_by` and `fallback_trail` to the `runs` schema, plan 03-06 drains them out of `Agent._drain` — but `cli.py` called `build_agent(config)` with no `trace=` sink, so `_drain` returned on its first line and **the shipped command never wrote a row**. SC#4's "authoritative record" and D-06's "each fallback trigger reason is recorded in the trace" were true of the library and false of `paaf chat`. They are now true of both.
- **D-06's loop is closed end to end, which no test previously did.** `test_the_trace_row_records_the_fallback_trail_the_user_was_shown` asserts the terminal printed `↳ fell back to cloud (connection)` AND that `json.loads(row["fallback_trail"])` is `[{"from": "local", "to": "cloud", "reason": "connection"}]` AND that the parsed `reason` is a substring of the printed notice. The user's view and the record on disk cannot drift.
- **The store's lifecycle is a coroutine, not a parameter.** `TraceStore` owns a writer task and a bounded `asyncio.Queue`, both bound to the running loop. `_chat_session` is where the sink is created, started, handed to the agent, and — in a `finally` — stopped. Mutation B proves that placement is load-bearing rather than stylistic.
- **The flag is the whole security posture, and it is proven load-bearing.** Nothing is written and no store is even constructed without `--trace-db` (T-03-44). The negative control replaces `cli.TraceStore` itself, so "created a store at a default path and merely wrote nothing" cannot pass.

## Task Commits

| # | Task | Commits |
|---|------|---------|
| 1 | `paaf chat --trace-db` writes a real run row | `d87d192` (test, RED) → `3911379` (feat, GREEN) |
| 2 | The fallback trail lands in the trace; nothing is written without the flag | `fcfec66` (test, mutation-checked) |

No REFACTOR commit was needed. **RED was observed, not assumed:**

- **Task 1 RED:** 1 failed, 28 passed — `Error: No such option '--trace-db'.` (exit code 2).
- **Task 2** is test-only, so its RED is a **mutation check** — three of them, recorded below.

## The final `_chat_session` signature

Recorded verbatim as the plan's `<output>` requires.

```python
async def _chat_session(
    config: LlmConfig,
    *,
    show_prompt: bool,
    console: Console,
    secret_store: SecretResolver | None,
    trace_db_path: str | None,
) -> None:
```

Its body, which is the substance of this plan:

```python
    store = TraceStore(trace_db_path) if trace_db_path is not None else None
    if store is not None:
        # Returns once the schema is applied, so the sink is usable immediately.
        await store.start()
    try:
        # The second reachable config-failure site: the factory validates every
        # declared profile's provider before a single turn runs, so a config
        # error can land here rather than mid-conversation.
        try:
            agent = build_agent(config, secret_store=secret_store, trace=store)
        except EngineError as exc:
            raise _config_failure(exc) from exc
        await _chat_loop(agent, show_prompt=show_prompt, console=console)
    finally:
        if store is not None:
            await store.stop()
```

The inner `try` is 03-10's handler **moved down unchanged**, not rewritten. Leaving it in `chat` would have left it attached to a `build_agent` call that no longer exists there — an unreachable handler that still looks correct, which is precisely the class of defect this plan exists to fix.

## The exact `--trace-db` help text

Recorded verbatim as the plan's `<output>` requires. Wrapped by click at render time; the source string is:

```
Record each turn — the prompt sent, which profile served it, and every fallback
hop — into a local SQLite file at this path, created on first use. Nothing is
written unless you give this flag.
```

`uv run paaf chat --help` lists `--config`, `--show-prompt`, `--secrets`, `--trace-db`, `--help` — both 03-11's flag and this plan's are present, as the acceptance criterion requires. The option is `click.Path(dir_okay=False, writable=True)` with **no** `exists` requirement, because the database is created on first use.

## `scripts/check_framework_uninstalled.sh` — the SC#1 gate

Recorded as the plan's `<output>` requires. Run last, alone, with all four gap-closure plans (03-10 … 03-13) merged into this worktree's history.

```
==> Asserting the wheel ships every fake-adapter test file in the source tree
ok: all 11 fake-adapter test files ship in the wheel
ok: deliberately excluded (runs in the engine-adapter job): ['test_engine_adapter.py']
==> Running the FULL fake-adapter suite via pytest --pyargs paaf_llm
128 passed in 1.93s
==> Asserting langchain and langgraph are NOT importable in the clean venv
ok: langchain is not importable (as required)
ok: langgraph is not importable (as required)
==> PASS
```

**Result: PASS. 128 tests passed** in a clean off-repo venv with `langchain` and `langgraph` genuinely unimportable. This matters more than usual here: `cli.py` gained a module-scope `from paaf_trace.store import TraceStore`, and this gate is what proves that import reaches the wheel through the declared `paaf-trace` dependency rather than through the repo checkout.

## No new test file was added under `packages/paaf-llm/tests/` across 03-10 … 03-13

Stated explicitly because the plan's `<output>` asks for it, and because it is a fact the gate above measures rather than one this executor merely asserts.

`check_framework_uninstalled.sh` enumerates the fake-adapter test files in the source tree and asserts every one of them ships in the wheel. It reports **11 files**, with `test_engine_adapter.py` deliberately excluded (it runs in the `[engine]` job). Had any of the four gap-closure plans added a twelfth file without updating `pyproject.toml`'s `force-include`, this gate would have failed. It passed, so:

- **03-10** — tests in `test_inspector.py` and existing files. No new file.
- **03-11** — tests in `test_inspector.py` and `test_engine_adapter.py`. No new file.
- **03-12** — tests in `test_profiles.py`, `test_engine_adapter.py`, `test_endpoint_declaration.py`. No new file (confirmed in its own SUMMARY, Constraint 5).
- **03-13** — tests in `test_inspector.py`. No new file.

**Across all four plans: zero new test files under `packages/paaf-llm/tests/`.** Neither `pyproject.toml`'s `force-include` nor `EXCLUDED_FROM_WHEEL` needed touching, and no `pyproject.toml` was modified.

## Task 2's mutation checks

Task 2 adds only tests, so all three passed the moment they were written. A control that has never been seen to fail is a claim, not a control (03-11's precedent, followed by 03-12). Each was mutation-checked against the exact defect it names.

**Mutation A — `build_agent(config, secret_store=secret_store, trace=None)`.** This *is* the shipped Gap-4 defect, reintroduced verbatim: the store is constructed, started, and stopped correctly, and the agent simply is not given it.

```
FAILED test_chat_with_a_trace_db_writes_a_run_row
FAILED test_the_trace_row_records_the_fallback_trail_the_user_was_shown
FAILED test_a_failing_session_still_flushes_its_rows
3 failed, 29 passed
```

Note which test did **not** fail: `test_chat_without_a_trace_db_writes_nothing` stayed green, as it must — it is a control over construction, not over writing.

**Mutation B — `store.stop()` moved out of the `finally` onto the happy path.** The realistic wrong implementation: it satisfies every positive assertion, because a session that ends normally still flushes.

```
>       assert len(rows) >= 1
E       assert 0 >= 1
FAILED test_a_failing_session_still_flushes_its_rows
1 failed, 31 passed
```

Exactly one test failed, which is the right shape: this is a defect visible only on the error path.

**Mutation C — a default trace path** (`TraceStore(trace_db_path or "paaf-trace.db")`), the "helpful" behavior this plan refused.

```
>       pytest.fail("a trace store was constructed for a run with no --trace-db")
E       Failed: a trace store was constructed for a run with no --trace-db
FAILED test_chat_without_a_trace_db_writes_nothing
1 failed, 31 passed
```

Worth noting: the *file-listing* half of that test would have passed against this mutation, because `paaf-trace.db` lands in the process CWD rather than in `tmp_path`. Only the constructor replacement caught it. That is the second half the plan insisted on, and it earned its place.

All three mutations were reverted with `git checkout -- packages/paaf-llm/src/paaf_llm/cli.py`; `git status --short` afterwards showed **only the test file modified**, confirming no mutation leaked into a commit.

## Files Modified

- **`packages/paaf-llm/src/paaf_llm/cli.py`** — a module-scope `from paaf_trace.store import TraceStore` (framework-free, and not subject to the lazy-adapter rule, which applies only to the agent framework; `paaf_llm.agent` already imports `RunEvent` from the same module at module scope, so `paaf_trace.store` was loaded before `cli` finished importing either way). The new `_chat_session` coroutine. A `--trace-db` option on `chat`. The `chat` body reduced to: load config, make console, render profiles, open the secret store, `asyncio.run(_chat_session(...))`. A new module-docstring paragraph stating that the trace is opt-in and that PAAF names no file on the user's behalf.
- **`packages/paaf-llm/tests/test_inspector.py`** — `import json`, `import sqlite3`, a new `MODEL-04 / D-06: the trace on disk` section holding `read_runs`, four tests, and the `_ServesOnceThenFailsAdapter` local adapter.

**Unchanged, by Constraint 2:** `Agent._drain`, `RunEvent`, `paaf_trace.store.TraceStore`, `packages/paaf-trace/src/paaf_trace/schema.sql`. **Unchanged by Constraint 4:** `_chat_loop`'s signature and body. **No new file, no new dependency, no `pyproject.toml` change** (Constraint 3, T-03-SC).

## Constraints Honoured

| # | Constraint | Status |
|---|------------|--------|
| 1 | Do not modify `03-01`…`03-09` or any `-SUMMARY.md` | Held — no planning file touched except this new summary |
| 2 | Do not change `Agent._drain`, `RunEvent`, the schema, or `TraceStore` | Held — `git diff ea4b1ee..HEAD --name-only` lists exactly `cli.py` and `test_inspector.py` |
| 3 | No new test file under `packages/paaf-llm/tests/` | Held — and measured by the SC#1 gate's 11-file assertion, not merely asserted |
| 4 | `_chat_loop`'s signature and body stay as they are | Held — untouched; its seven pre-existing tests pass unchanged |
| 5 | The store must be stopped in a `finally` | Held — and mutation B demonstrates the alternative loses rows |
| 6 | Do not await `emit`; add no second call site | Held — `cli.py` contains no `emit` call at all; `Agent._drain` remains the only one |

## Deviations from Plan

One, and it is a formatting adjustment rather than a change of substance.

### Adjustments

**1. [Rule 3 — Blocking] `uv sync --all-packages` needed before anything would run**
- **Found during:** baseline, before any edit
- **Issue:** A fresh worktree has no populated `.venv`; the suite could not be collected.
- **Fix:** Ran `uv sync --all-packages`. Environment-only; no file changed. Baseline established green (**202 passed, 1 skipped**) *before* any edit, so the Task 1 RED reported above is a real RED rather than an artifact of a broken environment.

**2. The `asyncio.run(_chat_session(...))` call is written in "hugged" form**
- **Found during:** Task 1 acceptance checks
- **Issue:** The natural multi-line formatting puts `asyncio.run(` and `_chat_session(` on separate lines, which makes the plan's own AST acceptance check — `assert 'asyncio.run(_chat_session' in b['chat']` — fail on a correct implementation. The check is a decidable criterion the plan chose deliberately over `grep -c`, so the source was written to satisfy it literally.
- **Fix:** `asyncio.run(_chat_session(` on one line, arguments indented below, closing `))`. Verified this is not a lint issue: the repo enforces `ruff check` only (no `ruff format` in `pyproject.toml`, `scripts/`, or `.github/`), and `uv run ruff check packages/paaf-llm` reports **All checks passed**.

### Out of scope — logged, not fixed

**The pre-existing `RUF022` finding in `packages/paaf-core/src/paaf_core/secrets/__init__.py`** (`__all__` is not sorted). Unrelated to this plan, in a file this plan does not touch, and already logged as out-of-scope by 03-12. The plan's step-7 expectation was "only the two pre-existing `PLW1510`" because it was written before 03-12 discovered this third one; it is the same pre-existing finding, not a new one. Per the executor scope boundary it was **not** fixed.

---

**Total deviations:** 2 (1 blocking environment fix, 1 formatting adjustment to satisfy a stated acceptance check) + 1 out-of-scope finding logged
**Impact on plan:** None on scope.

## Verification Results

All seven of the plan's `<verification>` steps were run, in order, with the gate run alone.

| # | Check | Result |
|---|-------|--------|
| 1 | `uv run pytest -q --disable-socket` (whole workspace) | **206 passed, 1 skipped** (baseline was 202 + 1) |
| 2 | `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` | **45 passed** |
| 3 | `uv run lint-imports --no-cache` | **3 contracts kept, 0 broken** |
| 4 | `bash scripts/check_wheel_independence.sh` | **PASS** — 128 passed in the clean venv; `paaf_voice` and `langchain` confirmed not importable, `paaf_trace` confirmed importable as a declared dependency |
| 5 | `bash scripts/check_framework_uninstalled.sh` (SC#1) | **PASS** — 128 passed, 11 fake-adapter test files shipped, `langchain`/`langgraph` genuinely unimportable |
| 6 | `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` | **35 passed, 0 skipped** — then `uv sync --all-packages` restored the baseline |
| 7 | `uv run ruff check packages/paaf-llm packages/paaf-core packages/paaf-trace scripts tests` | **3 findings, all pre-existing, none from this plan's files** — two `PLW1510` in `tests/negcontrol/test_import_boundary.py` (recorded by the verifier) and one `RUF022` in `paaf_core/secrets/__init__.py` (recorded by 03-12) |

Acceptance-criteria checks, all satisfied:

| Criterion | Required | Result |
|---|---|---|
| `grep -c 'trace=store' cli.py` | `1` | `1` |
| `grep -c 'await store.stop()' cli.py` | `1`, guarded on the line above | `1`, preceded by `if store is not None:` inside the `finally` |
| AST check: `build_agent(` absent from `chat`, `asyncio.run(_chat_session` present, `build_agent(` present in `_chat_session` | prints `ok` | prints `ok` |
| `uv run paaf chat --help` lists `--secrets` and `--trace-db` | both | both |
| `test_inspector.py` passes, all seven pre-existing `chat` tests unchanged | 0 failures | **32 passed** (was 28 at baseline) |
| `test_chat_with_a_trace_db_writes_a_run_row` imports stdlib `sqlite3`, asserts `len(rows) == 1` | yes | yes |
| the trail test asserts on `json.loads(...)`, not a substring of raw JSON | yes | yes — `trail == [{"from": "local", "to": "cloud", "reason": "connection"}]` |
| the negative control replaces `cli.TraceStore` with a failing callable | yes | yes |
| the flush test asserts non-zero exit AND `len(rows) >= 1` | yes | yes |
| whole-package suite: 0 failures, 1 skip | yes | **204 passed, 1 skipped** for `paaf-llm`+`paaf-core`+`paaf-trace` |

## Threat Model Disposition

| Threat ID | Disposition | Status |
|---|---|---|
| T-03-41 (the `runs` table records the full composed system prompt) | accept | **Accepted as planned.** This is D-06 / SC#4's own design and `RunEvent.prompts` already carried it. The user's exposure is bounded by the fact the file is created ONLY when they name it with `--trace-db`; `test_chat_without_a_trace_db_writes_nothing` is what makes that bound real. The trace stays local-only — `lint-imports`' `no-network-client-in-framework` contract is KEPT (TRACE-05 / PRIV-02). |
| T-03-42 (rows lost when the command exits or the session fails) | mitigate | **Held, and demonstrated.** `stop()` in a `finally` joins the bounded queue, so every emitted event is written and committed. Mutation B introduced the defect and turned `test_a_failing_session_still_flushes_its_rows` red with `assert 0 >= 1`. |
| T-03-43 (trace writes stalling the conversation) | mitigate | **Held vacuously, as intended.** This plan adds no `emit` call site — `cli.py` contains none — and awaits nothing on the turn path. `TraceStore.emit` remains `put_nowait` on a bounded queue with a drop counter, unchanged (Constraint 6). |
| T-03-44 (PAAF creating a database at a path the user did not choose) | mitigate | **Held, and demonstrated.** No default path. Mutation C introduced one and the negative control failed at the constructor — notably before the file-listing assertion could even be reached, since a CWD-relative default would not have landed in `tmp_path` at all. |
| T-03-SC (package installs) | mitigate | **Held vacuously, as intended.** No package installed, no dependency list edited; `aiosqlite` arrives through the declared `paaf-trace` dependency. Both `check_wheel_independence.sh` and `check_framework_uninstalled.sh` PASS, and the latter confirms `paaf_trace` is importable in a clean venv from the declared dependency alone. |

**One new security-relevant surface, and it is T-03-41 above:** PAAF now writes the full composed system prompt to a local file. It is the phase's own design, it is opt-in, and it is bounded by a proven negative control. **No threat flags.**

## Known Stubs

None. Nothing in this plan renders placeholder data or leaves a component unwired — closing an unwired component is what the plan was for.

## Scope Note — what this plan does NOT claim

- **MODEL-04 is claimed as recorded evidence, not as a second implementation.** `03-VERIFICATION.md` already records it ✓ SATISFIED at the library level (four fallback triggers, parametrized, with a non-vacuity control). No new fallback behavior was written here. What this plan adds is the **provenance** of that behavior reaching disk from the shipped command — the `runs` row carrying `served_by` and the per-hop `reason`, which is what makes a degraded-provider hop recoverable after the fact instead of only observable while it scrolls past.
- **MODEL-03 is deliberately NOT claimed.** The ordered chain surviving an unreachable provider is 03-06's work and 03-10 guards its boundary condition; this plan only reads the trail that chain produced. Padding `requirements` with it would make the phase traceability table assert coverage these two tasks do not produce.
- **No live provider was contacted.** Every check is decidable offline under `--disable-socket`.
- `REQUIREMENTS.md`, `STATE.md` and `ROADMAP.md` were intentionally **not** edited by this worktree agent — those are shared-file writes the orchestrator owns after the wave merges.

## User Setup Required

None. Every check in this plan is decidable offline, and the new flag needs no configuration.

**What the user can now do that they could not before:**

```bash
# Record a session. The file is created on first use; nothing is written without the flag.
uv run paaf chat --config paaf.yaml --trace-db ~/paaf-trace.db

# Read it back with anything that speaks SQLite — no PAAF tooling required.
sqlite3 ~/paaf-trace.db \
  "SELECT served_by, fallback_trail, started_at FROM runs ORDER BY id;"
```

That second command is the point of the phase stated as a shell one-liner: the record of which model answered, and why not the one you picked, is a file you own and can read with a tool we did not write.

## Next Phase Readiness

- **All four gaps recorded in `03-VERIFICATION.md` are closed** with 03-10 … 03-13 merged. The four Human Verification items in that report remain open by design — they need live providers or a physical WAN cut, and the suite is socket-disabled on purpose. 03-11 and 03-12 each note in their own SUMMARY which manual checks they make possible.
- **`_chat_session` is the seam Phase 9 will want.** APP-* needs the same construction — start the sink, build the agent against it, stop it in a `finally` — driven by a daemon rather than by stdin. The coroutine already isolates that shape from the click command wrapping it.
- **The `--trace-db` decision is a precedent to keep, not to revisit.** 03-11 refused to invent a default secrets path and this plan refused to invent a default trace path, both deferring to Phase 9 (APP-*) for filesystem conventions. Phase 9 should decide both at once, in one place.
- **Environment note for the next executor:** the worktree is left synced with `uv sync --all-packages` (no `[engine]` extra), matching the documented baseline. In that state the whole workspace reports **206 passed, 1 skipped**.

## Self-Check: PASSED

- Both claimed files verified present on disk.
- All 3 claimed commits (`d87d192`, `3911379`, `fcfec66`) verified present in `git log`.
- `git diff --diff-filter=D --name-only ea4b1ee..HEAD` reports no deleted files — nothing was removed by this plan.
- `git diff --name-only ea4b1ee..HEAD` lists exactly `packages/paaf-llm/src/paaf_llm/cli.py` and `packages/paaf-llm/tests/test_inspector.py` — Constraint 2 confirmed by the diff, not by inspection.
- All three mutation checks confirmed reverted: `git status --short` after each showed only the intended test file modified.
- No untracked files left behind (`git status --short` empty after the final suite run).

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-06*
