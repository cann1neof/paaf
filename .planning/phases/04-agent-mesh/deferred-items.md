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

## 4. A reasoning model's thinking tokens reach `stream()` as empty chunks, and are dropped

**Found during:** plan 04-04, Task 2 — while running the live A1 check (`scripts/check_tool_streaming.py`).

Measured against local Ollama 0.32.1 with `qwen3.5:2b`. For the prompt *"Say the single word:
blue."*, the raw Ollama stream carries **154 chunks, of which 152 have a `thinking` field and
exactly 1 has `content`** (measured directly against `POST /api/chat`). Through
`langchain-ollama==1.1.0` the same stream arrives as 235 `AIMessageChunk`s whose `.content` is `''`
— the thinking text is not surfaced as text at all — so `LangChainAdapter.stream`'s empty-chunk drop
correctly yields nothing for the whole thinking period. End to end this measured **53.7 s and 78.1 s
to first token** on `qwen3.5:2b` and `qwen3.5:9b`, and one run where the plain path produced **zero**
text chunks in 88 s.

Two consequences:

- The empty-chunk drop is behaving exactly as designed (D-04/D-05: an empty chunk must not satisfy
  the first-token budget). But on a reasoning model the user-visible result is a long silence, and
  `first_token_budget_s` will trip and walk the fallback chain for a model that is working fine.
- It is **not** an A1 problem and does not touch this plan's change: with a tool bound the same
  prompt reached first token in **1.9–6.2 s** on the same two models. If anything the tools-bound
  path is the fast one here.

**Not fixed here** because it is a Phase-3 `stream()` / latency-policy question on the *plain* path,
outside this plan's objective and its file list, and the honest fix is a product decision (surface
thinking as its own channel? extend the budget for models that think? both?) rather than a bug fix.

**Suggested fix (separate change):** decide whether reasoning content is a first-class stream channel
(`langchain-ollama` can surface it via reasoning content blocks) or whether `first_token_budget_s`
needs a "model is thinking" exemption. Whichever, take the measurement above into Phase 9's TTFA gate
so the gate is not calibrated on non-reasoning models alone.
