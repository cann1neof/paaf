---
phase: 03-paaf-llm-core
plan: 01
subsystem: config
tags: [pydantic, model-profiles, schema, validation, endpoint, reload-tier, uv-workspace]

# Dependency graph
requires:
  - phase: 02-core-software
    provides: "paaf_core.config.schema.ReloadTier (per-field reload-tier metadata), paaf_core.net.endpoint.Endpoint (LAN classification with no DNS lookup), the uv workspace + import-linter contracts"
provides:
  - "ModelProfile — a named model (provider, model, endpoint, params) declared in YAML with no code (MODEL-01)"
  - "ModelProfile.endpoint() — returns a paaf_core Endpoint, or None for a provider default (CORE-05 seam)"
  - "The inert mesh seam: capabilities (free text), peers, constraints as validated data with no behavior (MODEL-05, D-07/D-08)"
  - "LlmConfig — base_prompt + active_profile + profiles map + ordered fallback_chain"
  - "LlmConfig._check_refs — load-time reference integrity across active_profile, fallback_chain, and the peer graph"
  - "paaf-llm's real base dependency set, workspace sources, and the `paaf` console script"
affects: [03-02-ports, 03-03-fake-adapter, 03-04-agent-fallback, 03-05-compose, 03-06-trace, 03-07-cli, 03-08-engine-adapter, 04-agent-mesh]

# Tech tracking
tech-stack:
  added: [pydantic>=2.13, pyyaml>=6.0.3, click>=8.4, rich>=15]
  patterns:
    - "Cross-package type reuse: paaf-llm imports ReloadTier/Endpoint from paaf-core rather than redefining them"
    - "model_validator(mode='after') for cross-field reference integrity — the repo's first"
    - "PEP 561 py.typed marker so paaf-core's types survive the package boundary under mypy"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/profiles.py
    - packages/paaf-llm/tests/test_profiles.py
    - packages/paaf-core/src/paaf_core/py.typed
  modified:
    - packages/paaf-llm/pyproject.toml
    - uv.lock

key-decisions:
  - "fallback_chain (on LlmConfig) and peers (on ModelProfile) stay separate fields — resilience and handoff are different semantics, and Phase 4 reads only peers"
  - "capabilities is a single free-text str, never structured fields — structured capability fields would be a routing DSL by the back door (D-08)"
  - "The peer graph is inert but INTEGRAL: dangling peer/fallback/active references are rejected at load, so Phase 4 never traverses a broken edge at runtime"
  - "Self-as-peer is rejected — a profile handing off to itself is a config error, not a no-op"
  - "Added PEP 561 py.typed to paaf-core: this plan is the repo's first cross-package typed import, and without the marker mypy cannot enforce the 'public API never leaks framework types' rule"
  - "Did NOT mark MODEL-01/05/06 complete in REQUIREMENTS.md — plans 03-07 and 03-08 also claim them; this plan delivers only the data contract half"

patterns-established:
  - "Positive control beside every rejection test: test_valid_config_loads proves the ValidationError tests are non-vacuous"
  - "Every ModelProfile/LlmConfig field carries explicit reload_tier metadata, matching the paaf-core ModelConfig.provider RESTART precedent"
  - "api_key_ref holds the NAME of a SecretStore key; no field in the schema can hold a secret value (CORE-04 / T-03-01)"

requirements-completed: [MODEL-01, MODEL-05, MODEL-06]

coverage:
  - id: D1
    description: "A user names model profiles (provider, model, endpoint, generation params) in one YAML tree with no code"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_lan_ollama_profile_declares_a_lan_endpoint"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_cloud_profile_declares_no_endpoint"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_profile_defaults"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_valid_config_loads"
        status: pass
    human_judgment: false
  - id: D2
    description: "Each profile declares a natural-language capability manifest, a peer list, and optional constraints as inert validated data"
    requirement: MODEL-05
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_capabilities_is_free_text_not_a_structured_schema"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_fallback_chain_and_peers_are_separate_fields"
        status: pass
    human_judgment: false
  - id: D3
    description: "A config referencing an undeclared active_profile, fallback target, or peer — or a profile listing itself as a peer — is rejected at load with a ValidationError"
    requirement: MODEL-05
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_peer_validation"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_unknown_config_key_is_rejected"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_unknown_profile_key_is_rejected"
        status: pass
    human_judgment: false
  - id: D4
    description: "Two same-provider Ollama profiles at distinct LAN endpoints are distinct profiles, each classifying LAN"
    requirement: MODEL-06
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_two_lan_profiles"
        status: pass
    human_judgment: false
  - id: D5
    description: "paaf-llm declares its real base dependencies as workspace sources and exposes the `paaf` console script"
    verification:
      - kind: integration
        ref: "uv sync --all-packages (resolves paaf-core + paaf-trace as workspace deps of paaf-llm)"
        status: pass
      - kind: integration
        ref: "uv run lint-imports (3 contracts kept — paaf-llm gained deps without breaking voice/llm independence)"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 01: Model Profile Schema Summary

**Pydantic `ModelProfile` + `LlmConfig` with a load-time reference-integrity validator over the peer graph and fallback chain, reusing paaf-core's `ReloadTier` and `Endpoint` — plus paaf-llm's first real dependency set.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-08-05T12:29:00Z
- **Completed:** 2026-08-05T12:37:00Z
- **Tasks:** 2 (both TDD — 4 commits)
- **Files modified:** 5

## Accomplishments

- `ModelProfile` gives the user a named model in YAML with no code: provider (a three-way `Literal`), model, endpoint host/port/scheme, `api_key_ref`, `temperature`, and the D-05 per-profile `first_token_budget_s`. Every field carries explicit `reload_tier` metadata so the desktop app can classify each key it might edit.
- `ModelProfile.endpoint()` returns a real `paaf_core.net.endpoint.Endpoint` — so a model profile is visible to the CORE-05 endpoint registry (and therefore to Phase-9's offline refusal) through the same one interface as everything else, not a parallel model-specific path.
- The MODEL-05 mesh seam ships as **inert validated data**: `capabilities` free text, `peers`, `constraints`. No handoff behavior exists; Phase 4 reads these.
- `LlmConfig._check_refs` makes the peer graph *integral before it is live*: an undeclared `active_profile`, an undeclared `fallback_chain` entry, an undeclared peer, or a self-peer each fails at load with a readable error instead of surfacing as a Phase-4 runtime failure.
- `paaf-llm` stopped being a dependency-free stub: real base deps, `[tool.uv.sources]` workspace wiring, and the `paaf` console script — with the `langchain` confinement and voice/llm independence contracts still green.

## Task Commits

Each task was committed atomically, following the TDD RED → GREEN gate:

1. **Task 1 (RED): failing ModelProfile test** — `4f4e077` (test)
2. **Task 1 (GREEN): ModelProfile + endpoint() + pyproject deps** — `3668173` (feat)
3. **Task 2 (RED): failing LlmConfig reference-integrity tests** — `32b97bb` (test)
4. **Task 2 (GREEN): LlmConfig + `_check_refs` validator** — `7b6c323` (feat)

## Files Created/Modified

- `packages/paaf-llm/src/paaf_llm/profiles.py` (created) — `ModelProfile` (fields + `endpoint()`) and `LlmConfig` (root + `_check_refs` cross-reference validator).
- `packages/paaf-llm/tests/test_profiles.py` (created) — 16 tests: profile defaults/bounds/extra-forbid, the free-text `capabilities` guard, `test_peer_validation`, `test_two_lan_profiles`, and the `test_valid_config_loads` positive control.
- `packages/paaf-llm/pyproject.toml` (modified) — base dependencies, `[tool.uv.sources]`, `[project.scripts] paaf`; existing hatch wheel + `force-include` blocks untouched.
- `packages/paaf-core/src/paaf_core/py.typed` (created) — PEP 561 marker (see deviation 1).
- `uv.lock` (modified) — regenerated by `uv sync --all-packages`.

## Decisions Made

- **`fallback_chain` and `peers` stay separate fields on separate models.** `fallback_chain` (on `LlmConfig`) is resilience — try these in order when the active profile degrades. `peers` (on each `ModelProfile`) is handoff — delegate on the merits. Collapsing them would silently make every fallback target a handoff target. A test (`test_fallback_chain_and_peers_are_separate_fields`) pins this so a later refactor cannot quietly merge them.
- **`capabilities` is one `str`, asserted at the schema level.** `test_capabilities_is_free_text_not_a_structured_schema` reads `ModelProfile.model_fields["capabilities"].annotation` directly, so promoting it to a nested model turns CI red — the D-08 routing-DSL guard is mechanical, not a comment.
- **Self-as-peer is rejected, not ignored.** Checked before the membership check so the error message names the real problem.
- **`extra="forbid"` on both models** (T-03-02), with `test_unknown_config_key_is_rejected` using a plausible `routing_rules` key as the negative control — the exact shape of smuggled field the threat model is about.
- **REQUIREMENTS.md deliberately not updated.** Plans 03-07 and 03-08 also claim MODEL-01/05/06; this plan ships only the data-contract half. Marking them complete now would be premature and would collide across parallel worktrees. Flagged for the orchestrator.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added PEP 561 `py.typed` marker to paaf-core**
- **Found during:** Task 2 (verification pass)
- **Issue:** `uv run mypy packages/paaf-llm/src/paaf_llm/profiles.py` reported two `import-untyped` errors — `Skipping analyzing "paaf_core.config.schema"` / `"paaf_core.net.endpoint": module is installed, but missing library stubs or py.typed marker`. This plan is the repo's first cross-package typed import (paaf-trace *declares* paaf-core as a dependency but never imports it), so the missing marker had never surfaced. Without it, `paaf_core`'s types degrade to `Any` at the package boundary, which defeats the CLAUDE.md rule that mypy mechanically enforces "the public API never leaks framework types".
- **Fix:** Added the empty `packages/paaf-core/src/paaf_core/py.typed` marker. Hatchling includes it in the wheel automatically (it lives inside the package dir); no packaging change needed.
- **Files modified:** `packages/paaf-core/src/paaf_core/py.typed`
- **Verification:** `uv run mypy packages/paaf-llm/src/paaf_llm/profiles.py` → `Success: no issues found in 1 source file`. Full suite still 88 passed; `lint-imports` still 3 contracts kept.
- **Committed in:** `7b6c323` (Task 2 GREEN commit)

**2. [Rule 2 - Missing Critical] `test_profiles.py` written during Task 1, not only Task 2**
- **Found during:** Task 1
- **Issue:** Task 1 is marked `tdd="true"` but lists only `profiles.py` and `pyproject.toml` in `<files>`, with the test file assigned to Task 2. A TDD task cannot satisfy its RED gate without a failing test committed before the implementation.
- **Fix:** Created `test_profiles.py` in Task 1's RED commit (`4f4e077`) covering only Task 1's `<behavior>` block, then extended the same file in Task 2's RED commit (`32b97bb`) with the `LlmConfig` cases. Both gates are visible in git log as `test(...)` → `feat(...)` pairs. Net artifacts are exactly what the plan specifies.
- **Files modified:** `packages/paaf-llm/tests/test_profiles.py`
- **Verification:** Both RED commits were confirmed failing before their GREEN counterpart (`ModuleNotFoundError: No module named 'paaf_llm.profiles'`, then `ImportError: cannot import name 'LlmConfig'`).
- **Committed in:** `4f4e077`, `32b97bb`

### Out of Scope (logged, not fixed)

`packages/paaf-llm/tests/test_wheel_smoke.py:13` fails ruff `I001` (un-sorted import block). Pre-existing since Phase 2 commit `5d6ee7f`, unrelated to this plan's files. Logged to `deferred-items.md` per the executor scope boundary. This plan's own files pass `ruff check` clean.

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 missing critical) + 1 out-of-scope item deferred
**Impact on plan:** Both auto-fixes were necessary for the plan's own acceptance criteria to hold honestly. The `py.typed` marker is a one-byte packaging fix, not scope creep. No plan artifact was skipped or substituted.

## TDD Gate Compliance

Both tasks carry `tdd="true"` and both show the full gate sequence in git log:

| Task | RED (`test`) | GREEN (`feat`) | REFACTOR |
|------|--------------|----------------|----------|
| 1 | `4f4e077` — confirmed failing (`ModuleNotFoundError`) | `3668173` | not needed |
| 2 | `32b97bb` — confirmed failing (`ImportError: cannot import name 'LlmConfig'`) | `7b6c323` | not needed |

No test passed unexpectedly during a RED phase.

## Verification Results

| Check | Result |
|-------|--------|
| `uv sync --all-packages` | Resolves paaf-core + paaf-trace as workspace deps of paaf-llm |
| `uv run pytest packages/paaf-llm -q` | 17 passed |
| `uv run pytest -q` (whole workspace) | 88 passed |
| `uv run lint-imports` | 3 contracts kept, 0 broken |
| `uv run ruff check` (this plan's files) | All checks passed |
| `uv run mypy .../profiles.py` | Success, no issues |
| Plan's Task-1 inline assertion | `p.endpoint().is_lan()` True, `first_token_budget_s == 10.0` |

## Issues Encountered

None beyond the two deviations above.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-03-01 (info disclosure) | `api_key_ref` holds only a SecretStore key NAME; no field in either model accepts an inline secret. Documented in the module and field docstrings. |
| T-03-02 (tampering) | `extra="forbid"` on both `ModelProfile` and `LlmConfig`, each with a dedicated negative-control test; `capabilities` pinned to `str` by a schema-level assertion. |
| T-03-03 (policy EoP) | Every networked profile declares its endpoint through `endpoint()` → `paaf_core.net.endpoint.Endpoint`, the exact set APP-08 refuses offline. A cloud profile returns `None` (no PAAF-declared endpoint) rather than hiding — asserted in `test_two_lan_profiles`. |

## Known Stubs

`peers` and `constraints` are intentionally inert this phase — validated data with no behavior attached. This is the plan's stated design (MODEL-05 / D-07): Phase 4 (MESH-02, MESH-06) reads and enforces them. `LlmConfig.base_prompt` is stored but not yet composed into a system message; plan 03-05 (`compose.py`) consumes it.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `ports.py` (03-02), `compose.py` (03-05), `agent.py` (03-04), and `cli.py` (03-07) can all import `ModelProfile` / `LlmConfig` as their config contract now.
- `first_token_budget_s` is on the profile, ready for the 03-04 fallback loop's `asyncio.timeout` (D-05).
- `endpoint()` is ready for the 03-08 `_engine` adapter's `base_url` derivation.
- **For the orchestrator:** REQUIREMENTS.md was intentionally left untouched — MODEL-01/05/06 are shared with plans 03-07 and 03-08 and should be marked complete only once those land.
- **Note for plan 03-09 (wheel job):** `paaf-llm` now depends on `paaf-core` and `paaf-trace`. The existing `test_wheel_smoke.py` negative control only asserts `paaf_voice` is unimportable, so it stays valid — but the clean-venv job will now install two more workspace wheels.

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
