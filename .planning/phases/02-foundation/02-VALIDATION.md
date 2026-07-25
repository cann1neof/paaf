---
phase: 2
slug: foundation
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-25
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 via uv (pytest-asyncio `asyncio_mode=auto`; pytest-socket for the no-network default) |
| **Config file** | root `pyproject.toml` → `[tool.pytest.ini_options]` (`addopts = "--disable-socket"`, `testpaths = ["packages"]`, `asyncio_mode = "auto"`) — created in Plan 01, Wave 1 |
| **Quick run command** | `uv run pytest --disable-socket` |
| **Full suite command** | `uv run pytest --disable-socket` (collects `packages/`) + `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` (root-level guards, not covered by `testpaths=["packages"]`) |
| **Estimated runtime** | ~30 seconds for the pytest suite; the wheel-independence script (`uv build` + clean-venv install) adds ~30–60 s and runs in its own CI job |

*Note: `testpaths = ["packages"]` means the default `uv run pytest` collects only the per-package tests. Root-level `tests/test_governance.py` and `tests/negcontrol/` must be named explicitly (locally and in the Plan 02 `suite` CI job) or they never execute.*

---

## Sampling Rate

- **After every task commit:** Run the task's own `<automated>` command (typically `uv run pytest <path> -q --disable-socket`)
- **After every plan wave:** Run `uv run pytest --disable-socket` plus the root-level `tests/test_governance.py` + `tests/negcontrol/` invocation
- **Before `/gsd-verify-work`:** Full suite green AND all three CI jobs green (`suite`, `wheel-independence`, `ttfa-gate`)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | FOUND-01 | T-02-01 | paaf-llm import graph free of voice/core/audio deps | smoke/import | `uv sync --all-packages && uv run python -c "import paaf_core, paaf_trace, paaf_llm, paaf_voice, paaf_session"` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | FOUND-03 | T-02-02 | `--disable-socket` is the suite default; shared fixtures discoverable | smoke/unit | `uv run pytest packages -k smoke -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 2 | FOUND-04 | T-02-03 / T-02-04 | three import contracts green on the clean workspace | contract | `uv run lint-imports` | ❌ new | ⬜ pending |
| 2-02-02 | 02 | 2 | FOUND-04 | T-02-05 | each contract goes RED on its deliberate violation (non-vacuous guard) | contract/neg-control | `uv run pytest tests/negcontrol/test_import_boundary.py -v` | ❌ new | ⬜ pending |
| 2-02-03 | 02 | 2 | FOUND-03 | T-02-04 | suite CI job offline; runs contracts + packages suite + governance + negcontrol | CI/yaml | `uv run python -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/ci.yml')); assert 'suite' in d['jobs']; print('suite job present')"` | ❌ new | ⬜ pending |
| 2-03-01 | 03 | 2 | FOUND-02 | T-02-06 / T-02-07 | built wheel installs into a clean venv; `paaf_voice`/`paaf_core` NOT importable (neg control) | integration/script | `bash scripts/check_wheel_independence.sh` | ❌ new | ⬜ pending |
| 2-03-02 | 03 | 2 | FOUND-02 | T-02-06 | wheel-independence CI job valid, pins Python 3.12 | CI/yaml | `uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/wheel-independence.yml')); assert 'wheel-independence' in d['jobs']; print('ok')"` | ❌ new | ⬜ pending |
| 2-04-01 | 04 | 2 | CORE-01, CORE-06 | T-02-10 | invalid config rejected (ValidationError neg control); reload tiers discoverable | unit (tdd) | `uv run pytest packages/paaf-core/tests/test_config_schema.py packages/paaf-core/tests/test_reload_tiers.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-04-02 | 04 | 2 | CORE-02, CORE-03 | T-02-08 / T-02-09 | atomic write survives mid-write crash; stale revision → ConflictError (neg control) | unit (tdd) | `uv run pytest packages/paaf-core/tests/test_atomic_write.py packages/paaf-core/tests/test_revision_conflict.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-05-CP | 05 | 2 | CORE-04 | T-02-13 | master-key provisioning source selected & recorded (durable on-disk contract) | manual / human-verify | checkpoint:decision (blocking) — see Manual-Only Verifications | n/a | ⬜ pending |
| 2-05-01 | 05 | 2 | CORE-04 | T-02-11 / T-02-12 | secret round-trips; plaintext absent from encrypted file; audited Fernet+scrypt only | unit (tdd) | `uv run pytest packages/paaf-core/tests/test_secret_store.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-05-02 | 05 | 2 | CORE-04, PRIV-01, PRIV-02 | T-02-11 / T-02-14 | secret absent from YAML tree and from logs; no account/cloud (neg controls) | unit (tdd) | `uv run pytest packages/paaf-core/tests/test_secret_store.py -k "yaml or log or offline" -q --disable-socket` | ❌ new | ⬜ pending |
| 2-06-01 | 06 | 2 | CORE-05 | T-02-15 / T-02-16 | LAN vs non-LAN classification; public endpoint flagged non-LAN (neg control); no DNS | unit (tdd) | `uv run pytest packages/paaf-core/tests/test_endpoint_declaration.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-07-01 | 07 | 2 | TRACE-02, TRACE-03 | — | schema records TRACE-02 fields; `time_to_first_audio` is a first-class REAL column | unit (tdd) | `uv run pytest packages/paaf-trace/tests/test_trace_schema.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-07-02 | 07 | 2 | TRACE-01 | T-02-17 / T-02-19 | emit never awaits; queue overflow drops with counter (off-hot-path neg control); WAL single writer | unit (tdd) | `uv run pytest packages/paaf-trace/tests/test_trace_queue.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-07-03 | 07 | 2 | TRACE-05 | T-02-18 | no network egress at runtime; no HTTP client in the `paaf_trace` graph | unit/neg-control | `uv run pytest packages/paaf-trace/tests/test_trace_no_egress.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-08-01 | 08 | 2 | FOUND-06, FOUND-07 | T-02-21 | Apache-2.0 LICENSE + DCO + outsider-facing CONTRIBUTING/ARCHITECTURE present | doc-presence | `test -f LICENSE && test -f CONTRIBUTING.md && test -f ARCHITECTURE.md && grep -qi 'Apache License' LICENSE && grep -q 'signed-off-by\|git commit -s\|Developer Certificate' CONTRIBUTING.md && echo OK` | ❌ new | ⬜ pending |
| 2-08-02 | 08 | 2 | FOUND-05, PRIV-01, PRIV-02 | T-02-20 / T-02-22 | DECISIONS.md records anti-features, no-telemetry/no-accounts, injection-defense, skills posture | doc-content | `grep -qi 'anti-feature\|anti feature' DECISIONS.md && grep -qi 'no telemetry\|telemetry' DECISIONS.md && grep -qi 'no account' DECISIONS.md && grep -qi 'injection' DECISIONS.md && grep -qi 'in-process\|no sandbox' DECISIONS.md && echo OK` | ❌ new | ⬜ pending |
| 2-08-03 | 08 | 2 | FOUND-07 | T-02-21 | docs exist with required sections; every `packages/*/src/**/*.py` carries the SPDX header (rot guard) | unit | `uv run pytest tests/test_governance.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-09-01 | 09 | 3 | TRACE-04 | T-02-23 / T-02-24 | TTFA accuracy (`abs(recorded-D)<tol`) + overhead + budget; accuracy FAILS for a broken recorder (neg control); no wall-clock | unit (tdd) | `uv run pytest packages/paaf-trace/tests/test_ttfa_regression.py -q --disable-socket` | ❌ new | ⬜ pending |
| 2-09-02 | 09 | 3 | TRACE-04 | T-02-25 | ttfa-gate CI job cold, offline, no audio deps, pins Python 3.12 | CI/yaml | `uv run python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ttfa-gate.yml')); assert 'ttfa-gate' in d['jobs']; print('ok')"` | ❌ new | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*File Exists: ✅ present at phase start · ❌ new = created within this phase · ❌ W0 = Wave-0 substrate created in Plan 01*

---

## Wave 0 Requirements

The shared test substrate is created in **Plan 01 (Wave 1)** and every later plan's `<automated>` verify depends on it. It is planned but not yet built (`wave_0_complete: false`):

- [ ] `conftest.py` (root) — shared fixtures `frozen_clock` (deterministic clock: `.now()`/`.monotonic()`/`.advance(seconds)`, NOT wall-clock), `tmp_config_path`, `captured_logs` (Plan 01 Task 2)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` — `addopts = "--disable-socket"`, `testpaths = ["packages"]`, `asyncio_mode = "auto"` (Plan 01 Task 2)
- [ ] uv workspace + dev toolchain — pytest 9.1.1, pytest-asyncio, pytest-socket, import-linter, ruff, mypy (Plan 01 Task 1)
- [ ] per-package `tests/test_smoke.py` scaffolds ×5 (Plan 01 Task 2)

Fixtures consumed downstream: `frozen_clock` → Plan 09 TTFA accuracy test; `captured_logs` → Plan 05 secret-absence-in-logs test; `tmp_config_path` → Plan 04 config tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Master-key provisioning source for the encrypted secret store | CORE-04 | A `checkpoint:decision` (blocking) — where the master key comes from (`key-file-0600` / `passphrase-at-boot` / `systemd-credential`) is a durable on-disk contract downstream phases inherit; no automated test can make this governance choice. Plan 05 is `autonomous: false` for this reason. | At the Plan 05 checkpoint the executor presents the three provisioning options; developer selects one (or, if unattended, `key-file-0600` is recorded as the RESEARCH A2 default and flagged for ratification). The choice is written to `02-05-SUMMARY.md` so Plan 08 can cite it in DECISIONS.md. The `EncryptedFileSecretStore` master-key loading is implemented against the chosen source. |

All other phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (the single exception is the Plan 05 `checkpoint:decision`, which is human-verify by design)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (no `<automated>MISSING` markers exist; shared fixtures + per-plan tests cover every requirement)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-25
