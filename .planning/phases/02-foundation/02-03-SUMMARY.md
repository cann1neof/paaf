---
phase: 02-foundation
plan: 03
subsystem: infra
tags: [ci, packaging, wheel, uv, hatchling, isolation, foundation-02]

# Dependency graph
requires:
  - phase: 02-foundation
    plan: 01
    provides: "uv workspace; paaf-llm src/ package with zero voice/core/audio deps; hatchling wheel target"
provides:
  - "scripts/check_wheel_independence.sh — build+clean-venv+smoke+negative-control (reusable by any release gate)"
  - "wheel-independence CI job proving paaf-llm installs standalone on every push/PR (SC#2, FOUND-02)"
  - "force-include pattern: the wheel ships its own --pyargs-discoverable smoke test"
affects: [05-pypi-release]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "build-wheel → fresh off-repo venv → `pytest --pyargs <pkg>` so the INSTALLED wheel is tested, never the source tree (RESEARCH Pitfall 2)"
    - "negative control by absence: assert forbidden sibling packages raise ModuleNotFoundError in the clean venv — flips red on any hidden coupling"
    - "hatchling force-include ships an in-package smoke test so --pyargs can discover it without the workspace present"
    - "conftest collect_ignore_glob scopes an isolation-only test out of the workspace suite (clean venv never loads the conftest)"

key-files:
  created:
    - scripts/check_wheel_independence.sh
    - packages/paaf-llm/tests/test_wheel_smoke.py
    - .github/workflows/wheel-independence.yml
  modified:
    - packages/paaf-llm/pyproject.toml
    - conftest.py

key-decisions:
  - "Force-include test_wheel_smoke.py into the wheel (paaf_llm/tests/) so `pytest --pyargs paaf_llm` discovers it in a clean venv with no workspace on sys.path"
  - "Exclude the wheel-smoke test from the workspace suite via conftest collect_ignore_glob — its `paaf_voice not importable` assertion is only true in the isolated venv, and the clean venv never loads the root conftest"
  - "Kept wheel-independence as a separate workflow file (not ci.yml) per plan, so wave-2 plans do not contend on one file"

requirements-completed: [FOUND-02]

coverage:
  - id: D1
    description: "Built paaf-llm wheel installs into a fresh off-repo venv and imports; smoke tests pass via --pyargs"
    requirement: "FOUND-02"
    verification:
      - kind: integration
        ref: "bash scripts/check_wheel_independence.sh => exit 0; `pytest --pyargs paaf_llm` = 2 passed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Negative control: paaf_voice AND paaf_core raise ModuleNotFoundError in the clean venv"
    requirement: "FOUND-02"
    verification:
      - kind: integration
        ref: "script step 6 exits nonzero if either import succeeds; observed both report 'not importable'"
        status: pass
    human_judgment: false
  - id: D3
    description: "wheel-independence CI job is valid YAML, keyed 'wheel-independence', pins Python 3.12, invokes the script"
    requirement: "FOUND-02"
    verification:
      - kind: other
        ref: "yaml.safe_load asserts job present, UV_PYTHON==3.12, step runs scripts/check_wheel_independence.sh"
        status: pass
    human_judgment: false
  - id: D4
    description: "No editable-install leak: script contains no `pip install -e`; workspace suite stays green (5 passed)"
    requirement: "FOUND-02"
    verification:
      - kind: other
        ref: "grep -c 'pip install -e' => 0; `uv run pytest -q` => 5 passed (wheel-smoke excluded from workspace collection)"
        status: pass
    human_judgment: false

# Metrics
duration: 5min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 03: Wheel Independence Guarantee Summary

**A build-wheel → clean-off-repo-venv → `pytest --pyargs paaf_llm` script (plus its dedicated CI job) that proves the `paaf-llm` wheel installs standalone and carries neither `paaf-voice` nor `paaf-core` — with a negative control that flips CI red the instant a hidden coupling is added (RESEARCH Pitfall 2).**

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-07-25
- **Tasks:** 2
- **Files created:** 3 (2 modified)

## Accomplishments
- `scripts/check_wheel_independence.sh` runs `uv build --package paaf-llm`, creates a fresh venv in a `mktemp -d` dir OUTSIDE the repo, installs ONLY the built wheel, `cd`s out of the repo, imports `paaf_llm`, runs `pytest --pyargs paaf_llm`, then asserts `paaf_voice` and `paaf_core` both raise `ModuleNotFoundError`. Exits nonzero if either import unexpectedly succeeds.
- `packages/paaf-llm/tests/test_wheel_smoke.py` asserts `paaf_llm.__version__ == "0.1.0"` and that `import paaf_voice` raises `ModuleNotFoundError`. It is force-included into the wheel (`paaf_llm/tests/`) so `--pyargs paaf_llm` discovers it in the clean venv.
- `.github/workflows/wheel-independence.yml` defines the `wheel-independence` job (ubuntu-latest, Python 3.12, uv) that runs the script on every push to `main` and every PR. A job-level comment records the Pitfall-2 warning sign.
- Verified end-to-end: script exits 0 with `2 passed` in the clean venv; both forbidden imports report "not importable"; the workspace suite stays green at `5 passed`.

## Task Commits

1. **Task 1: clean-venv wheel independence script + smoke test** - `5d6ee7f` (feat)
2. **Task 2: wheel-independence CI job** - `20efda4` (ci)

## Files Created/Modified
- `scripts/check_wheel_independence.sh` - build+clean-venv+smoke+negative-control; avoids editable installs; temp dir asserted outside the repo tree
- `packages/paaf-llm/tests/test_wheel_smoke.py` - `--pyargs`-discoverable version + `paaf_voice`-absence smoke test
- `.github/workflows/wheel-independence.yml` - dedicated `wheel-independence` CI job (separate from ci.yml)
- `packages/paaf-llm/pyproject.toml` - added `[tool.hatch.build.targets.wheel.force-include]` shipping the smoke test into `paaf_llm/tests/`
- `conftest.py` - added `collect_ignore_glob = ["**/test_wheel_smoke.py"]` so the workspace suite skips the isolation-only test

## Decisions Made
- **Force-include the smoke test into the wheel.** `pytest --pyargs paaf_llm` resolves tests from the *installed* package directory; the workspace `tests/` dir is not shipped by the wheel, so an un-modified build collected 0 tests (pytest exit 5). Shipping `test_wheel_smoke.py` as `paaf_llm/tests/test_wheel_smoke.py` via hatchling `force-include` makes it discoverable in the clean venv without dragging in the rest of the workspace tests dir.
- **Scope the wheel-smoke test out of the workspace suite via conftest.** Its `paaf_voice not importable` assertion is true only inside the isolated venv; in the workspace, `paaf_voice` IS installed, so collecting it there would (correctly) fail. `collect_ignore_glob` in the root `conftest.py` excludes it from `uv run pytest`, while the clean venv — which never loads the repo conftest — still runs it via `--pyargs`.
- **Separate workflow file** (not `ci.yml`) per plan action, to avoid wave-2 file contention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Force-include the smoke test into the wheel (`packages/paaf-llm/pyproject.toml`)**
- **Found during:** Task 1 (first run of `check_wheel_independence.sh`)
- **Issue:** `pytest --pyargs paaf_llm` collected 0 tests (exit code 5, fails `set -euo pipefail`) because the wheel ships only `src/paaf_llm` — the `tests/` dir is not inside the installed package, so `--pyargs` had nothing to discover.
- **Fix:** Added `[tool.hatch.build.targets.wheel.force-include]` mapping `tests/test_wheel_smoke.py` → `paaf_llm/tests/test_wheel_smoke.py`, so the built wheel carries its own `--pyargs`-discoverable smoke test.
- **Files modified:** `packages/paaf-llm/pyproject.toml`
- **Verification:** re-run of the script → `2 passed`, exit 0.
- **Committed in:** `5d6ee7f` (Task 1 commit)

**2. [Rule 3 - Blocking] Exclude the wheel-smoke test from the workspace suite (`conftest.py`)**
- **Found during:** Task 1 (post-fix, before commit)
- **Issue:** With the test in `packages/paaf-llm/tests/`, the workspace suite (`testpaths = ["packages"]`) would also collect it. In the workspace venv `paaf_voice` IS installed, so `pytest.raises(ModuleNotFoundError)` on `import paaf_voice` would fail `uv run pytest` (and the existing `ci.yml` suite).
- **Fix:** Added `collect_ignore_glob = ["**/test_wheel_smoke.py"]` to the root `conftest.py`. The workspace suite skips the file; the clean venv (no repo conftest present) still discovers it via `--pyargs`. This preserves the negative control exactly where it is meaningful: a hidden `paaf-voice` dep added to `paaf-llm` would install `paaf_voice` into the clean venv, making the `--pyargs` test AND the script's step-6 assertion fail.
- **Files modified:** `conftest.py`
- **Verification:** `uv run pytest -q` → `5 passed`; `--collect-only | grep -c wheel_smoke` → 0; clean-venv script unaffected (still `2 passed`, exit 0).
- **Committed in:** `5d6ee7f` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both blocking, both build/test-config only)
**Impact on plan:** No new dependencies, no design change, no change to the shipped `paaf_llm` runtime code. Both fixes are the mechanical wiring required to make `pytest --pyargs paaf_llm` real (the plan's own acceptance criterion) without breaking the existing workspace suite. The negative control is strengthened, not weakened: it now lives in exactly one environment (the clean venv) where it can actually bite.

## Issues Encountered
None beyond the two config-wiring fixes documented above.

## User Setup Required
None — no external service configuration required. The job runs on GitHub-hosted `ubuntu-latest` with `astral-sh/setup-uv`.

## Next Phase Readiness
- FOUND-02 is now un-rottable: Phase 5's "a stranger pip installs paaf-llm" is guarded on every push/PR. If a future plan adds a voice/core/audio dependency to `paaf-llm`, both the `--pyargs` smoke test and the script's step-6 assertion turn the `wheel-independence` job red.
- The `check_wheel_independence.sh` script is reusable by a Phase-5 release gate as-is.

## Self-Check: PASSED

- All 3 created files and 2 modified files verified present on disk.
- Both task commits (`5d6ee7f`, `20efda4`) verified in git log.
