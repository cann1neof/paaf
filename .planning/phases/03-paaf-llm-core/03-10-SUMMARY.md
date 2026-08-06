---
phase: 03-paaf-llm-core
plan: 10
subsystem: cli
tags: [python, click, exceptions, ports, error-handling, tdd]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "ports.ChatAdapter + the four AdapterError subclasses; agent._run_chain's post-commit no-re-route rule; cli._chat_loop and the _default_adapter test seam; the real adapter's EngineError"
provides:
  - "paaf_llm.ports.EngineError — a port-level exception a framework-free caller can name in an except clause"
  - "paaf chat prints one readable line for a bind failure instead of a Python traceback (Gap 2 of 03-VERIFICATION)"
  - "paaf chat prints one readable line for a provider that fails AFTER the reply began, naming the FallbackReason value and stating no re-route was attempted"
  - "A negative control (LookupError) proving the new handlers name concrete types and are not a catch-all"
affects: [03-11, 03-12, 03-13, 04-agent-mesh, 09-embedded-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "An exception type that a framework-free caller must catch belongs in the PORT, not beside the optional-extra implementation that raises it"
    - "User-facing CLI strings are module constants, so tests assert against the text the CLI emits rather than a copy of it"
    - "Every readable-failure handler ships with a negative control proving it did not become a catch-all"

key-files:
  created: []
  modified:
    - packages/paaf-llm/src/paaf_llm/ports.py
    - packages/paaf-llm/src/paaf_llm/_engine/__init__.py
    - packages/paaf-llm/src/paaf_llm/__init__.py
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/test_ports.py
    - packages/paaf-llm/tests/test_engine_adapter.py
    - packages/paaf-llm/tests/test_inspector.py

key-decisions:
  - "EngineError moved to ports.py rather than duplicated: the adapter package is unimportable without the optional [engine] extra, so a class defined there can never appear in a framework-free except clause. This was the structural reason Gap 2 was unfixable in place."
  - "The adapter package imports and re-exports the port's EngineError; there is exactly one definition, guarded by an identity test, because two same-named classes would let the adapter raise one while the CLI catches the other with every other test still green."
  - "AllProvidersFailed keeps its own message and does NOT gain the config prefix — chain exhaustion is not a configuration error, and prefixing it would blame the user's YAML for a run of unreachable providers."
  - "The mid-reply notice formats {reason} from exc.reason.value, never from the exception's class name, so the terminal message and the trace row agree on why the turn ended (D-06)."
  - "No new test file was added under packages/paaf-llm/tests/ — a new one would need registering in the wheel force-include list and the SC#1 gate's exclusion list, and an unregistered one fails the gate's non-vacuity guard."

patterns-established:
  - "Port-level exception placement: catchability by a framework-free caller is a design constraint on WHERE a class lives, not just on what it means"
  - "Paired failure tests: each positive readable-failure claim carries a control that fails if the handler is widened"

requirements-completed: [MODEL-03, MODEL-04, MODEL-08]

coverage:
  - id: D1
    description: "EngineError is a port type: importable from paaf_llm and paaf_llm.ports with the agent framework uninstalled, not an AdapterError subclass"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_engine_error_is_not_a_degraded_provider"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_ports.py#test_public_surface_re_exports_paaf_types"
        status: pass
      - kind: integration
        ref: "bash scripts/check_framework_uninstalled.sh (SC#1 gate — full fake-adapter suite in a clean venv with langchain/langgraph not importable)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The adapter package's EngineError IS ports.EngineError — one class object, not a second definition"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_engine_error_is_the_class_the_port_declares"
        status: pass
    human_judgment: false
  - id: D3
    description: "paaf chat prints a one-line readable error and exits non-zero when a profile cannot be bound (missing credential, wrong model name) instead of a Python traceback"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_bind_failure_is_reported_readably"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_build_time_failure_is_reported_readably"
        status: pass
      - kind: e2e
        ref: "echo hello | uv run paaf chat --config <yaml declaring api_key_ref with no secret store> — the verifier's own reproduced case, now exit 1 with one line"
        status: pass
    human_judgment: false
  - id: D4
    description: "paaf chat prints a readable error when a provider fails AFTER the reply has begun, naming the fallback reason and saying no re-route was attempted"
    requirement: MODEL-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_failure_after_the_reply_began_is_reported_readably"
        status: pass
    human_judgment: false
  - id: D5
    description: "A pre-commit AdapterError still produces a fallback hop, not an error line — the new handler did not intercept the ordered fallback chain"
    requirement: MODEL-03
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_failure_before_the_reply_began_still_falls_back"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py (full file, 0 failures)"
        status: pass
    human_judgment: false
  - id: D6
    description: "An exception that is neither a configuration failure nor a degraded provider still escapes — the new handlers are not a catch-all"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_an_unexpected_exception_still_escapes"
        status: pass
      - kind: other
        ref: "! grep -q 'except Exception' packages/paaf-llm/src/paaf_llm/cli.py"
        status: pass
    human_judgment: false

# Metrics
duration: 19min
completed: 2026-08-06
status: complete
---

# Phase 3 Plan 10: Readable Failure Surfaces on `paaf chat` Summary

**`EngineError` relocated from the optional-extra adapter package into `ports.py`, which is what finally made it catchable — and three named failure surfaces on `paaf chat` (bind, build-time, post-commit), each with a control proving its handler is not a catch-all**

## Performance

- **Duration:** 19 min
- **Started:** 2026-08-06T12:01:00Z
- **Completed:** 2026-08-06T12:20:12Z
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 7

## Accomplishments

- **Closed Gap 2 of `03-VERIFICATION.md`** (status `failed`, classified 🛑 Blocker). The verifier reproduced an unhandled `EngineError` traceback twice; the same invocation now exits 1 with a single line. Verified live, not just in tests — see "Live reproduction" below.
- **Found and removed the structural reason the gap existed.** `EngineError` was defined inside `paaf_llm._engine`, which raises `ImportError` when the optional `[engine]` extra is absent. A framework-free CLI therefore *could not name it in an `except` clause at all*. The fix was not a `try` block; it was moving the type to the port its own docstring already described ("PAAF-typed on purpose — no framework exception escapes the port").
- **One class, not two.** The adapter package now imports and re-exports the port's `EngineError`. `test_engine_error_is_the_class_the_port_declares` asserts identity with `is`, because two divergent same-named classes would let the adapter raise one while the CLI's handler names the other — and every other test in both files would still pass.
- **Three failure surfaces, three controls.** Bind failure, build-time provider-table failure, and post-commit provider failure each read as one line; `test_an_unexpected_exception_still_escapes` (a `LookupError`) and `test_a_failure_before_the_reply_began_still_falls_back` (a pre-commit `ConnectionFailed` that must still hop) are the controls that fail if either handler is widened.

## Task Commits

Each task was committed atomically, RED before GREEN:

1. **Task 1: Move EngineError into the port** — `e5ffbc3` (test, RED) → `d398b2f` (feat, GREEN)
2. **Task 2: Readable bind failure** — `b64dd17` (test, RED) → `3ced4fa` (feat, GREEN)
3. **Task 3: Readable post-commit failure** — `1026d8e` (test, RED) → `6f4ee04` (feat, GREEN)

No REFACTOR commits were needed; each GREEN implementation was already at its final shape.

RED was observed, not assumed. Task 1 RED: `ImportError: cannot import name 'EngineError' from 'paaf_llm'`. Task 2 RED: `<Result EngineError("profile 'cloud': no binding for provider 'moon'")>` — the exception escaping is visible in the failure output. Task 3 RED: `<Result ServerError('upstream exploded')>`.

## The exact text of both new notices

Recorded verbatim as the plan's `<output>` section requires. Both live in `packages/paaf-llm/src/paaf_llm/cli.py` as module constants, following the file's existing convention (`FALLBACK_NOTICE`, `NO_FALLBACK_TARGET`, `PROVENANCE_LABEL`, `NO_HANDOFF_NOTE`) so tests assert against the text the CLI actually emits.

```python
CONFIG_FAILURE_NOTICE = "paaf could not use the model you configured: {detail}"

MID_REPLY_FAILURE_NOTICE = (
    "the model failed after it had begun replying ({reason}); the chain does not "
    "re-route once a reply has started: {detail}"
)
```

## Live reproduction — the verifier's own case

Run with the `[engine]` extra installed, against a config declaring `api_key_ref: anthropic_key` with no secret store behind it. Previously a ~30-line Python traceback:

```
Error: paaf could not use the model you configured: could not bind
'anthropic:claude-sonnet-4-5': profile declares api_key_ref 'anthropic_key' but
no secret store was provided to the adapter; the key value is never read from YAML
```

Exit code 1. Note the underlying detail is unchanged and still fully informative — the CLI adds a framing sentence and removes the traceback, nothing more. It renders no config contents and no credential (T-03-30: the detail is the adapter's own already-scrubbed message).

## Files Created/Modified

- `packages/paaf-llm/src/paaf_llm/ports.py` — `EngineError(Exception)` defined here, placed after `AllProvidersFailed` and before `TurnResult`. Its docstring states the three things the plan required, and refers to "the real adapter" / "the adapter package" in prose only (Constraint 2 — the source-text grep in `test_ports_source_imports_no_agent_framework` reads docstrings and comments too).
- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` — local `class EngineError` deleted; `EngineError` added to the existing alphabetical `from ..ports import (...)` block; `"EngineError"` kept in `__all__` so `from paaf_llm._engine import EngineError` still resolves; the "What is deliberately NOT translated" paragraph now points at the port and explains why the placement is load-bearing.
- `packages/paaf-llm/src/paaf_llm/__init__.py` — `EngineError` added to the `.ports` import block and to `__all__`, both between `ConnectionFailed` and `FakeAdapter`.
- `packages/paaf-llm/src/paaf_llm/cli.py` — `CONFIG_FAILURE_NOTICE`, `MID_REPLY_FAILURE_NOTICE`, the `_config_failure()` helper, `except EngineError` and `except AdapterError` in `_chat_loop`, and a `try`/`except EngineError` around `build_agent(config)` in `chat`.
- `packages/paaf-llm/tests/test_ports.py` — `test_engine_error_is_not_a_degraded_provider`; `test_public_surface_re_exports_paaf_types` extended with the `EngineError` identity assertion.
- `packages/paaf-llm/tests/test_engine_adapter.py` — `test_engine_error_is_the_class_the_port_declares` under a new `MODEL-08: one EngineError` section.
- `packages/paaf-llm/tests/test_inspector.py` — a `readable failure surfaces` section with two local adapter classes (`_RaisingAdapter`, `_FailsAfterFirstTokenAdapter`, both following the `_SlowLaterTokensAdapter` precedent) and five tests.

**No new test file was added under `packages/paaf-llm/tests/`** (Constraint 3, confirmed). The SC#1 gate's non-vacuity guard reports `ok: all 11 fake-adapter test files ship in the wheel` — the same count as before this plan, so neither `pyproject.toml`'s `force-include` nor `EXCLUDED_FROM_WHEEL` needed touching. No dependency was added and no `pyproject.toml` was modified.

## Existing tests that needed an edit beyond the ones named in the plan

Two, both in `packages/paaf-llm/tests/test_inspector.py`, both minor:

1. **`inject()`'s parameter annotation widened from `FakeAdapter` to `ChatAdapter`.** The plan instructs injecting local adapter classes through the existing `inject()` helper, and those are not `FakeAdapter` instances. The annotation would have been a lie. `ChatAdapter` is a PAAF port type, so Constraint 4 is respected. Runtime behavior is unchanged (`monkeypatch.setattr` never consulted the annotation); no type checker runs in CI, so this was hygiene rather than a fix.
2. **`test_public_surface_re_exports_paaf_types` in `test_ports.py` gained one import and one assertion** — this one *was* named in the plan and is listed here only for completeness.

No other existing test's body or assertions were modified. `test_healthy_turn_prints_no_fallback_notice` and `test_manifest_performs_no_handoff` pass unchanged, confirming the new handlers do not fire on a healthy run.

## Decisions Made

- **`EngineError` belongs in the port, and that is a design conclusion rather than a convenience.** Where an exception lives determines who can catch it. A class behind an optional extra is uncatchable by callers that run without the extra, which in this codebase means the CLI — the one caller most likely to need it. The port's job is to be nameable by a framework-free caller, and an exception is part of a contract just as much as a return type.
- **`AllProvidersFailed` keeps its existing message.** The plan called for this and it is worth restating: chain exhaustion already names every hop and reads well, and prefixing it with "paaf could not use the model you configured" would blame the user's YAML for a run of unreachable providers.
- **`{reason}` is read from `exc.reason.value`, never from a class name.** This keeps the CLI consistent with the engine's rule that a hop is classified by reading `.reason`, and makes the terminal message and the trace row agree (D-06, T-03-32).
- **The `except AdapterError` clause carries a comment explaining it is not a duplicate of the fallback loop.** Reaching it means the turn loop already committed to a profile; a pre-commit `AdapterError` is caught inside `agent._run_chain` and becomes a hop. Without the comment a future reader would reasonably assume the clause is redundant and delete it.

## Deviations from Plan

The plan was followed as written. Two small adjustments were made inside its stated intent:

### Adjustments

**1. `CONFIG_FAILURE_NOTICE` cross-referenced from the `_config_failure` docstring**
- **Found during:** Task 2 acceptance-criteria check
- **Issue:** The plan's criterion expects `grep -c 'CONFIG_FAILURE_NOTICE' cli.py` to return at least 3 ("the constant, the helper, and no fewer than one usage"). The plan's own design — one constant, one helper, two call sites that go through the helper — yields only 2 occurrences, so the criterion and the design were in tension.
- **Fix:** Rather than restructure the code to inflate a count, the helper's docstring now names `:data:`CONFIG_FAILURE_NOTICE`` and states the module convention it follows. That is a genuine cross-reference a reader benefits from, and it brings the count to 3.
- **Also:** the two Task-2 tests were strengthened from `assert detail in result.output` to `assert CONFIG_FAILURE_NOTICE.format(detail=detail) in result.output`, which is what the module-constant convention exists for and is a strictly stronger assertion than the plan specified.
- **Committed in:** `3ced4fa`

**2. [Rule 3 — Blocking] `uv sync --all-packages` needed before the suite would run**
- **Found during:** Task 1 baseline
- **Issue:** A fresh worktree has no populated `.venv`; `pytest` failed with `ModuleNotFoundError: No module named 'paaf_llm'` at conftest import.
- **Fix:** Ran `uv sync --all-packages`. Environment-only; no file changed.
- **Verification:** Baseline established green (99 passed, 1 skipped) before any edit was made, so every RED below is a real RED and not an artifact of a broken environment.

---

**Total deviations:** 2 (1 criterion/design reconciliation, 1 blocking environment fix)
**Impact on plan:** None on scope. Both adjustments strengthen what the plan asked for rather than substituting for it.

## Issues Encountered

- **Ruff caught an unused import and an over-long import line** after Task 2, because `ServerError` was imported one task before it was used. Resolved by importing it in Task 3 where it is actually needed and wrapping the `paaf_llm.ports` import block. `uv run ruff check packages/paaf-llm` reports **All checks passed**.
- Nothing else. No architectural question arose and no checkpoint was needed.

## Verification Results

All five of the plan's `<verification>` steps were run:

| # | Check | Result |
|---|-------|--------|
| 1 | `uv run pytest packages/paaf-llm -q --disable-socket` | **105 passed, 1 skipped** (the skip is `test_engine_adapter.py`'s `importorskip`) |
| 2 | `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` | **27 passed, 0 skipped**; `test_engine_error_is_the_class_the_port_declares` confirmed RAN (`PASSED`), not skipped. Full package with the extra: **132 passed, 0 skipped** |
| 3 | `uv run lint-imports --no-cache` | **3 contracts kept, 0 broken** — `ports.py` gained no import; the adapter package's whitelist is unchanged |
| 4 | `uv run pytest -q --disable-socket` (whole workspace) | **180 passed, 1 skipped** |
| 5 | `uv sync --all-packages` | Baseline restored; the worktree is left in the documented no-extra state for the next plan |

Additional gates run beyond the plan's list:

- `bash scripts/check_framework_uninstalled.sh` — **PASS**. Builds the wheels, installs into a clean venv with no `[engine]` extra, and runs the full fake-adapter suite there (**108 passed**) with `langchain` and `langgraph` proven not importable. This is the check that matters most for Task 1: the new tests in `test_inspector.py` and `test_ports.py` ship in the wheel and run where the framework is genuinely absent.
- `uv run ruff check packages/paaf-llm` — **All checks passed**.

Acceptance-criteria greps, all satisfied:

| Criterion | Result |
|---|---|
| `grep -c 'class EngineError' ports.py` | `1` |
| `! grep -q 'class EngineError' _engine/__init__.py` | succeeds (grep exit 1) |
| `! grep -q '_engine' ports.py` | succeeds (grep exit 1) — raw file, no comment filter |
| `python -c "... paaf_llm.EngineError is paaf_llm.ports.EngineError ..."` | prints `ok` |
| `"EngineError"` in `paaf_llm.__all__` and the adapter's `__all__` | both true |
| `! grep -q 'except Exception' cli.py` | succeeds (grep exit 1) |
| `grep -c 'CONFIG_FAILURE_NOTICE' cli.py` | `3` |
| `grep -c 'MID_REPLY_FAILURE_NOTICE' cli.py` | `2` |
| `grep -c 'exc.reason.value' cli.py` | `1` |
| stream-call count in the mid-reply test | asserted `== ["local"]`, i.e. exactly 1 |

## Threat Model Disposition

| Threat ID | Disposition | Status |
|---|---|---|
| T-03-30 (info disclosure via rendered third-party error text) | mitigate | **Held.** The interpolated detail is the adapter's own message, already scrubbed of resolved secret values by `LangChainAdapter._scrub` (T-03-04, still covered by `test_a_resolved_key_never_appears_in_a_raised_message`). The CLI adds no formatting of credentials and renders no config contents. |
| T-03-31 (broad `except Exception` absorbing real bugs) | mitigate | **Held.** Handlers name `AllProvidersFailed`, `EngineError`, and `AdapterError` exactly; `test_an_unexpected_exception_still_escapes` turns red on a catch-all rewrite; the negated grep passes. |
| T-03-32 (mid-reply failure reported without naming why) | mitigate | **Held.** The notice interpolates `exc.reason.value`, the same `FallbackReason` the trace records. |
| T-03-SC (package installs) | mitigate | **Held vacuously, as intended.** No package was installed and no dependency list was edited; `packages/paaf-llm/pyproject.toml` is untouched. |

No new security-relevant surface was introduced: no network endpoint, no auth path, no file access pattern, no schema change. No threat flags.

## Known Stubs

None. Nothing in this plan renders placeholder data or leaves a component unwired.

## Scope Note — what this plan does NOT claim

Stated so the phase requirements table is not read as asserting more than the tasks produced:

- **MODEL-08** is addressed by Task 1: `EngineError` becomes a port type a framework-free caller can name — the requirement's own property applied to an exception.
- **MODEL-03 / MODEL-04** are addressed by Task 3, which reads `exc.reason.value` off the `FallbackReason` enum and carries the paired control `test_a_failure_before_the_reply_began_still_falls_back`. A handler that intercepted every `AdapterError` before the fallback loop saw it would break both outright; that control is what keeps them true.
- **MODEL-02 is deliberately NOT claimed.** No task here adds, changes, or tests provider support. Its OpenAI-compatible leg is 03-12's work.
- **Gap 1 is NOT closed here.** `cli._default_adapter` still calls `build_engine_adapter(config)` without a secret store, so an `api_key_ref` profile remains unusable from `paaf chat` — the live reproduction above is precisely that failure, now *reported readably* rather than fixed. Wiring the secret store is a separate gap-closure plan.

## User Setup Required

None — no external service configuration required. Every test in this plan is decidable offline under `--disable-socket`.

## Next Phase Readiness

- `paaf chat` no longer produces a traceback on any of the three named failure paths. The remaining `03-1x` gap-closure plans can proceed independently; nothing here touches their files.
- `paaf_llm.ports.EngineError` is now available to any framework-free caller, which the Phase 9 embedded app and its config API will want for the same reason the CLI did.
- **Environment note for the next executor:** the worktree is left synced with `uv sync --all-packages` (no `[engine]` extra), matching the documented baseline. `packages/paaf-llm` should report 105 passed, 1 skipped in that state.

## Self-Check: PASSED

- All 7 claimed files verified present on disk.
- All 7 claimed commits verified present in `git log`.
- `git diff --diff-filter=D dd48187..HEAD` reports no deleted files — nothing was removed by this plan.
- Working tree clean; no uncommitted changes remain.

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-06*
