---
phase: 04-agent-mesh
plan: 08
subsystem: llm-engine
status: complete
tags: [mesh, observer, mesh-06, mesh-04, d-07, oq-4, d-05, unobserved, fail-open, signals]
requirements: [MESH-06, MESH-04]

requires:
  - "paaf_llm.observer — ObserverVerdict, HandoffAttempt, ObserverDecision, Observer.judge() (04-07)"
  - "paaf_llm.mesh.observer_tools() and retry_text() + MESH_RETRY_SOURCE / DEFAULT_RETRY_TEMPLATE (04-07)"
  - "paaf_llm.agent.Agent._chain(agent_name) / _emit_handoff / the per-leg loop (04-06)"
  - "paaf_trace.store.HandoffEvent's observer_verdict / observer_profile / rerouted_to columns (04-02)"
provides:
  - "paaf_llm.observer.UNOBSERVED_NOTICE constant describing unobserved mesh operation"
  - "paaf_llm.agent.Agent.has_observer / .is_observed properties"
  - "MeshSignalKind.UNOBSERVED signal emissions on construction and observer failure"
  - "Fail-open execution when observer chain degrades with distinct trace detail"
  - "paaf prompt --provenance rendering of MESH_RETRY_SOURCE and DEFAULT_RETRY_TEMPLATE"
  - "Exhaustiveness meta-test walking MeshSignalKind across test suite"
affects:
  - "04-09 (closing phase validation map and updating governance docs)"

tech-stack:
  added: []
  patterns:
    - "Unobserved state is explicitly announced, never silent (D-07)"
    - "Fail-open loudly: unreachable supervisor approves handoff but leaves visible trace"
    - "Every mesh signal kind has an automated trigger test"

key-files:
  created:
    - .planning/phases/04-agent-mesh/04-08-SUMMARY.md
  modified:
    - packages/paaf-llm/src/paaf_llm/observer.py
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/test_observer.py
    - packages/paaf-llm/tests/test_inspector.py
    - packages/paaf-llm/tests/test_mesh.py

decisions:
  - "UNOBSERVED_NOTICE explicitly states free-text constraints are unjudged while peer-graph guard still applies"
  - "Fail-open when observer chain degrades records observer_profile as 'observer', observer_verdict as NULL, and detail containing 'observer unreachable'"
  - "MeshSignalKind.UNOBSERVED fires once at Agent initialization when no observer is configured"
  - "MESH_RETRY_SOURCE is rendered in --provenance mode when offered tools exist"

metrics:
  duration: ~35 min
  tasks: 3
  commits: 1
  files_changed: 6
  lines: +280 / -25
  tests_added: 5
  suite: 383 passed (workspace) / 248 passed (clean venv, framework uninstalled)
  completed: 2026-08-08
---

# Phase 4 Plan 08: Observer Visibility and Signal Honesty Summary

The observer implementation has been completed by making its absence and its failure as visible as its presence, fulfilling D-07, OQ-4, and D-05.

## What Was Built

1. **Unobserved Mesh Visibility (D-07):**
   - Added `UNOBSERVED_NOTICE` constant to `paaf_llm.observer` stating that no supervisor profile is declared and free-text constraints are unjudged, while noting that deterministic peer-graph guards still apply.
   - Added `has_observer` and `is_observed` properties to `Agent`.
   - `Agent.__init__` emits `MeshSignalKind.UNOBSERVED` once at startup when unobserved.
   - `HandoffEvent` records `observer_verdict=NULL`, `observer_profile=NULL`, and `detail` containing `"unobserved by configuration"` when no observer is present.
   - `paaf profiles` / `paaf chat` prints `UNOBSERVED_NOTICE` when running without an observer profile.

2. **Loud Fail-Open Path (OQ-4):**
   - `Observer.judge` catches `AllProvidersFailed` when the supervisor's chain degrades, returning `ObserverDecision(ObserverVerdict.APPROVE, detail="observer unreachable: ...", served_by=None)`.
   - `Agent.turn` handles unreachable observers by failing open (approving handoff) while emitting `MeshSignalKind.UNOBSERVED` with detail `"observer unreachable"` and recording `observer_profile="observer"`, `observer_verdict=NULL`, and `detail="observer unreachable: ..."`.

3. **Correction Signals & Inspectable Refusal Text (D-05, OQ-1, PERS-05):**
   - Verified `OBSERVER_RETRY` and `OBSERVER_REROUTE` signals fire with complete metadata (`turn_id`, `from_agent`, `to_agent`, `detail`).
   - Extended `paaf prompt --provenance` output via `_render_tool_surface` to display `mesh.DEFAULT_RETRY_TEMPLATE` under the `mesh:observer-retry` source label when tools exist.
   - Added exhaustiveness meta-test `test_every_mesh_signal_kind_has_a_trigger` verifying all six `MeshSignalKind` members have automated test triggers.

## Verification

- `uv run pytest packages/paaf-llm/tests/test_observer.py packages/paaf-llm/tests/test_inspector.py -v`: 66 passed.
- `uv run pytest -q`: 383 passed across the workspace.
- `bash scripts/check_framework_uninstalled.sh`: 248 passed in clean venv with 14 test files shipped.
- `uv run lint-imports`: 3 contracts kept.
- `uv run ruff check packages && uv run ruff format --check packages`: All checks passed.

## Self-Check: PASSED
- `packages/paaf-llm/src/paaf_llm/observer.py` — `UNOBSERVED_NOTICE` and fail-open `judge()` block
- `packages/paaf-llm/src/paaf_llm/agent.py` — `has_observer` property, `UNOBSERVED` signal emission, trace details
- `packages/paaf-llm/src/paaf_llm/cli.py` — `UNOBSERVED_NOTICE` output and `MESH_RETRY_SOURCE` rendering
- `packages/paaf-llm/tests/test_observer.py` — `test_unobserved_notice`, `test_fail_open_loud`, `test_correction_signal`, `test_mesh_unavailable`, `test_every_mesh_signal_kind_has_a_trigger`
