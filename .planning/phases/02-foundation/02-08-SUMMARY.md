---
phase: 02-foundation
plan: 08
subsystem: governance
tags: [licensing, apache-2.0, dco, spdx, conventional-commits, semver, privacy, anti-features, contributing, architecture]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "five-package uv workspace + SPDX-headered source files (Plan 01); .importlinter contracts + ci.yml suite job wired to run tests/test_governance.py explicitly (Plan 01/02); passphrase-at-boot master-key decision (Plan 05)"
provides:
  - "Apache-2.0 LICENSE (framework) + NOTICE stating framework-vs-deferred-apps license scope"
  - "CONTRIBUTING.md: DCO sign-off (no CLA), conventional commits, per-package semver, offline test-run commands"
  - "ARCHITECTURE.md: five-package map, the three import boundaries, config/secret/trace subsystems, apps deferred (D-07)"
  - "DECISIONS.md extended (Phase-1 preserved) with anti-feature list, no-accounts/no-telemetry-ever, skills-security posture, injection-defense constraint, open app-license question, passphrase-at-boot decision"
  - ".github/workflows/dco.yml: per-commit sign-off enforcement on PRs"
  - "tests/test_governance.py: doc-presence + DECISIONS-section + SPDX-header rot-guard (32 tests)"
affects: [04-tools-mcp-permissions TOOL-07 injection-defense enforcement, 05-skills SKILL-05 posture, 09-appliance boot-time passphrase delivery, 12-launch OSS docs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "governance rot-guard: root-level pytest globs packages/*/src/**/*.py and fails CI on any unheadered source file (FOUND-07)"
    - "DECISIONS.md is EXTENDED not overwritten — a test asserts Phase-1 D-05/D-12 caveats survive"
    - "commitments enforced mechanically where possible: no-telemetry backed by the no-network import contract + --disable-socket, not policy alone"

key-files:
  created:
    - LICENSE
    - NOTICE
    - CONTRIBUTING.md
    - ARCHITECTURE.md
    - .github/workflows/dco.yml
    - tests/test_governance.py
  modified:
    - DECISIONS.md

key-decisions:
  - "App license recorded as an OPEN governance question: framework Apache-2.0 (locked), apps default Apache-2.0 for v1, AGPL NOT chosen (per 02-CONTEXT Claude's Discretion)"
  - "SPDX header convention: code files carry `# SPDX-License-Identifier: Apache-2.0` as first non-empty line; docs/config carry a short comment license note"
  - "The governance test's DECISIONS.md section markers are matched case-insensitively so wording tweaks that preserve a commitment do not trip the guard, while deleting a section does"

patterns-established:
  - "Public commitments written from the phase's first commits (not at launch) so they are auditable and un-retrofittable, with a CI rot-guard keeping them present"
  - "Preview constraints (TOOL-07 injection-defense, SKILL-05 skills-security) recorded now so later phases inherit them rather than invent a hidden alternative"

requirements-completed: [FOUND-05, FOUND-06, FOUND-07, PRIV-01, PRIV-02]

coverage:
  - id: D1
    description: "Apache-2.0 LICENSE, NOTICE, DCO enforcement, and outsider-facing CONTRIBUTING/ARCHITECTURE docs exist from the phase's commits"
    requirement: "FOUND-06"
    verification:
      - kind: unit
        ref: "tests/test_governance.py::test_required_governance_doc_exists + ::test_license_is_apache_2"
        status: pass
    human_judgment: false
  - id: D2
    description: "Framework carries Apache-2.0 license, SPDX headers on source, DCO sign-off, documented conventional-commits + semver policy"
    requirement: "FOUND-07"
    verification:
      - kind: unit
        ref: "tests/test_governance.py::test_source_file_has_spdx_header (globs packages/*/src/**/*.py)"
        status: pass
    human_judgment: false
  - id: D3
    description: "DECISIONS.md records the anti-feature list, skills-security posture, and injection-defense constraint (extended, Phase-1 preserved)"
    requirement: "FOUND-05"
    verification:
      - kind: unit
        ref: "tests/test_governance.py::test_decisions_has_required_section + ::test_decisions_preserves_phase1_caveats"
        status: pass
    human_judgment: false
  - id: D4
    description: "No-accounts (PRIV-01) and no-telemetry-ever (PRIV-02) recorded as non-negotiable, enforced by the no-network import contract + --disable-socket"
    requirement: "PRIV-01, PRIV-02"
    verification:
      - kind: unit
        ref: "tests/test_governance.py::test_decisions_has_required_section[no telemetry|no accounts]; lint-imports no-network-client contract KEPT"
        status: pass
    human_judgment: false

# Metrics
duration: 4min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 08: Governance & Licensing Substrate Summary

**Apache-2.0 LICENSE + SPDX headers + DCO + conventional-commits/semver policy, an outsider-facing CONTRIBUTING.md and ARCHITECTURE.md, and a DECISIONS.md extended with the anti-feature list, the no-accounts/no-telemetry-ever guarantee, the skills-security posture, the permission-model-as-only-injection-defense constraint, and the open app-license question — all kept from rotting by a CI-run governance test.**

## Performance

- **Duration:** ~4 min
- **Completed:** 2026-07-25
- **Tasks:** 3 (all `type="auto"`, no checkpoints)
- **Files created:** 6; modified: 1

## Accomplishments

- **`LICENSE`** — full Apache-2.0 text (framework license, FOUND-07). **`NOTICE`** — copyright/attribution plus an explicit statement that the Apache-2.0 scope covers the five `packages/*`, that the two apps are unbuilt and default to Apache-2.0 for v1, and that AGPL is an open question, not chosen.
- **`CONTRIBUTING.md`** — DCO sign-off (`git commit -s`, DCO 1.1, **no CLA**), Conventional Commits, per-package SemVer (with the "public API must not leak framework types = breaking change" note), and a build/test section listing `uv sync --all-packages`, `uv run pytest --disable-socket`, and `uv run lint-imports`, plus the explicit root-level governance-test invocation CI uses.
- **`ARCHITECTURE.md`** — the five-package map (paaf-core + paaf-trace real; paaf-llm/voice/session stubs with their landing phases), the three import boundaries (voice↔llm independence, langchain confined to `paaf_llm._engine`, no network client in the framework) each with its enforcement and negative control, the config/secret/trace subsystems, a "where things live" tree, and the apps-deferred (D-07) note.
- **`DECISIONS.md`** (extended, Phase-1 content byte-preserved) — six new public-commitment sections: the anti-feature list (transcribed from REQUIREMENTS Out of Scope), the non-negotiable no-accounts (PRIV-01) + no-telemetry-ever (PRIV-02) guarantee, the skills-security posture (in-process, no sandbox, manifest is disclosure — SKILL-05 preview), the permission-model-as-only-injection-defense constraint with the no-hidden-defensive-prompts rule (TOOL-07 preview), the open app-license question, and the passphrase-at-boot master-key decision (from Plan 05) with its unattended-restart tradeoff.
- **`.github/workflows/dco.yml`** — walks each non-merge commit in a PR and fails on any missing a valid `Signed-off-by` trailer.
- **`tests/test_governance.py`** — 32 tests: five docs exist and are non-empty, LICENSE is Apache-2.0, each DECISIONS.md required-section marker present, Phase-1 D-05/D-12 caveats preserved, at least one source file exists, and every `packages/*/src/**/*.py` file carries the SPDX header as its first non-empty line (the FOUND-07 rot-guard). Wired into CI by the Plan 02 `suite` job's explicit invocation (root `testpaths = ["packages"]` skips root-level `tests/`).

## Task Commits

1. **Task 1 — LICENSE, NOTICE, CONTRIBUTING, ARCHITECTURE, DCO (FOUND-06, FOUND-07)** — `46d7484` (feat)
2. **Task 2 — extend DECISIONS.md with public commitments (FOUND-05, PRIV-01, PRIV-02)** — `21bec43` (docs)
3. **Task 3 — governance rot-guard test (FOUND-05/06/07)** — `92be998` (test)

## Verification

- `uv run pytest tests/test_governance.py -q --disable-socket` → **32 passed**
- `uv run pytest --disable-socket` (full package suite) → **67 passed** (no regressions)
- `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` (the CI root-level guard step) → **36 passed**
- `uv run lint-imports` → **3 contracts kept, 0 broken** (voice↔llm independence, langchain confinement, no-network-client)
- Task 1 automated grep gate and Task 2 marker grep gate both green; DCO and CI YAML parse as valid YAML.

## Deviations from Plan

None — the plan executed exactly as written. All three tasks are `type="auto"`; no checkpoints, no auth gates, no auto-fixes required. All commits were signed off (`git commit -s`) per the DCO policy this plan establishes.

## Threat Model Coverage

| Threat ID | Mitigation as built |
|-----------|---------------------|
| T-02-20 (undocumented commitments erode) | DECISIONS.md records anti-features, no-telemetry/no-accounts, skills-security, injection-defense; `test_decisions_has_required_section` asserts each stays present |
| T-02-21 (license-header erosion) | `test_source_file_has_spdx_header` globs `packages/*/src/**/*.py` and fails CI on any unheadered file (FOUND-07) |
| T-02-22 (injection-defense posture) | permission-model-as-only-injection-defense + no-hidden-defensive-prompts written in DECISIONS.md now (TOOL-07 enforces in Phase 4) |

No new threat surface introduced — this plan adds only docs, a doc-check test, and a CI workflow. No network endpoints, auth paths, or schema changes.

## User Setup Required

None. Forward reference: contributors must sign off commits (`git commit -s`); the DCO check enforces it on PRs.

## Next Phase Readiness

- SC#6 satisfied: DECISIONS.md, CONTRIBUTING.md, ARCHITECTURE.md, Apache-2.0 headers, and DCO exist from the phase's commits, with the anti-feature list, the no-accounts/no-telemetry-ever commitment, the skills-security posture, and the injection-defense constraint written publicly.
- Phase 4 (TOOL-07) inherits the injection-defense constraint; Phase 5 (SKILL-05) inherits the skills-security posture; Phase 9 (APP-\*) inherits the passphrase-at-boot boot-time-delivery obligation.
- The SPDX rot-guard now fails CI on any future source file added without the Apache-2.0 header.

## Self-Check: PASSED

- All 6 created files and the modified DECISIONS.md verified present on disk.
- All three task commits (`46d7484`, `21bec43`, `92be998`) verified in git log.
- Governance test green (32 passed); full offline suite green (67 passed); import contracts kept (3/0).

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
