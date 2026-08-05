---
phase: 03-paaf-llm-core
plan: 05
subsystem: api
tags: [protocol, port, adapter, test-double, dataclass, asyncio, wheel-independence, import-linter]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "plan 03-01's ModelProfile/LlmConfig (the config contract ChatAdapter.stream is typed against) and paaf-llm's real dependency set"
  - phase: 02-core-software
    provides: "paaf_core.net.endpoint.Endpoint (reached through ModelProfile), paaf_trace.store.TraceStore (the async conftest fixture), the clean-venv wheel job and its negative-control discipline"
provides:
  - "ChatAdapter — a two-method streaming Protocol whose entire surface is PAAF types (MODEL-08)"
  - "Message / Usage / TurnResult — frozen PAAF value types; TurnResult carries served_by + fallback_trail provenance"
  - "TurnResult.handoff — the inert Phase-4 seam, always None this phase, so MESH-02 changes no port signature"
  - "FallbackReason + the AdapterError hierarchy (ConnectionFailed/RequestTimedOut/ServerError/RateLimited) — one PAAF exception per degraded trigger"
  - "AllProvidersFailed — terminal, deliberately NOT an AdapterError"
  - "FakeAdapter — the shipped, programmable, framework-free adapter the whole phase is tested against (SC#1)"
  - "packages/paaf-llm/tests/conftest.py — fake_adapter, make_profile, make_llm_config, and an async trace_store fixture"
  - "test_no_leak.py — a signature walker proving no public annotation names a framework type, plus proof that importing paaf_llm loads no langchain*/langgraph*"
  - "A wheel-independence job retargeted at langchain absence, with a positive control that the declared deps are present"
affects: [03-06-agent-fallback, 03-07-cli, 03-08-engine-adapter, 03-09-trace-wiring, 04-agent-mesh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One-method port + shipped fake: the correctness surface is the fake, and the fake ships in the wheel so the suite runs framework-uninstalled"
    - "PEP 695 `type X = Any` under TYPE_CHECKING as a forward seam for a type that does not exist yet"
    - "Annotation-walking conformance test: resolve every public annotation and reject any root module outside stdlib/paaf_llm/paaf_core"
    - "Detector negative controls: each guard is paired with a test that plants a violation and proves the detector reports it"
    - "Positive control beside a negative control in the clean-venv job — the absence assertions cannot pass on an empty venv"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/ports.py
    - packages/paaf-llm/src/paaf_llm/fake/__init__.py
    - packages/paaf-llm/tests/conftest.py
    - packages/paaf-llm/tests/test_ports.py
    - packages/paaf-llm/tests/test_fake_adapter.py
    - packages/paaf-llm/tests/test_no_leak.py
  modified:
    - packages/paaf-llm/src/paaf_llm/__init__.py
    - packages/paaf-llm/tests/test_wheel_smoke.py
    - scripts/check_wheel_independence.sh
    - .github/workflows/wheel-independence.yml
    - conftest.py

key-decisions:
  - "FakeAdapter keys programs by profile.model, not profile.name — ModelProfile has no name field (the name is the LlmConfig.profiles dict key and does not cross the port); a `.name` attribute is honored first if a future profile type has one"
  - "An un-programmed profile raises LookupError, never an AdapterError — a fallback loop catches AdapterError, so a forgotten program() call would otherwise be swallowed as a plausible-looking hop"
  - "FakeAdapter's default usage is Usage(7, 3), not Usage() — a both-None default would let an aggregated-usage test pass against an engine that never read usage at all"
  - "There is deliberately no adapter error for SLOW_FIRST_TOKEN: the budget is the user's (first_token_budget_s), so only the engine's deadline may classify it"
  - "AllProvidersFailed does NOT subclass AdapterError — 'try the next profile' and 'there is no next profile' must not be catchable by the same except clause"
  - "The no-leak walker inspects only members DEFINED in paaf_llm; inherited pydantic BaseModel machinery is the base class's contract, not PAAF's public surface"
  - "paaf_core is an ALLOWED root in the no-leak walker — ModelProfile.endpoint() returning a paaf_core Endpoint is deliberate type reuse, the opposite of leaking a swappable dependency's types"
  - "The wheel job gained a positive control (paaf_llm/paaf_core/paaf_trace ARE importable) so the langchain/paaf_voice absence assertions cannot pass vacuously on a failed install"

patterns-established:
  - "Source-text assertions beside import-graph assertions: ports.py and fake/ are checked for framework imports both by reading their source and by import-linter"
  - "Every detector in test_no_leak.py has a `..._is_not_vacuous` twin that plants a fake violation"
  - "Shared fixtures live in packages/paaf-llm/tests/conftest.py — the repo's first per-package conftest"

requirements-completed: [MODEL-08]

coverage:
  - id: D1
    description: "A single-method streaming port (ChatAdapter) whose only surface is PAAF types — no agent-framework type appears in any public signature"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_public_signatures_are_paaf_typed"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_signature_walker_is_not_vacuous"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_walker_actually_inspected_the_surface"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_chat_adapter_is_a_two_method_protocol"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_ports_source_imports_no_agent_framework"
        status: pass
      - kind: integration
        ref: "uv run lint-imports (3 contracts kept, 0 broken)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A shipped FakeAdapter implements the port with zero framework imports and can be programmed to stream scripted tokens or raise any of the four degraded failures"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_streams_the_scripted_tokens_in_order"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_programmed_failure_raises_on_the_first_token"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_slow_first_token_is_the_engines_deadline_to_fire"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_fake_adapter_satisfies_the_chat_adapter_protocol"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_fake_source_imports_no_agent_framework"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fake_adapter.py#test_last_usage_reports_concrete_counts_after_aggregation"
        status: pass
    human_judgment: false
  - id: D3
    description: "The public paaf_llm surface re-exports only PAAF types + FakeAdapter and never pulls _engine, so the fake suite runs with the framework uninstalled"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_import_paaf_llm_needs_no_framework"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_import_paaf_llm_needs_no_framework_in_a_pristine_interpreter"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_no_leak.py#test_framework_module_detector_is_not_vacuous"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_public_surface_exposes_no_engine_symbol"
        status: pass
    human_judgment: false
  - id: D4
    description: "The wheel-independence job reflects paaf-llm's real framework deps: it asserts paaf_voice and langchain are absent while paaf_core/paaf_trace are legitimately present"
    verification:
      - kind: integration
        ref: "bash scripts/check_wheel_independence.sh (exit 0; 3 smoke tests pass in the clean venv)"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_wheel_smoke.py#test_langchain_not_importable_from_llm_wheel"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_wheel_smoke.py#test_paaf_voice_not_importable_from_llm_wheel"
        status: pass
    human_judgment: false
  - id: D5
    description: "TurnResult carries the inert Phase-4 handoff seam so the port's shape does not change when MESH-02 adds handoff"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_turn_result_carries_the_inert_handoff_seam"
        status: pass
    human_judgment: false

# Metrics
duration: 19min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 05: Port, Fake, and the No-Leak Proof Summary

**A two-method `ChatAdapter` Protocol typed entirely in PAAF values, a shipped programmable `FakeAdapter` with zero framework imports, and an annotation-walking no-leak test — plus a wheel-independence job retargeted from `paaf_core` to `langchain`.**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-08-05T16:05:30Z
- **Completed:** 2026-08-05T16:24:30Z
- **Tasks:** 3 (2 TDD → 5 commits)
- **Files modified:** 11 (6 created, 5 modified)

## Accomplishments

- **The port exists and is provably a port.** `ChatAdapter` has two methods; every annotation across the whole public surface — 45 of them, walked by `test_no_leak.py` — resolves to stdlib, `paaf_llm`, or `paaf_core`. MODEL-08 is now a red build rather than a review comment.
- **The exception hierarchy makes the fallback loop's job structural.** Each of the four degraded triggers has exactly one PAAF exception carrying exactly one `FallbackReason`, so plan 03-06 classifies a hop by reading `.reason` and adding a provider means adding a translation, never a branch.
- **`SLOW_FIRST_TOKEN` has deliberately no adapter error.** The fake honors `first_token_delay_s` and lets the engine's deadline fire — pinned by `test_slow_first_token_is_the_engines_deadline_to_fire`, which is the negative control that an engine with no deadline at all would fail.
- **The shipped fake is the phase's correctness substrate.** `program(profile, tokens=..., fail=..., first_token_delay_s=..., usage=...)` scripts a profile deterministically; `import paaf_llm` loads no `langchain*`/`langgraph*` module, verified in-process *and* in a pristine subprocess.
- **The wheel job now guards the right thing.** Its Phase-2 negative control asserted `paaf_core` absent — which plan 03-01 turned into a guard against a deliberate design decision. It now builds and installs `paaf-core`/`paaf-trace` alongside `paaf-llm` (they are workspace packages, unresolvable from PyPI), still without the `[engine]` extra, and asserts `paaf_voice` + `langchain` absent. No red-CI window was ever opened.
- **Every guard is paired with a detector control.** `test_signature_walker_is_not_vacuous` plants a class whose `__module__` is `langchain_core.messages` and proves the walker reports it; `test_framework_module_detector_is_not_vacuous` does the same for the `sys.modules` probe; the clean-venv script gained a positive control so its absence assertions cannot pass on a failed install.

## Task Commits

Both TDD tasks show the full RED → GREEN gate in git log:

1. **Task 1 (RED): failing port contract tests** — `a04aa47` (test)
2. **Task 1 (GREEN): ports.py + public re-exports** — `4d1357b` (feat)
3. **Task 2 (RED): failing FakeAdapter/no-leak tests + fixtures** — `2f078d4` (test)
4. **Task 2 (GREEN): fake/ + FakeAdapter on the public surface** — `9d8d43f` (feat)
5. **Task 3: retarget the wheel-independence control** — `2b4463a` (fix)

## Files Created/Modified

- `packages/paaf-llm/src/paaf_llm/ports.py` (created) — `Role`, `Message`, `Usage`, `FallbackReason`, `AdapterError` + the four subclasses, `AllProvidersFailed`, `TurnResult` (with the `handoff` seam), and the `ChatAdapter` Protocol. Stdlib-only at runtime.
- `packages/paaf-llm/src/paaf_llm/fake/__init__.py` (created) — `FakeAdapter.program()/stream()/last_usage()`, `PROFILE_KEY_FIELD`, `DEFAULT_USAGE`, and the `calls` record of what actually crossed the port.
- `packages/paaf-llm/src/paaf_llm/__init__.py` (modified) — re-exports the 12 PAAF port types plus `ModelProfile`/`LlmConfig`/`FakeAdapter`; imports nothing from the adapter package.
- `packages/paaf-llm/tests/conftest.py` (created) — `fake_adapter`, `make_profile`, `make_llm_config`, async `trace_store`. The repo's first per-package conftest.
- `packages/paaf-llm/tests/test_ports.py` (created) — 14 tests on the value types, exception hierarchy, Protocol shape, and re-export surface.
- `packages/paaf-llm/tests/test_fake_adapter.py` (created) — 14 tests including the four-trigger parametrization and the slow-first-token control.
- `packages/paaf-llm/tests/test_no_leak.py` (created) — 6 tests: the annotation walker, its two controls, and three framework-absence proofs.
- `packages/paaf-llm/tests/test_wheel_smoke.py` (modified) — added `test_langchain_not_importable_from_llm_wheel`; docstring corrected to state the file is excluded from the workspace suite.
- `scripts/check_wheel_independence.sh` (modified) — builds/installs three wheels, negative control is now `(paaf_voice, langchain)`, added a positive control.
- `.github/workflows/wheel-independence.yml` (modified) — step name and header comments describe the amended guard.
- `conftest.py` (modified) — the comment explaining `collect_ignore_glob` no longer claims `paaf_core` is asserted absent.

## Decisions Made

- **Programs are keyed by `profile.model`, not `profile.name`.** `ModelProfile` (plan 03-01) has no `name` field — a profile's name is the key it sits under in `LlmConfig.profiles`, so it does not travel with the profile object across `stream(profile, messages)`. Rather than widen the port signature (which siblings 03-06/03-08 are being written against concurrently) or edit the merged schema, `FakeAdapter.program_key()` prefers a `.name` attribute when one exists and falls back to `PROFILE_KEY_FIELD` (`model`). The `make_profile` fixture sets `model=name`, so `program("local", ...)` drives `make_profile("local")`. This is documented in three places: the fake's module docstring, `conftest.py`'s docstring, and `program_key`'s own docstring.
- **`LookupError`, not an `AdapterError`, for an un-programmed profile.** A fallback loop catches `AdapterError`; if the fake raised one for a profile nobody scripted, a forgotten `program()` call would be silently absorbed as a plausible-looking fallback hop and the test that forgot it would still pass.
- **The default usage is concrete (`Usage(7, 3)`), not `Usage()`.** A both-`None` default would let an aggregated-usage assertion pass against an engine that never called `last_usage()` at all.
- **`AllProvidersFailed` is not an `AdapterError`.** "Try the next profile" and "there is no next profile" must not be catchable by one `except`.
- **The no-leak walker inspects only own-declared members.** Folding in inherited pydantic `BaseModel` machinery (`model_dump`, `model_config`) would make the test flag `pydantic` types that are the base class's contract, not PAAF's public surface — and the assertion would then mean something other than what its name says.
- **`paaf_core` is an allowed root in the walker.** `ModelProfile.endpoint()` genuinely returns a `paaf_core` `Endpoint`; reusing the framework's own shared types is the opposite of leaking a swappable dependency's types. This allowance is exercised, not hypothetical — it is one of the 45 annotations walked.
- **The clean-venv job gained a positive control.** Asserting three packages ARE importable means the `paaf_voice`/`langchain` absence assertions cannot pass simply because the install silently produced an empty environment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `profile.name` does not exist; the fake needed a different program key**
- **Found during:** Task 2 (FakeAdapter implementation)
- **Issue:** The plan (and RESEARCH Pattern 2's `self._served_by = profile.name`) assumes `ModelProfile` carries a `name`. It does not — plan 03-01 keyed profiles by the `LlmConfig.profiles` dict key, so the name never crosses the `stream(profile, messages)` boundary. `FakeAdapter.program(profile_name, ...)` had nothing to match against.
- **Fix:** Added `FakeAdapter.program_key(profile)` — prefers a `.name` attribute when present, falls back to `PROFILE_KEY_FIELD` (`"model"`). The `make_profile` fixture sets `model` to the profile's name so the convention is invisible in test bodies. The port signature was NOT changed, because siblings 03-06/03-08 are being written against `stream(profile, messages)` in the same wave.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/fake/__init__.py`, `packages/paaf-llm/tests/conftest.py`
- **Verification:** `test_programs_are_addressed_per_profile` proves two profiles get two distinct scripts.
- **Committed in:** `9d8d43f` / `2f078d4`
- **Flagged for 03-06:** the engine needs the profile NAME for `TurnResult.served_by` and the fallback trail. It iterates `[active_profile, *fallback_chain]`, which are names, so it already has them — it should carry the name alongside the profile rather than read it off the profile object.

**2. [Rule 2 - Missing Critical] TDD tasks needed their own test files**
- **Found during:** Tasks 1 and 2
- **Issue:** Both tasks are `tdd="true"` but the plan's `files_modified` lists only `test_no_leak.py`. A TDD task cannot satisfy its RED gate without a failing test committed before the implementation, and `test_no_leak.py` does not cover the port's value semantics or the fake's behavior.
- **Fix:** Created `test_ports.py` (Task 1 RED) and `test_fake_adapter.py` (Task 2 RED), each covering only its own task's `<behavior>` block. Both gates are visible in git log as `test(...)` → `feat(...)` pairs. This matches the precedent set by plan 03-01's deviation 2.
- **Files modified:** `packages/paaf-llm/tests/test_ports.py`, `packages/paaf-llm/tests/test_fake_adapter.py`
- **Verification:** Both RED commits confirmed failing first (`ImportError: cannot import name 'ports'`, then `ModuleNotFoundError: No module named 'paaf_llm.fake'`).
- **Committed in:** `a04aa47`, `2f078d4`

**3. [Rule 1 - Bug] Stale comment in the root `conftest.py` describing the guard this plan amended**
- **Found during:** Task 3
- **Issue:** The root `conftest.py`'s `collect_ignore_glob` comment states the wheel smoke test "asserts that paaf_voice / paaf_core are NOT importable". After Task 3 that is false — `paaf_core` is now asserted *present*. Documentation that describes a guard incorrectly is how the guard's intent gets lost.
- **Fix:** Rewrote the comment to name `paaf_voice` + `langchain`, and added a Phase-3 note explaining why `paaf_core` moved from the negative to the positive control.
- **Files modified:** `conftest.py`
- **Verification:** `uv run pytest --disable-socket` → 130 passed; `ruff check conftest.py` clean.
- **Committed in:** `2b4463a`

**4. [Rule 1 - Bug] My own `test_wheel_smoke.py` docstring claimed the file runs in the workspace suite**
- **Found during:** Task 3 (verification)
- **Issue:** I wrote a docstring paragraph asserting these tests are collected by the ordinary workspace run and hold because `uv sync --all-packages` skips extras. Running the file directly proved otherwise: `test_paaf_voice_not_importable_from_llm_wheel` fails standalone, because the root `conftest.py` excludes the file from the suite entirely (`collect_ignore_glob`). The claim was wrong in a way that would have misled the next reader about where the guard actually runs.
- **Fix:** Replaced the paragraph with the accurate mechanism — the file is excluded by the root conftest and only runs under `pytest --pyargs paaf_llm` in the clean venv.
- **Files modified:** `packages/paaf-llm/tests/test_wheel_smoke.py`
- **Verification:** `bash scripts/check_wheel_independence.sh` → 3 smoke tests pass in the clean venv; the workspace suite collects 0 wheel-smoke tests, as designed.
- **Committed in:** `2b4463a`

### Deferred Item Resolved

`deferred-items.md` logged `packages/paaf-llm/tests/test_wheel_smoke.py:13` ruff `I001` (un-sorted imports), deferred by plan 03-01 to "whichever plan next touches the wheel-smoke surface". That is this plan: the file was rewritten in Task 3 with correct import order and now passes `ruff check` clean. `deferred-items.md` was left untouched (shared phase artifact — flagged for the orchestrator).

---

**Total deviations:** 4 auto-fixed (2 bugs, 1 blocking, 1 missing critical) + 1 deferred item resolved
**Impact on plan:** No plan artifact was skipped or substituted. Deviation 1 is the only design-shaped one; it was resolved *without* changing the port signature precisely so parallel siblings are unaffected.

## Issues Encountered

- **Resolving annotations that reference a type which does not exist.** `TurnResult.handoff` is annotated `HandoffRequest | None` where `HandoffRequest` is a Phase-4 payload with no definition. `ports.py` declares it under `TYPE_CHECKING` as PEP 695 `type HandoffRequest = Any`; `test_no_leak.py` supplies `HandoffRequest = object` in its resolution namespace so `get_type_hints` reaches the annotations that do matter instead of stopping at a `NameError`. Documented in both files.
- **`ruff` flagged `TypeAlias` (UP040) and two unused `noqa` directives.** The repo enables more than ruff's default rule set (I, UP, RUF, PL) with no config file. Fixed: PEP 695 `type` statement, and both `noqa`s removed.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-03-11 (tampering — framework type leaking through the public API) | `test_public_signatures_are_paaf_typed` walks all 45 public annotations and rejects any non-stdlib/non-PAAF root, with a planted-violation control proving it bites. `ports.py` and `fake/` carry source-text assertions that they name no framework. `__init__.py` imports nothing from the adapter package, asserted by `test_public_surface_exposes_no_engine_symbol`. |
| T-03-12 (tampering — wheel silently gaining an agent-framework dep) | The amended clean-venv job installs without the `[engine]` extra and asserts `import langchain` raises `ModuleNotFoundError` while the smoke suite runs green; `test_langchain_not_importable_from_llm_wheel` asserts the same at wheel-smoke level; a positive control proves the venv is genuinely populated. |
| T-03-13 (info disclosure — fake echoing secrets) | Accepted per plan. `FakeAdapter` handles only scripted tokens and PAAF exception types; no `api_key` value flows through it (real key resolution is plan 03-08's `_engine` adapter). Confirmed by inspection: nothing in `fake/` reads `api_key_ref` or a `SecretStore`. |

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest --disable-socket` (packages) | 130 passed (baseline 96 + 34 new) |
| `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` | 43 passed (baseline 41; +2 SPDX-header cases for the two new source files) |
| `uv run lint-imports` | 3 contracts kept, 0 broken |
| `bash scripts/check_wheel_independence.sh` | exit 0 — 3 smoke tests pass in the clean venv; `paaf_voice`/`langchain` absent; `paaf_llm`/`paaf_core`/`paaf_trace` present |
| `uv run ruff check` (this plan's files) | All checks passed |
| `uv run mypy` (ports.py, fake/, `__init__.py`) | Success, no issues in 3 source files |
| Plan Task-1 inline assertion | `TurnResult.handoff` default is `None`; `ConnectionFailed.reason == FallbackReason.CONNECTION` |
| Plan Task-2 inline assertion | `import paaf_llm` leaves no `langchain*`/`langgraph*` in `sys.modules` |

## TDD Gate Compliance

| Task | RED (`test`) | GREEN (`feat`) | REFACTOR |
|------|--------------|----------------|----------|
| 1 | `a04aa47` — confirmed failing (`ImportError: cannot import name 'ports'`) | `4d1357b` | not needed |
| 2 | `2f078d4` — confirmed failing (`ModuleNotFoundError: No module named 'paaf_llm.fake'`) | `9d8d43f` | not needed |
| 3 | n/a (`type="auto"`, not a TDD task) | `2b4463a` | — |

No test passed unexpectedly during a RED phase.

## Known Stubs

- **`TurnResult.handoff` is intentionally inert** — always `None` this phase. This is the plan's stated design (the Phase-4 seam): MESH-02 populates it from a parsed handoff signal and the serving profile's `peers`. It is declared now specifically so the port's shape is final; `test_turn_result_carries_the_inert_handoff_seam` pins the default so a future change is deliberate.
- **`TurnResult` is constructed by nobody yet** — plan 03-06's engine loop is its first producer. The type and its provenance fields exist so 03-06 and 03-09 (trace wiring, which already has `served_by`/`fallback_trail` columns from plan 03-02) agree on one shape.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 03-06 (agent/fallback loop)** has everything it needs: `ChatAdapter`, the four `AdapterError` subclasses to catch, `AllProvidersFailed` to raise, `FallbackReason.SLOW_FIRST_TOKEN` to record on its own `asyncio.timeout`, and a `FakeAdapter` that can be programmed to trigger each path. **Note the deviation-1 flag:** the engine must carry the profile *name* from the chain it is iterating; it cannot read it off the `ModelProfile`.
- **Plan 03-08 (`_engine` adapter)** implements this exact `ChatAdapter` and must translate its framework's exceptions into the four PAAF types. It must be imported lazily — `test_import_paaf_llm_needs_no_framework` and the clean-venv job both go red if `__init__.py` ever imports it eagerly.
- **Plan 03-09 (trace wiring)** can construct `TurnResult` and map `served_by`/`fallback_trail` straight onto the `runs` columns plan 03-02 added.
- **`packages/paaf-llm/tests/conftest.py` is now the shared fixture home** for the package. Sibling plans should extend it rather than defining local `FakeAdapter` factories, so the profile-naming convention stays in one place.
- **For the orchestrator:** `REQUIREMENTS.md` was intentionally left untouched. This plan completes MODEL-08 (recorded in `requirements-completed`), but the orchestrator owns that write. `deferred-items.md` also left untouched — its single entry is now resolved (see "Deferred Item Resolved").

## Self-Check: PASSED

All claimed artifacts verified present on disk and all claimed commits verified in git log.

| Claim | Result |
|-------|--------|
| `packages/paaf-llm/src/paaf_llm/ports.py` | FOUND |
| `packages/paaf-llm/src/paaf_llm/fake/__init__.py` | FOUND |
| `packages/paaf-llm/src/paaf_llm/__init__.py` | FOUND |
| `packages/paaf-llm/tests/conftest.py` | FOUND |
| `packages/paaf-llm/tests/test_ports.py` | FOUND |
| `packages/paaf-llm/tests/test_fake_adapter.py` | FOUND |
| `packages/paaf-llm/tests/test_no_leak.py` | FOUND |
| `packages/paaf-llm/tests/test_wheel_smoke.py` | FOUND |
| `scripts/check_wheel_independence.sh` | FOUND |
| `.github/workflows/wheel-independence.yml` | FOUND |
| `conftest.py` | FOUND |
| `.planning/phases/03-paaf-llm-core/03-05-SUMMARY.md` | FOUND |
| Commits `a04aa47`, `4d1357b`, `2f078d4`, `9d8d43f`, `2b4463a`, `9e6b080` | ALL FOUND |

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
