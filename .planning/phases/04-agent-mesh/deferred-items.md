# Phase 04 — Deferred Items

Out-of-scope discoveries found during execution. Logged, not fixed (executor scope boundary).

## 1. Pre-existing `ruff format` drift across `packages/paaf-llm`

**Found during:** plan 04-01, Task 1.

`uv run ruff format --check packages/paaf-llm` reports 6 files that would be reformatted at
baseline — before this phase touched anything:

- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- `packages/paaf-llm/src/paaf_llm/cli.py`
- `packages/paaf-llm/src/paaf_llm/profiles.py`
- `packages/paaf-llm/tests/test_engine_adapter.py`
- `packages/paaf-llm/tests/test_inspector.py`
- `packages/paaf-llm/tests/test_profiles.py`

Every diff is cosmetic (a blank line after a module docstring, string-concat wrapping). The cause
is that `ruff` is declared unpinned in the dev group (`pyproject.toml`) and the locally resolved
`0.16.0` formats slightly differently from whatever version last formatted these files. **No CI
workflow runs `ruff format --check`**, so nothing turned red.

**Not fixed here** because reformatting six unrelated files inside a mesh plan would bury the
plan's real diff. Files this phase actually touches are kept format-clean individually.

**Suggested fix (separate change):** pin `ruff` to an exact version in the dev group, run
`uv run ruff format` once across the workspace, and add a `ruff format --check` step to CI so the
drift cannot silently return.
