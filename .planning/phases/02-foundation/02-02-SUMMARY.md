---
phase: 02-foundation
plan: 02
subsystem: infra
tags: [import-linter, negative-controls, ci, github-actions, boundaries, langchain-confinement, offline]

# Dependency graph
requires:
  - phase: 02-foundation
    plan: 01
    provides: uv workspace with five importable packages + paaf_llm/_engine adapter marker + --disable-socket default
provides:
  - three import-linter contracts (independence, langchain-confined, no-network-client) enforced on the real workspace
  - negative-control fixtures + test proving each contract goes RED on a deliberate violation (non-vacuous guard)
  - suite CI job (offline, no audio) that runs the contracts + full pytest + root-level governance/negcontrol guards
  - Phase-3 ignore_imports whitelist target documented in .importlinter (paaf_llm._engine.* -> langchain*)
affects: [02-03 wheel-independence, 02-08 governance rot-guard (test_governance.py named in CI), Phase-3 langchain adapter whitelist]

# Tech tracking
tech-stack:
  added: [import-linter 2.13 (wired), pyyaml==6.0.3 (dev, CI-yaml validation)]
  patterns:
    - "INI .importlinter with include_external_packages=True so forbidden externals (langchain*, httpx, socket) resolve without being installed"
    - "negative-control fixtures live OUTSIDE packages/ so the real contract stays green while the guard is proven to bite"
    - "import-linter is static AST analysis — uninstalled forbidden modules are still recorded, and subprocess invocation is unaffected by pytest-socket"
    - "contract section-id decoupled from name= so each contract name is grep-unique in the config"
    - "CI names root-level tests explicitly because root testpaths=['packages'] excludes them"

key-files:
  created:
    - .importlinter
    - tests/negcontrol/.importlinter-negcontrol
    - tests/negcontrol/paaf_voice_violation/__init__.py
    - tests/negcontrol/paaf_llm_langchain_violation/__init__.py
    - tests/negcontrol/paaf_trace_net_violation/__init__.py
    - tests/negcontrol/test_import_boundary.py
    - .github/workflows/ci.yml
  modified:
    - .gitignore
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Replaced the plan's illustrative urllib.request with socket in the no-network contract: import-linter rejects submodules of external packages as forbidden modules, and socket is the raw egress primitive underneath every HTTP client"
  - "Added include_external_packages=True (required by import-linter whenever a forbidden contract names external modules)"
  - "Added pyyaml to the dev group so the plan's own YAML-validation verify command runs (paaf-core uses ruamel.yaml for config; pyyaml is CI-only)"
  - "Used --contract <id> per negative-control test so each contract's red-on-violation is asserted in isolation, and the printed contract name is matched in output"

requirements-completed: [FOUND-04, FOUND-03]

coverage:
  - id: D1
    description: "Three named import-linter contracts pass (green) against the real workspace"
    requirement: "FOUND-04"
    verification:
      - kind: other
        ref: "uv run lint-imports => exit 0; 'Contracts: 3 kept, 0 broken'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each contract is proven to fail RED on a deliberate violation while the real workspace stays green"
    requirement: "FOUND-04"
    verification:
      - kind: unit
        ref: "uv run pytest tests/negcontrol/test_import_boundary.py => 4 passed (real green + 3 contracts red on violation)"
        status: pass
    human_judgment: false
  - id: D3
    description: "langchain confinement lists all four langchain* modules; voice<->llm independence is bidirectional"
    requirement: "FOUND-04"
    verification:
      - kind: other
        ref: "grep .importlinter: langchain/langgraph/langchain_core/langchain_mcp_adapters forbidden; independence modules=[paaf_voice,paaf_llm]"
        status: pass
    human_judgment: false
  - id: D4
    description: "suite CI job runs contracts + full suite offline (no network, no audio) and names root-level governance + negcontrol guards"
    requirement: "FOUND-03"
    verification:
      - kind: other
        ref: "ci.yml parses; job 'suite' present; lint-imports + pytest --disable-socket; names test_governance.py + tests/negcontrol; 0 audio system deps; Python 3.12"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 02: Import-Boundary Contracts + Negative Controls + Suite CI Summary

**Three import-linter contracts (voice↔llm independence, langchain-confined-to-adapter, no-network-client) declared on the real workspace and green, each paired with an out-of-tree negative control that proves it turns RED on a deliberate violation, wired into an offline `suite` CI job that also runs the root-level governance and negcontrol guards the packages-only testpaths would otherwise skip.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-25
- **Tasks:** 3
- **Files created:** 7 (3 modified: .gitignore, pyproject.toml, uv.lock)

## Accomplishments
- Root `.importlinter` declares three contracts with exact names — `voice-and-llm-are-independent` (independence, bidirectional/indirect), `langchain-confined-to-adapter` (forbidden: langchain, langgraph, langchain_core, langchain_mcp_adapters), `no-network-client-in-framework` (forbidden: httpx, requests, aiohttp, socket) — all KEPT (3 kept, 0 broken) against the real workspace because no package imports a forbidden module yet.
- The Phase-3 `ignore_imports` whitelist (`paaf_llm._engine.* -> langchain*`) is documented in a `.importlinter` comment so the future exception target is explicit from the first commit.
- Three deliberately-violating fixture packages live under `tests/negcontrol/` (OUTSIDE `packages/`), each importing exactly the forbidden thing (`paaf_llm`, `langchain`, `httpx`); a separate `.importlinter-negcontrol` maps the three contract types onto them.
- `tests/negcontrol/test_import_boundary.py` (4 tests) proves the pair: the real `.importlinter` exits 0 (green-on-clean), and each contract exits nonzero AND names itself in output (red-on-violation). The guard is non-vacuous — the exact discipline Phase 1 caught missing twice.
- `.github/workflows/ci.yml` job `suite` (ubuntu-latest, Python 3.12) runs `uv sync`, `lint-imports`, `pytest --disable-socket` (packages/), then `pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` — naming the root-level files explicitly because root `testpaths=["packages"]` would otherwise skip the FOUND-07 SPDX rot-guard (Plan 08) and the FOUND-04 negative controls. No system audio library is installed, so "no audio hardware" holds by construction.

## Task Commits

Each task was committed atomically:

1. **Task 1: Declare the three import-linter contracts on the real workspace** - `65e89ff` (feat)
2. **Task 2: Negative controls — prove each contract goes RED on a deliberate violation** - `482d905` (test)
3. **Task 3: Suite CI job — contracts + full offline test suite** - `7d5c2a9` (feat)

## Files Created/Modified
- `.importlinter` - Root config: `include_external_packages=True`, five `root_packages`, three named contracts; Phase-3 whitelist documented in comments
- `tests/negcontrol/.importlinter-negcontrol` - Separate negative-control config mapping the three contract types onto the violation fixtures
- `tests/negcontrol/paaf_voice_violation/__init__.py` - `import paaf_llm` (independence violation)
- `tests/negcontrol/paaf_llm_langchain_violation/__init__.py` - `import langchain` (langchain-confinement violation)
- `tests/negcontrol/paaf_trace_net_violation/__init__.py` - `import httpx` (no-network-client violation)
- `tests/negcontrol/test_import_boundary.py` - 4 tests: real config green + each contract red-on-violation, via subprocess with fixtures on PYTHONPATH
- `.github/workflows/ci.yml` - `suite` job: offline contracts + full suite + explicit root-level governance/negcontrol guards
- `.gitignore` - Added `.import_linter_cache/` (generated grimp graph cache)
- `pyproject.toml` / `uv.lock` - Added `pyyaml` to the dev group (CI-yaml validation)

## Decisions Made
- **`socket` replaces the plan's illustrative `urllib.request`** in the no-network contract — import-linter rejects submodules of external packages as forbidden modules (`Invalid forbidden module urllib.request: subpackages of external packages are not valid`). `socket` is the raw egress primitive under every HTTP client and is a valid top-level forbidden module; the contract still lists `httpx`, `requests`, `aiohttp` alongside it.
- **`include_external_packages=True`** is mandatory: import-linter refuses to run a forbidden contract naming external modules without it.
- **Contract section-ids decoupled from `name=`** (`[importlinter:contract:independence]` / `name = voice-and-llm-are-independent`) so each contract name is grep-unique (acceptance required `grep -c == 1`).
- **pyyaml added (dev only)** to satisfy the plan's `import yaml` verify command; runtime config in `paaf-core` still uses `ruamel.yaml`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `urllib.request` is not a valid import-linter forbidden module**
- **Found during:** Task 1 (`uv run lint-imports` errored: "subpackages of external packages are not valid")
- **Issue:** The plan listed `urllib.request` (a submodule) as a forbidden module in the no-network contract; import-linter forbids external submodules.
- **Fix:** Replaced with `socket` (top-level, the raw egress primitive). The plan phrased the forbidden list as illustrative ("e.g. `httpx`, `requests`, `urllib.request`, `aiohttp`"), so intent is preserved.
- **Files modified:** `.importlinter`
- **Commit:** `65e89ff`

**2. [Rule 3 - Blocking] `include_external_packages=True` required**
- **Found during:** Task 1 (`uv run lint-imports` errored requiring it for external forbidden modules)
- **Fix:** Added `include_external_packages = True` to `[importlinter]`. Same fix applied to `.importlinter-negcontrol` so the langchain/httpx externals resolve.
- **Files modified:** `.importlinter`, `tests/negcontrol/.importlinter-negcontrol`
- **Commit:** `65e89ff`, `482d905`

**3. [Rule 3 - Blocking] pyyaml missing for the plan's verify command**
- **Found during:** Task 3 (`uv run python -c "import yaml..."` — ModuleNotFoundError)
- **Issue:** The plan's Task 3 verify command imports `yaml`, but pyyaml was not in the workspace (paaf-core uses ruamel.yaml).
- **Fix:** `uv add --dev pyyaml` (pyyaml==6.0.3). CI-yaml validation only; not a runtime dependency.
- **Files modified:** `pyproject.toml`, `uv.lock`
- **Commit:** `7d5c2a9`

**4. [Rule 3 - Blocking] `.import_linter_cache/` left untracked**
- **Found during:** Task 2 (running lint-imports generated a grimp graph cache at repo root)
- **Fix:** Added `.import_linter_cache/` to `.gitignore` (generated artifact).
- **Files modified:** `.gitignore`
- **Commit:** `482d905`

---

**Total deviations:** 4 auto-fixed (all Rule 3 blocking). No architectural changes; all are standard tool-wiring corrections that preserve the plan's intent.

## Issues Encountered
None beyond the four blocking fixes above. The key risk (grimp detecting imports of uninstalled `langchain`/`httpx`) resolved cleanly: import-linter is static AST analysis, so it records the forbidden edges without the packages installed, and subprocess invocation is unaffected by `--disable-socket`.

## User Setup Required
None — no external service configuration required. The `suite` CI job runs on GitHub Actions on the next push/PR.

## Next Phase Readiness
- SC#1 substrate is real: a forbidden import (voice↔llm coupling or langchain escaping `_engine`) now fails `lint-imports`, and the negative controls prove the guards bite.
- `.github/workflows/ci.yml` already NAMES `tests/test_governance.py` — Plan 08 must create that file (the FOUND-07 SPDX/DECISIONS rot-guard) for the CI step to pass; until then the step will error on the missing file if CI runs mid-phase.
- Phase 3's langchain adapter has a documented whitelist target (`paaf_llm._engine.* -> langchain*`); confirm the exact `ignore_imports` glob against import-linter 2.13 when wiring it (RESEARCH A5).
- Plan 03 (wheel-independence) builds on the same workspace; the import contracts do not interfere with per-package wheel builds.

## Self-Check: PASSED

- All 7 created files verified present on disk.
- All three task commits (`65e89ff`, `482d905`, `7d5c2a9`) verified in git log.
- `uv run lint-imports` exits 0; `tests/negcontrol/test_import_boundary.py` 4 passed; `ci.yml` parses with a `suite` job.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
