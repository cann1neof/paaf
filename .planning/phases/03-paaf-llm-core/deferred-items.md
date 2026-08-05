# Phase 3 — Deferred Items

Out-of-scope discoveries logged during execution. These were NOT fixed, per the
executor scope boundary (only issues directly caused by the current task's
changes are auto-fixed).

| Found in | Item | Why deferred |
|----------|------|--------------|
| 03-01 | `packages/paaf-llm/tests/test_wheel_smoke.py:13` — ruff `I001` (import block un-sorted). `uv run ruff check packages/paaf-llm` is red on this one pre-existing file. | Pre-existing since Phase 2 (`5d6ee7f`), unrelated to plan 03-01's files. One-line fix (`ruff check --fix`), but it belongs to whichever plan next touches the wheel-smoke surface (03-09 extends the wheel job). |
