---
phase: 02-foundation
plan: 09
subsystem: trace
tags: [ttfa, fake-tts, ci-gate, deterministic-clock, pytest-socket, no-egress, regression-guard]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "runs.time_to_first_audio REAL column + compute_time_to_first_audio / record_time_to_first_audio, and the WAL single-writer TraceStore (Plan 07)"
  - phase: 02-foundation
    provides: "deterministic FrozenClock fixture (.now()/.advance()) at workspace root conftest (Plan 01)"
  - phase: 02-foundation
    provides: "--disable-socket + --allow-unix-socket test default; no-egress posture (Plans 02/07)"
provides:
  - "paaf_trace._testing.FakeTTS: a fake TTS driven by an injected controllable clock that emits first audio after a fixed injected delay and exposes started_at/first_audio_at/ended_at"
  - "test_ttfa_regression.py: accuracy (abs(recorded-D)<tol, load-bearing) + overhead-under-ceiling + budget assertions + a two-case negative control (constant / whole-round-trip recorders must FAIL accuracy)"
  - ".github/workflows/ttfa-gate.yml job 'ttfa-gate': cold, Python 3.12, --disable-socket, no audio system deps"
affects: [phase-7 real Chatterbox TTS latency validation, desktop logs page TTFA display]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recorder seam (Callable[(started_at, first_audio_at, ended_at) -> seconds]) lets one FakeTTS drive feed both a correct recorder and a broken one — the negative control is the same drive with a swapped recorder"
    - "FakeTTS tail chunks advance the clock past first-audio so the whole round trip is strictly longer than first-audio latency — this is what makes a whole-round-trip recorder distinguishable from a correct first-audio one"
    - "Budget kept ABOVE the fake's whole-round-trip value on purpose, so budget alone cannot catch the wrong-measurement pitfall — only the accuracy assertion can (Pitfall 3 made concrete)"

key-files:
  created:
    - packages/paaf-trace/src/paaf_trace/_testing/__init__.py
    - packages/paaf-trace/src/paaf_trace/_testing/fake_tts.py
    - packages/paaf-trace/tests/test_ttfa_regression.py
    - .github/workflows/ttfa-gate.yml
  modified: []

key-decisions:
  - "The TTFA accuracy assertion is proven non-vacuous by a parametrised negative control: a constant-zero recorder AND a whole-round-trip recorder each MUST fail abs(recorded-D)<tol — the round-trip case additionally asserts it slips under BUDGET, making Pitfall 3 concrete (budget passes, accuracy catches it)"
  - "BUDGET is documented (module docstring + workflow comment) as a measurement/overhead-regression guardrail, EXPLICITLY NOT a shipped-latency claim (D-09; real TTFA was 6.27s on mps with a ~10x tail)"
  - "FakeTTS lives under paaf_trace._testing (underscore-private) so the test double never leaks into the public API surface"
  - "The recorded value goes through the real Plan-07 TraceStore + record_time_to_first_audio and is read back from SQLite — the number the gate defends is the one that actually lands on the runs row, not an in-memory shortcut"

patterns-established:
  - "Deterministic-clock accuracy gate: inject a controllable clock, advance it by a known delta, assert the recorded metric reproduces the delta within a tight tolerance — no wall-clock, no sleep, no flake"
  - "Non-vacuous metric guard: every accuracy assertion pairs with a broken-recorder negative control that must fail it"

requirements-completed: [TRACE-04]

coverage:
  - id: D1
    description: "Recorded time_to_first_audio matches the injected delay within a tight tolerance (accuracy, D-08a/D-09, load-bearing)"
    requirement: "TRACE-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_ttfa_regression.py::test_ttfa_accuracy"
        status: pass
    human_judgment: false
  - id: D2
    description: "Framework/measurement overhead beyond D stays under a small ceiling"
    requirement: "TRACE-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_ttfa_regression.py::test_ttfa_overhead_under_ceiling"
        status: pass
    human_judgment: false
  - id: D3
    description: "Recorded time_to_first_audio is under the fixed budget ceiling (D-08b)"
    requirement: "TRACE-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_ttfa_regression.py::test_ttfa_under_budget"
        status: pass
    human_judgment: false
  - id: D4
    description: "The accuracy assertion FAILS for a broken recorder (constant, or whole-round-trip) — the negative control proving the guard is non-vacuous (Pitfall 3)"
    requirement: "TRACE-04"
    verification:
      - kind: unit
        ref: "packages/paaf-trace/tests/test_ttfa_regression.py::test_accuracy_fails_for_broken_recorder[constant-zero]"
        status: pass
      - kind: unit
        ref: "packages/paaf-trace/tests/test_ttfa_regression.py::test_accuracy_fails_for_broken_recorder[whole-round-trip]"
        status: pass
    human_judgment: false
  - id: D5
    description: "A dedicated cold CI job runs the gate offline (--disable-socket) on Python 3.12 with no audio system dependency"
    requirement: "TRACE-04"
    verification:
      - kind: other
        ref: ".github/workflows/ttfa-gate.yml job 'ttfa-gate' (yaml-valid; runs test_ttfa_regression.py --disable-socket; no portaudio/libasound/sounddevice; pins 3.12)"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 09: Fake-TTS TTFA CI Gate Summary

**Time-to-first-audio is now a number CI defends before any real audio engine exists. A `FakeTTS` test double emits its first audio chunk after a fixed injected delay on the deterministic `frozen_clock`; `test_ttfa_regression.py` records `time_to_first_audio` through the real Plan-07 trace store and asserts accuracy (`abs(recorded - D) < 1e-9`, the load-bearing half), overhead-under-ceiling, and a budget guardrail — with a parametrised negative control proving the accuracy guard is non-vacuous (Pitfall 3). A dedicated cold `ttfa-gate` workflow runs it offline on Python 3.12 with no audio deps.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-25
- **Tasks:** 2 (Task 1 executed TDD: RED test commit → GREEN impl commit)
- **Files created:** 4 (0 modified)

## Accomplishments
- `paaf_trace._testing.FakeTTS` (underscore-private, never public API): takes an injected controllable clock (`frozen_clock`: `.now()`/`.advance()`) and an injected first-audio `delay`. On `synthesize()` it records `started_at`, advances the clock by `delay` and yields the FIRST chunk (recording `first_audio_at`), then advances further while yielding tail chunks (recording `ended_at`). The tail makes the whole round trip strictly longer than first-audio latency — the property that lets the negative control distinguish a correct first-audio measurement from a broken whole-round-trip one.
- `test_ttfa_regression.py` drives `FakeTTS` with `D = 0.5 s`, records `time_to_first_audio` via the **real** `TraceStore` + `record_time_to_first_audio`, reads it back from SQLite, and asserts:
  - **accuracy** (load-bearing, D-08a/D-09): `abs(recorded - D) < 1e-9`;
  - **overhead**: `0 <= recorded - D < 1e-6` (exactly 0 on a frozen clock — deterministic, no wall-clock noise);
  - **budget** (D-08b): `recorded < 2.0 s`.
- **Negative control (Pitfall 3):** a parametrised `test_accuracy_fails_for_broken_recorder` swaps in a constant-zero recorder and a whole-round-trip recorder; each MUST fail the accuracy assertion (wrapped in `pytest.raises(AssertionError)`). The round-trip case additionally asserts its value (`0.8 s`) is **under BUDGET** — making Pitfall 3 concrete: a budget-only gate would pass this mis-measurement silently; the accuracy assertion catches it.
- `.github/workflows/ttfa-gate.yml` job `ttfa-gate`: Linux runner, Python 3.12 pinned, `uv sync --all-packages`, then `uv run pytest packages/paaf-trace/tests/test_ttfa_regression.py --disable-socket`. Cold (fresh checkout, no real-engine warm cache — there is none), offline, no audio system package. Job/file comments state it defends measurement accuracy+overhead with a fake TTS, and that a measurement/overhead regression — not shipped latency (D-09) — is what turns it red. Kept as a separate workflow file so wave-2/3 plans do not contend on one CI file.
- No `time.sleep`, no wall-clock (`grep -c 'time.sleep'` returns 0); the deterministic `frozen_clock` is the only time source (Anti-Pattern avoided).

## Task Commits

1. **Task 1 (RED): failing TTFA regression test** - `0f05182` (test)
2. **Task 1 (GREEN): FakeTTS test double + accuracy/overhead/budget/negative-control green** - `fa11b24` (feat)
3. **Task 2: ttfa-gate CI job (cold, no HW, no net)** - `50ae963` (ci)

## Files Created/Modified
- `packages/paaf-trace/src/paaf_trace/_testing/__init__.py` - Private test-double package; re-exports `FakeTTS`.
- `packages/paaf-trace/src/paaf_trace/_testing/fake_tts.py` - `FakeTTS`: injected-clock, injected-delay fake emitting first audio after `delay`, exposing `started_at`/`first_audio_at`/`ended_at`.
- `packages/paaf-trace/tests/test_ttfa_regression.py` - Accuracy + overhead + budget + two-case negative control, recording through the real Plan-07 store.
- `.github/workflows/ttfa-gate.yml` - Cold, offline `ttfa-gate` job (Python 3.12, `--disable-socket`, no audio deps).

## Decisions Made
- **The accuracy guard is proven non-vacuous** by a two-case negative control (constant + whole-round-trip). The round-trip case is deliberately tuned to sit under BUDGET (`0.8 < 2.0`) so it demonstrates exactly what a budget-only gate would miss.
- **BUDGET is a regression guardrail, not a latency promise** — stated in both the test module docstring and the workflow comments, anchored to D-09 / the Phase-1 6.27 s-on-mps evidence.
- **Record through the real store, read back from SQLite** — the defended number is the one that lands on the `runs` row, not an in-memory shortcut.
- **`FakeTTS` under `_testing`** keeps the double out of the public API surface.

## Deviations from Plan
None - plan executed exactly as written. (One in-flight correction: the test module docstring initially contained the literal token `time.sleep` in prose, which tripped the `grep -c 'time.sleep' == 0` acceptance check via `.` matching a space; reworded to "Nothing sleeps" before the GREEN commit. This is a wording fix, not a behavior/scope change.)

## Known Stubs
None. `FakeTTS` is an intentional, documented test double for a metric gate — not a stub standing in for unwired production data. The real audio engine (Chatterbox) arrives in Phase 7; this plan's explicit purpose (per the roadmap and D-09) is to make the TTFA *measurement* trustworthy before that engine exists, so no production data source is expected here.

## Issues Encountered
None beyond the docstring/grep wording fix noted above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7's real Chatterbox TTS inherits a metric that is already accuracy-defended: when the real engine records `time_to_first_audio`, the accounting path (`compute_time_to_first_audio` → `record_time_to_first_audio` → `runs.time_to_first_audio`) is the same one this gate proves correct, so latency validation is an addition, not a retrofit.
- The `ttfa-gate` workflow runs on every push/PR to `main`, cold and offline, alongside `ci` and `wheel-independence`.

## Self-Check: PASSED

- All 4 created files verified present on disk.
- All three commits (`0f05182`, `fa11b24`, `50ae963`) verified in `git log`.
- `test_ttfa_regression.py`: 5 passed; full workspace suite: 72 passed; governance rot-guard: 34 passed; import-linter: 3/3 KEPT; mypy + ruff clean on new sources.
- Acceptance greps: `grep -c 'time.sleep'` = 0; ttfa-gate YAML valid with `ttfa-gate` job; no `portaudio|libasound|sounddevice`; Python 3.12 pinned.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
