---
phase: 03-paaf-llm-core
plan: 09
subsystem: testing
tags: [ci, github-actions, wheel, packaging, hatchling, pytest, pyargs, sc1, model-08, force-include]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "plan 03-05's ChatAdapter port, FakeAdapter, and scripts/check_wheel_independence.sh — the clean-venv pattern this gate generalizes from a smoke test to the whole suite"
  - phase: 03-paaf-llm-core
    provides: "plan 03-08's real LangChainAdapter and the paaf-llm[engine] optional extra — the thing whose laziness this gate exists to prove, and the 26 adapter tests that were skipping in CI"
  - phase: 03-paaf-llm-core
    provides: "plans 03-01/03-04/03-06/03-07's profiles, composer, agent and CLI — the suite that must run framework-uninstalled"
  - phase: 02-core-software
    provides: "paaf-core and paaf-trace as legitimate installable workspace dependencies"
provides:
  - "The entire fake-adapter suite (11 test files) force-included into the paaf-llm wheel, so `pytest --pyargs paaf_llm` runs a real suite rather than three smoke assertions"
  - "scripts/check_framework_uninstalled.sh — the SC#1 gate: builds wheels, asserts wheel completeness, installs into an off-repo clean venv WITHOUT [engine], runs the full suite, asserts langchain+langgraph unimportable"
  - "A non-vacuity guard that fails when a source-tree fake test is not shipped in the wheel — stops the gate rotting silently as the suite grows"
  - ".github/workflows/framework-uninstalled.yml — SC#1 CI gate (framework ABSENT)"
  - ".github/workflows/engine-adapter.yml — complementary CI gate (framework PRESENT) that ends the 26-test silent skip, with an explicit anti-skip assertion"
  - "check_wheel_independence.sh updated for the now-shipped async/offline suite (pytest-asyncio, pytest-socket, explicit addopts)"
affects: [04-agent-mesh, 05-tools-mcp, 06-skills-pypi-release]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit pytest flags under `--pyargs`: site-packages is not the repo rootdir, so NO root `addopts` are inherited — asyncio_mode, socket policy and plugin refusals must all be restated by hand or the job silently runs with the network open"
    - "Non-vacuity guard on a hand-maintained force-include list: compare source tree against wheel contents and fail on omission, so an unshipped test cannot masquerade as a passing gate"
    - "Anti-skip assertion before an importorskip'd suite: assert the dependency imports in its own step, so a silently no-op install cannot green a job that proved nothing"
    - "Complementary paired CI jobs (dependency ABSENT / dependency PRESENT) where neither substitutes for the other"

key-files:
  created:
    - "scripts/check_framework_uninstalled.sh"
    - ".github/workflows/framework-uninstalled.yml"
    - ".github/workflows/engine-adapter.yml"
  modified:
    - "packages/paaf-llm/pyproject.toml"
    - "scripts/check_wheel_independence.sh"

key-decisions:
  - "Ship the WHOLE fake suite in the wheel, not a smoke subset — SC#1 says 'the entire suite passes framework-uninstalled', and a claim only a three-assertion file can check is a claim nobody is checking."
  - "Deliberately do NOT ship test_engine_adapter.py: it importorskips langchain and could only ever SKIP in the framework-free venv, muddying the gate. It runs from the source tree in the engine-adapter job instead."
  - "Guard the hand-maintained force-include list mechanically rather than by discipline — a future fake test nobody lists would never run, and the job would still print green."
  - "Restate every needed pytest setting explicitly under --pyargs rather than relying on inheritance; verified that site-packages is not the rootdir."
  - "Assert the framework is importable in its own CI step before running the importorskip'd adapter tests, so a no-op install cannot pass silently."
  - "Keep both gates in separate workflow files rather than ci.yml, so wave plans do not contend on a single file."

patterns-established:
  - "Gate non-vacuity: every gate that reads a hand-maintained list carries a mechanical check that the list is complete."
  - "Paired absent/present CI jobs for any optional extra whose laziness is a product guarantee."

requirements-completed: [MODEL-08, MODEL-02, MODEL-04]

coverage:
  - id: D1
    description: "The entire paaf-llm fake-adapter suite ships in the wheel and passes with the wheel installed WITHOUT the [engine] extra — agent framework uninstalled (SC#1)."
    requirement: "MODEL-08"
    verification:
      - kind: integration
        ref: "bash scripts/check_framework_uninstalled.sh (102 passed; langchain+langgraph ModuleNotFoundError; paaf_llm/paaf_core/paaf_trace importable)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Adding the real adapter in 03-08 did NOT make langchain a load-bearing import — the _engine adapter stays lazy."
    requirement: "MODEL-08"
    verification:
      - kind: integration
        ref: "scripts/check_framework_uninstalled.sh negative control — import langchain / import langgraph both raise ModuleNotFoundError while 102 fake tests are green"
        status: pass
    human_judgment: false
  - id: D3
    description: "The wheel's shipped test set cannot silently drift from the source tree (non-vacuity guard on the force-include list)."
    verification:
      - kind: integration
        ref: "scripts/check_framework_uninstalled.sh step 2 — 'ok: all 11 fake-adapter test files ship in the wheel'"
        status: pass
    human_judgment: false
  - id: D4
    description: "The real-adapter exception translation (5xx->ServerError, 429->RateLimited, connection->ConnectionFailed, timeout->RequestTimedOut) is exercised in CI rather than silently skipped."
    requirement: "MODEL-02"
    verification:
      - kind: unit
        ref: "uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q -p no:langsmith_plugin (26 passed, 0 skipped, with [engine] installed)"
        status: pass
      - kind: integration
        ref: ".github/workflows/engine-adapter.yml anti-skip step — asserts langchain/langgraph/ollama/anthropic/openai bindings import before the suite runs"
        status: pass
    human_judgment: false
  - id: D5
    description: "The full workspace suite stays green with the [engine] extra installed, so the extra does not rot the rest of the suite."
    requirement: "MODEL-04"
    verification:
      - kind: integration
        ref: "uv run pytest --disable-socket -q -p no:langsmith_plugin (200 passed with [engine])"
        status: pass
    human_judgment: false

# Metrics
duration: 30min
completed: 2026-08-06
status: complete
---

# Phase 03 Plan 09: SC#1 Framework-Uninstalled Gate Summary

**The full 102-test fake-adapter suite now ships in the paaf-llm wheel and runs green in an off-repo clean venv where `import langchain` raises ModuleNotFoundError — with a paired CI job that ends the 26 real-adapter tests' silent skip.**

## Performance

- **Duration:** ~30 min (executor interrupted by a provider usage limit during final verification; closed out by the orchestrator)
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- **SC#1 is now a build failure if it regresses.** `scripts/check_framework_uninstalled.sh` builds paaf-llm/paaf-core/paaf-trace wheels, installs them into a fresh venv in a temp dir *outside* the repo with no `[engine]` extra, runs the whole shipped suite via `pytest --pyargs paaf_llm`, and asserts both `langchain` and `langgraph` are unimportable while every test is green. A positive control (paaf_llm, paaf_core, paaf_trace must all import) stops the negative control passing vacuously in a venv where the install silently failed.
- **The gate cannot rot silently.** The wheel's shipped test set is a hand-maintained `force-include` list. A future fake test that nobody adds to it would simply never run, and the job would still print a cheerful green. Step 2 compares the source tree's `tests/*.py` against the wheel's contents and fails on any non-excluded omission — and also fails if a deliberately-excluded file leaks in.
- **The 26 real-adapter tests were running nowhere.** `ci.yml` does `uv sync --all-packages`, which installs no extras, and `test_engine_adapter.py` opens with `pytest.importorskip("langchain")` — so the whole module skipped in CI and pytest exited 0. That is a green check mark over the seam where every provider failure is translated into the PAAF exception the fallback loop classifies. `.github/workflows/engine-adapter.yml` installs the extra and runs them.
- **The anti-skip step is load-bearing, not ceremony.** A job that installs the extra and runs an importorskip'd module is *still green* if the install silently no-ops — it just skips again, which is the exact failure being fixed. The framework is therefore asserted importable in its own step first; with langchain present, `importorskip` cannot skip and the 26 tests must execute or fail.

## Task Commits

1. **Task 1: ship the fake suite in the wheel** — `01ecca3` (chore)
2. **Task 2: SC#1 CI gate, framework uninstalled** — `7391fe8` (feat)
3. **Task 3: run real-adapter tests in CI instead of skipping** — `303a1a2` (feat)

## Files Created/Modified

- `packages/paaf-llm/pyproject.toml` — force-include 11 fake-adapter test files (conftest + suite) into the wheel; `test_engine_adapter.py` deliberately excluded with a stated reason
- `scripts/check_framework_uninstalled.sh` — the SC#1 gate, with wheel-completeness guard, off-repo clean venv, and negative + positive controls
- `.github/workflows/framework-uninstalled.yml` — CI job, framework ABSENT
- `.github/workflows/engine-adapter.yml` — CI job, framework PRESENT, with anti-skip assertion
- `scripts/check_wheel_independence.sh` — updated for the now-shipped async/offline suite: pinned pytest-asyncio + pytest-socket, explicit `-o asyncio_mode=auto`, `--disable-socket --allow-unix-socket`, `-p no:langsmith_plugin`

## Decisions Made

- **Ship the whole suite, not a smoke subset.** SC#1 is "the entire suite passes without the framework". A claim that only a three-assertion smoke file can check is a claim nobody is really checking.
- **Do not ship `test_engine_adapter.py`.** It importorskips langchain and could only ever SKIP in the framework-free venv. A skipped test inside the artifact whose whole point is "no framework here" muddies the gate rather than strengthening it.
- **Restate all pytest settings under `--pyargs`.** site-packages is not the repo rootdir, so *none* of the root `addopts` are inherited. Without `-o asyncio_mode=auto` pytest 9 **fails** (not skips) the unmarked async tests; without `--disable-socket` the job would run with the network wide open. A known consequence: a bare `pip install paaf-llm && pytest --pyargs paaf_llm` does not pass on its own — it needs pytest-asyncio and the flag. That is a property of running a shipped suite through `--pyargs`, not a defect in the wheel; this script is the authoritative run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `scripts/check_wheel_independence.sh` updated (file outside declared `files_modified`)**
- **Found during:** Task 1 (shipping the suite into the wheel)
- **Issue:** That script also runs `pytest --pyargs paaf_llm` in a clean venv. Once the wheel shipped the whole suite instead of one smoke file, its bare `pip install ... pytest` invocation could no longer run it: the suite is async (needs pytest-asyncio) and asserts offline posture (needs pytest-socket), and under `--pyargs` inherits no `addopts`. Leaving it would have broken the pre-existing Phase-2 wheel-independence job.
- **Fix:** Pinned `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `pytest-socket==0.7.0` (matching the workspace dev group so this job and `uv run pytest` cannot disagree) and passed the required flags explicitly.
- **Verification:** `bash scripts/check_wheel_independence.sh` exits 0.
- **Committed in:** `01ecca3`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to keep an existing CI job green after the wheel's contents changed. No scope creep.

## Issues Encountered

The executor was terminated by a provider usage limit while running the final phase-gate verification, after all three task commits had landed. No partial or uncommitted work was lost. The orchestrator closed the plan out by running every gate itself rather than re-dispatching:

| Gate | Result |
|---|---|
| `bash scripts/check_framework_uninstalled.sh` | **102 passed**; 11/11 test files shipped; langchain + langgraph `ModuleNotFoundError`; paaf_llm/paaf_core/paaf_trace importable; exit 0 |
| `uv sync --all-packages --extra engine` + anti-skip assertion | agent framework present: langchain 1.3.14 |
| `uv run pytest packages/paaf-llm/tests/test_engine_adapter.py` | **26 passed, 0 skipped** — the tests genuinely execute |
| `uv run pytest --disable-socket -q` (with `[engine]`) | **200 passed** |

## User Setup Required

None — no external service configuration required. Both new CI jobs run on `ubuntu-latest` with `astral-sh/setup-uv@v6` and need no secrets, which is itself consistent with the project's no-accounts commitment.

## Next Phase Readiness

- **SC#1 is closed and durable.** The port is proven to be a port and not a mirror: the real adapter exists and the fake suite still runs with the framework genuinely absent.
- **Phase 4 (Agent Mesh) is unblocked.** The peer graph and capability manifest are validated inert data (03-01), the handoff seam exists on `TurnResult` (03-05), and `NO_HANDOFF_NOTE` + `test_manifest_performs_no_handoff` (03-07) are the two assertions that make turning the mesh on a deliberate act rather than an accident.
- **Carried forward, not blocking:** `paaf_core.Endpoint` carries no path, so an OpenAI-compatible profile cannot express `http://host:8080/v1` (vLLM, llama.cpp server, LM Studio). Plan 03-08 declined to silently append a suffix — that is the hidden behavior this project refuses — and the fix is an `endpoint_path` field on `ModelProfile`. Ollama and Anthropic are unaffected.

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-06*
