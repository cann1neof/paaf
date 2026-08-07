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
