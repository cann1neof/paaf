# Phase 04 — Deferred Items

Out-of-scope discoveries found during execution. Logged, not fixed (executor scope boundary).

## 1. Pre-existing `ruff format` drift across `packages/paaf-llm` and `packages/paaf-trace`

**Found during:** plan 04-01, Task 1 (`paaf-llm`); confirmed again in plan 04-02, Task 1
(`paaf-trace`).

`uv run ruff format --check packages/paaf-llm` reports 6 files that would be reformatted at
baseline — before this phase touched anything:

- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- `packages/paaf-llm/src/paaf_llm/cli.py`
- `packages/paaf-llm/src/paaf_llm/profiles.py`
- `packages/paaf-llm/tests/test_engine_adapter.py`
- `packages/paaf-llm/tests/test_inspector.py`
- `packages/paaf-llm/tests/test_profiles.py`

`uv run ruff format --check packages/paaf-trace` reports 4 more, likewise untouched by this phase:

- `packages/paaf-trace/src/paaf_trace/metrics.py`
- `packages/paaf-trace/tests/test_trace_no_egress.py`
- `packages/paaf-trace/tests/test_trace_queue.py`
- `packages/paaf-trace/tests/test_ttfa_regression.py`

Every diff is cosmetic (a blank line after a module docstring, string-concat wrapping). The cause
is that `ruff` is declared unpinned in the dev group (`pyproject.toml`) and the locally resolved
`0.16.0` formats slightly differently from whatever version last formatted these files. **No CI
workflow runs `ruff format --check`**, so nothing turned red.

**Not fixed here** because reformatting six unrelated files inside a mesh plan would bury the
plan's real diff. Files this phase actually touches are kept format-clean individually.

**Suggested fix (separate change):** pin `ruff` to an exact version in the dev group, run
`uv run ruff format` once across the workspace, and add a `ruff format --check` step to CI so the
drift cannot silently return.

## 2. A SQL error inside `TraceStore._writer` kills the writer and deadlocks `stop()`

**Found during:** plan 04-02, Task 2 — while proving the Pitfall-5 reopen test is non-vacuous.

`_writer`'s drain loop has no `except` around `await db.execute(sql, params)`. If any event yields
SQL the database rejects (the exact Pitfall-5 failure mode: `sqlite3.OperationalError: table runs
has no column named turn_id`, reproduced in a scratch script), the exception escapes the loop and
the writer task dies. `finally: task_done()` marks only that one item done, so every event emitted
afterwards is never consumed and `stop()`'s `await self._q.join()` waits forever. The failure
surfaces as a **hung test / hung shutdown**, not as an error.

Two consequences worth naming: the drop counter stays at `0` (nothing was dropped — the writer just
stopped existing), and the exception itself is never logged anywhere.

**Not fixed here** because the plan explicitly holds `TraceStore` unmodified — the writer is
event-agnostic by design and this plan's whole point is that a new record type needs no writer
change. Changing error handling on the single writer is a `paaf-trace` design change that deserves
its own plan.

**Suggested fix (separate change):** catch `sqlite3.Error` per event inside the loop, count it on a
`failed` counter beside `dropped`, and keep draining — so a bad event loses one row instead of
silencing the trace and hanging shutdown. Assert `store.failed == 0` alongside `store.dropped == 0`
in the round-trip tests.

## 3. `mypy` cannot narrow `self._adapter` at `agent.py`'s tool-path call site

**Found during:** plan 04-04, Task 1 — while checking the "public API leaks no framework type" gate.

`uv run mypy packages/paaf-llm/src` reports:

```
packages/paaf-llm/src/paaf_llm/agent.py:566: error: "ChatAdapter" has no attribute
"stream_with_tools"  [attr-defined]
```

The `isinstance(self._adapter, ToolCallingChatAdapter)` check is stored in the local `with_tools`
alongside `tool_path`, so by the time the call is made mypy has lost the narrowing — the runtime
behavior is correct and covered, the type checker simply cannot see it. Pre-existing: introduced by
plan 04-01 (`_run_chain`'s feature detection) and widened by 04-03's `tool_path` argument, both
before this plan. Verified untouched by 04-04, whose only source change is in `_engine/__init__.py`.

The other three mypy diagnostics in that run are missing third-party stubs (`yaml`,
`paaf_trace.store`) and are likewise pre-existing. **No CI workflow runs `mypy`**, so nothing is red.

**Not fixed here** because `agent.py` is outside this plan's file list, and `_run_chain` is edited
again by 04-06 and 04-07 — a narrowing fix landed now would collide with both.

**Suggested fix (separate change):** narrow into a local of the protocol type, e.g.
`tool_adapter = self._adapter if isinstance(self._adapter, ToolCallingChatAdapter) else None`, and
branch on `tool_path and tool_adapter is not None`. Then add `mypy` (and `ruff format --check`, per
item 1) to CI so neither gate can drift unobserved again.
