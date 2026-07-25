---
phase: 02-foundation
plan: 01
subsystem: infra
tags: [uv, hatchling, monorepo, pytest, pytest-socket, python312, packaging]

# Dependency graph
requires:
  - phase: 01-spike-gate
    provides: toolchain baseline (uv 0.11.31, CPython 3.12.13, pytest 9.1.1, pytest-asyncio 1.4.0)
provides:
  - uv workspace with five importable framework packages (paaf-core, paaf-trace, paaf-llm, paaf-voice, paaf-session)
  - src/ layout + hatchling build backend per package (makes the Plan 03 wheel-independence job real)
  - paaf-llm carries NO voice/core/audio dependency (FOUND-02 substrate)
  - paaf-llm/_engine adapter marker subpackage (Phase-3 langchain whitelist target)
  - root conftest.py with frozen_clock, tmp_config_path, captured_logs fixtures
  - no-network test default (--disable-socket) as the suite-wide baseline (FOUND-03/PRIV-02)
affects: [02-02 import-linter contracts, 02-03 wheel-independence, 02-04 config, 02-05 secret store, 02-09 ttfa gate]

# Tech tracking
tech-stack:
  added: [uv workspace, hatchling, pytest-socket==0.7.0, import-linter 2.13, ruff, mypy]
  patterns:
    - "src/ layout per package so tests import the installed package, not the source tree"
    - "virtual workspace root (tool.uv package=false) — root ships nothing"
    - "workspace dependency via [tool.uv.sources] name = { workspace = true }"
    - "pytest --import-mode=importlib to let identically-named test modules coexist"
    - "deterministic (non-wall-clock) FrozenClock fixture for reproducible timing assertions"

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - conftest.py
    - packages/paaf-core/pyproject.toml
    - packages/paaf-core/src/paaf_core/__init__.py
    - packages/paaf-trace/pyproject.toml
    - packages/paaf-trace/src/paaf_trace/__init__.py
    - packages/paaf-llm/pyproject.toml
    - packages/paaf-llm/src/paaf_llm/__init__.py
    - packages/paaf-llm/src/paaf_llm/_engine/__init__.py
    - packages/paaf-voice/pyproject.toml
    - packages/paaf-voice/src/paaf_voice/__init__.py
    - packages/paaf-session/pyproject.toml
    - packages/paaf-session/src/paaf_session/__init__.py
    - packages/paaf-core/tests/test_smoke.py
    - packages/paaf-trace/tests/test_smoke.py
    - packages/paaf-llm/tests/test_smoke.py
    - packages/paaf-voice/tests/test_smoke.py
    - packages/paaf-session/tests/test_smoke.py
  modified:
    - .gitignore

key-decisions:
  - "pytest-socket pinned to 0.7.0 (the version uv resolved) — closes RESEARCH Assumptions A3 unpinned item"
  - "Added --import-mode=importlib so five identically-named test_smoke.py modules coexist without __init__.py files"
  - "Virtual workspace root (tool.uv package=false) — the root pyproject groups members + dev tooling but is never built (D-07: no app packages ship)"

patterns-established:
  - "Package skeleton: src/ layout + hatchling wheel target + SPDX Apache-2.0 header on every .py"
  - "Deterministic FrozenClock fixture (counter-backed, not wall-clock) for reproducible TTFA-style assertions"
  - "No-network-by-default test suite via pytest-socket --disable-socket in root addopts"

requirements-completed: [FOUND-01, FOUND-03]

coverage:
  - id: D1
    description: "uv workspace resolves with five members; each package imports and reports __version__ == 0.1.0"
    requirement: "FOUND-01"
    verification:
      - kind: unit
        ref: "uv run pytest packages -k smoke -q (5 passed)"
        status: pass
      - kind: other
        ref: "uv sync --all-packages (exit 0, uv.lock written)"
        status: pass
    human_judgment: false
  - id: D2
    description: "paaf-llm declares no voice/core/audio dependency; _engine adapter marker exists; apps not scaffolded (D-07)"
    requirement: "FOUND-01"
    verification:
      - kind: other
        ref: "grep -v '^#' packages/paaf-llm/pyproject.toml | grep -Eci 'paaf-voice|paaf-core|sounddevice|chatterbox|whisper' => 0; app-embedded/app-desktop absent"
        status: pass
    human_judgment: false
  - id: D3
    description: "Full test suite runs green with no audio hardware and no network (--disable-socket default)"
    requirement: "FOUND-03"
    verification:
      - kind: unit
        ref: "uv run pytest -q (5 passed, --disable-socket active by default)"
        status: pass
    human_judgment: false
  - id: D4
    description: "frozen_clock, tmp_config_path, captured_logs fixtures available to every package's tests"
    requirement: "FOUND-03"
    verification:
      - kind: other
        ref: "uv run pytest --fixtures | grep -Ec 'frozen_clock|tmp_config_path|captured_logs' => 3"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 01: Foundation Workspace Scaffold Summary

**uv workspace with five hatchling-built framework packages (src/ layout), deterministic shared test fixtures, and a `--disable-socket` no-network test default — the resolvable substrate every remaining Phase-2 plan builds on.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-25
- **Tasks:** 2
- **Files created:** 19 (1 modified: .gitignore)

## Accomplishments
- `uv sync --all-packages` resolves the workspace with five members and writes `uv.lock`; uv auto-selected CPython 3.12.13 for `requires-python = ">=3.12"`.
- Five packages import and report `__version__ == "0.1.0"`: `paaf-core` (pydantic, ruamel.yaml, cryptography, filelock), `paaf-trace` (aiosqlite + workspace dep on paaf-core), and the `paaf-llm`/`paaf-voice`/`paaf-session` stubs.
- `paaf-llm` carries no voice/core/audio dependency and ships the empty `paaf_llm/_engine/` adapter-marker subpackage — the exact target Phase 3's import-linter whitelist will name (FOUND-02/FOUND-04 substrate).
- Root `conftest.py` exports `frozen_clock` (deterministic counter-backed clock), `tmp_config_path`, and `captured_logs`; the suite defaults to `--disable-socket` so any socket open fails the build (FOUND-03/PRIV-02).
- Five smoke tests pass with no audio hardware and no network; apps deliberately not scaffolded (D-07).

## Task Commits

Each task was committed atomically:

1. **Task 1: uv workspace + five package skeletons** - `5bc918d` (feat)
2. **Task 2: smoke tests, shared fixtures, no-network default, .gitignore** - `a4e1c22` (test)

## Files Created/Modified
- `pyproject.toml` - Virtual workspace root: members=packages/*, dev toolchain, pytest config (--disable-socket, importlib mode, asyncio auto)
- `uv.lock` - Single workspace lockfile (35 packages)
- `conftest.py` - Shared fixtures: FrozenClock, tmp_config_path, CapturedLogs
- `packages/paaf-core/*` - Real config package skeleton with declared runtime deps
- `packages/paaf-trace/*` - Trace package skeleton; depends on paaf-core (workspace) + aiosqlite
- `packages/paaf-llm/*` - Stub with `_engine/` adapter marker; zero voice/core/audio deps
- `packages/paaf-voice/*`, `packages/paaf-session/*` - Stubs, no internal deps
- `packages/*/tests/test_smoke.py` - Five import + version assertions
- `.gitignore` - Added dist/, build/, *.db/*.db-wal/*.db-shm, **/__pycache__/

## Decisions Made
- **pytest-socket pinned to 0.7.0** — the version `uv sync` resolved; closes the one unpinned item RESEARCH flagged (Assumptions A3) and satisfies threat T-02-SC's "confirm exact version at install".
- **Virtual workspace root** (`[tool.uv] package = false`) — the root groups members and dev tooling but is never built or published (aligns with D-07: no app packages ship from Phase 2).
- **`requires-python = ">=3.12"`** per plan action — uv selected 3.12.13 (the Phase-1 baseline), so wheels resolved without the 3.13+ risk CLAUDE.md warns about.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `--import-mode=importlib` to pytest addopts**
- **Found during:** Task 2 (running the five smoke tests)
- **Issue:** Five identically-named `test_smoke.py` modules across packages collided under pytest's default "prepend" import mode (`import file mismatch` — the tests dirs have no `__init__.py`), interrupting collection with 4 errors.
- **Fix:** Added `--import-mode=importlib` to `[tool.pytest.ini_options] addopts` in the root pyproject — the modern pytest recommendation that lets same-basename test modules coexist without `__init__.py` files or unique basenames.
- **Files modified:** pyproject.toml (already in Task 2's file set)
- **Verification:** `uv run pytest packages -k smoke -q` → 5 passed; full `uv run pytest -q` → 5 passed.
- **Committed in:** a4e1c22 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The importlib mode is a standard, non-scope-changing fix required to make the planned smoke tests collect. No new dependencies, no design change.

## Issues Encountered
None beyond the collection-mode fix documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Workspace resolves and the five packages import — Plan 02 (import-linter contracts + negative controls), Plan 03 (wheel-independence), Plans 04/05 (config + secret store in paaf-core), and Plan 09 (TTFA gate) all have their substrate.
- The `paaf_llm/_engine/` marker exists, so Plan 02's `forbidden` contract can list all five packages now and Phase 3's `ignore_imports` whitelist has a real target.
- `frozen_clock` is deterministic and ready for Plan 09's TTFA accuracy assertion.
- Note for downstream: the no-network default is *in place* here; the PRIV-02 negative-control test that proves `--disable-socket` actually blocks a socket is Plan 02's responsibility (per plan acceptance criteria).

## Self-Check: PASSED

- All 19 created files verified present on disk.
- Both task commits (`5bc918d`, `a4e1c22`) verified in git log.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
