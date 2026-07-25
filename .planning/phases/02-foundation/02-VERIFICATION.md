---
phase: 02-foundation
verified: 2026-07-25T18:55:05Z
status: passed
score: 6/6 must-haves verified (20/20 requirements)
behavior_unverified: 0
overrides_applied: 0
re_verification:
  # No previous VERIFICATION.md existed — this is the initial verification.
notes:
  - "ROADMAP marks Phase 2 `mode: mvp`, but the phase goal is an infrastructure outcome, not an `As a…, I want…, so that…` User Story. Per 02-CONTEXT.md the six Success Criteria are the real contract; verification is goal-backward against those six SCs (standard methodology), not MVP user-flow coverage. Informational — not a gap."
---

# Phase 2: Foundation Verification Report

**Phase Goal:** A monorepo where the architectural rules that everything else depends on are build failures rather than intentions, and where time-to-first-audio is already a number CI defends.
**Verified:** 2026-07-25T18:55:05Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

This phase's entire value proposition is that the guards are REAL — a check that cannot fail is not a check (the twice-caught Phase-1 lesson). Verification therefore ran every contract/gate on the real tree AND confirmed each NEGATIVE CONTROL genuinely bites on a deliberate violation, executing the tests rather than trusting SUMMARY claims.

### Observable Truths (the six ROADMAP Success Criteria)

| #   | Truth (Success Criterion) | Status | Evidence |
| --- | --- | --- | --- |
| 1 | A deliberate `paaf-voice→paaf-llm` import, or `langchain*` outside the adapter, fails CI on import-linter; suite otherwise green with no audio/network | ✓ VERIFIED | `lint-imports` reports 3 contracts KEPT on real tree. Ran `tests/negcontrol/test_import_boundary.py` → 4 passed; manually confirmed `independence` goes RED (`paaf_voice_violation -> paaf_llm (l.12)`). `uv run pytest -q` → 72 passed under `--disable-socket`. Socket guard verified biting (injected AF_INET connect → `SocketBlockedError`). |
| 2 | A separate CI job installs the built `paaf-llm` wheel into a clean venv with no workspace and runs its smoke tests | ✓ VERIFIED | Ran `scripts/check_wheel_independence.sh`: wheel built, installed into off-repo venv, `pytest --pyargs paaf_llm` → 2 passed, and negative control fired — `paaf_voice` AND `paaf_core` both NOT importable. `.github/workflows/wheel-independence.yml` wires it in CI. |
| 3 | Config validates on a typed schema, writes atomically, bumps a monotonic revision, rejects stale writes as conflicts; API keys in a separate store the YAML/logs never contain | ✓ VERIFIED | CORE-01/02/03/04 all carry biting negative controls (out-of-range/mistyped rejected; injected crash at `os.replace` leaves original intact + no temp leftover; stale revision → `ConflictError` with file untouched; wrong passphrase → `InvalidPassphraseError`, plaintext absent from encrypted bytes/YAML/logs). See tables below. |
| 4 | Every component declares network endpoints through one interface; each config key reports its reload tier on request | ✓ VERIFIED | `EndpointRegistry` + `Endpoint.is_lan()` (stdlib `ipaddress`, no DNS) with non-LAN negative control (`api.openai.com`, `8.8.8.8` → non-LAN). `reload_tiers(AppConfig)` returns dotted paths for all keys incl. all four tiers + documented default fallback. |
| 5 | A run's prompts/model/tool-calls-args+results/timings/tokens land in local SQLite off the hot path, `time_to_first_audio` is a first-class column, and CI asserts it cold with a fake TTS | ✓ VERIFIED | WAL + single-writer bounded queue; `emit` is sync non-blocking, drops-on-overflow (proven). `schema.sql` has all TRACE-02 columns + `time_to_first_audio REAL` first-class. TTFA gate: accuracy (tol 1e-9) + overhead ceiling + budget, on `frozen_clock`, with a negative control proving a whole-round-trip/constant recorder FAILS accuracy while slipping under budget. No-egress control runs under `--disable-socket`. |
| 6 | `DECISIONS.md`, `CONTRIBUTING.md`, architecture doc, Apache-2.0 headers + DCO exist from first commits, with anti-feature list, no-accounts/no-telemetry-ever, skills-security posture, injection-defense constraint written publicly | ✓ VERIFIED | `tests/test_governance.py` (38 passed) rot-guard: 5 required docs exist, LICENSE is Apache-2.0, every `packages/*/src/**/*.py` first non-empty line is the SPDX id, DECISIONS.md required markers present. DCO enforced by `.github/workflows/dco.yml`; CONTRIBUTING covers DCO/conventional-commits/SemVer/pytest. |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `.importlinter` | 3 real contracts over 5 packages | ✓ VERIFIED | independence / langchain-confined / no-network — all KEPT on real tree |
| `tests/negcontrol/` (3 fixtures + config + test) | Proof each contract goes RED | ✓ VERIFIED | Each fixture imports the forbidden edge; paired test asserts nonzero exit + contract name |
| `scripts/check_wheel_independence.sh` | Clean-venv wheel install + neg control | ✓ VERIFIED | Executed end-to-end; leak guard for paaf_voice/paaf_core |
| `packages/paaf-core/.../config/{schema,store,reload_tiers}.py` | CORE-01/02/03/06 | ✓ VERIFIED | Pydantic schema, temp+fsync+rename+dirfsync, FileLock+revision, tier discovery |
| `packages/paaf-core/.../secrets/{interface,fernet_backend}.py` | CORE-04 pyca-only crypto | ✓ VERIFIED | Fernet + Scrypt from `cryptography` only; no hand-rolled crypto; 0600 file; repr scrubbed |
| `packages/paaf-core/.../net/endpoint.py` | CORE-05 declaration + LAN class | ✓ VERIFIED | Protocol + registry + `is_lan()` no-DNS |
| `packages/paaf-trace/.../store.py` + `schema.sql` | TRACE-01/02/03/05 | ✓ VERIFIED | WAL single-writer bounded queue; raw SQL (no ORM); TTFA first-class column |
| `packages/paaf-trace/.../_testing/fake_tts.py` | TRACE-04 fake engine on injected clock | ✓ VERIFIED | Clock-driven, no wall-clock/sleep; distinguishes first-audio from round-trip |
| `LICENSE`/`NOTICE`/`CONTRIBUTING.md`/`ARCHITECTURE.md`/`DECISIONS.md` | FOUND-05/06/07 | ✓ VERIFIED | All present, non-empty, rot-guarded |
| `.github/workflows/{ci,wheel-independence,ttfa-gate,dco}.yml` | CI enforcement | ✓ VERIFIED | Root-level tests named explicitly (`testpaths=["packages"]` would otherwise skip them) |
| 5 framework packages, independently versioned | FOUND-01 | ✓ VERIFIED | Each has own pyproject `version=0.1.0` + `__version__`; apps not scaffolded per D-07 |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `ci.yml` suite job | `tests/test_governance.py` + `tests/negcontrol/` | explicit `uv run pytest tests/… --disable-socket` | ✓ WIRED | Without this the root tests (outside `testpaths`) would never fail CI — correctly named explicitly |
| `metrics.record_time_to_first_audio` | `runs.time_to_first_audio` | `TtfaUpdate.as_sql()` via single writer | ✓ WIRED | TTFA gate reads the column back from SQLite after recording |
| config `atomic_write_bytes` | on-disk YAML | temp+fsync+`os.replace`+dir-fsync | ✓ WIRED | Crash-injection test confirms old-or-new, never partial |
| `EncryptedFileSecretStore` | Fernet/Scrypt | `cryptography.fernet` + `hazmat…scrypt` | ✓ WIRED | No `hashlib`/bespoke cipher anywhere in the module |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Full workspace suite offline | `uv run pytest -q` | 72 passed (1.87s) | ✓ PASS |
| Import contracts on real tree | `uv run lint-imports --config .importlinter` | 3 kept, 0 broken | ✓ PASS |
| Import negcontrols bite | `uv run pytest tests/negcontrol/test_import_boundary.py -q` | 4 passed | ✓ PASS |
| independence contract goes RED | manual `lint-imports … --contract independence` | nonzero, names the violation | ✓ PASS |
| Wheel independence + neg control | `bash scripts/check_wheel_independence.sh` | PASS; paaf_voice & paaf_core not importable | ✓ PASS |
| Socket guard non-vacuous | injected AF_INET connect under `--disable-socket` | `SocketBlockedError` (test failed as required) | ✓ PASS |
| Governance rot-guard | `uv run pytest tests/test_governance.py … -q` | 38 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| --- | --- | --- | --- |
| FOUND-01 | 02-01 | ✓ SATISFIED | 5 packages, independently versioned |
| FOUND-02 | 02-03 | ✓ SATISFIED | Wheel-independence job + neg control (ran) |
| FOUND-03 | 02-01, 02-02 | ✓ SATISFIED | `--disable-socket` default; no audio libs imported |
| FOUND-04 | 02-02 | ✓ SATISFIED | 3 contracts + biting negcontrols |
| FOUND-05 | 02-08 | ✓ SATISFIED | DECISIONS.md commitments + rot-guard |
| FOUND-06 | 02-08 | ✓ SATISFIED | CONTRIBUTING + ARCHITECTURE, tests runnable |
| FOUND-07 | 02-08 | ✓ SATISFIED | Apache-2.0, SPDX rot-guard, DCO workflow |
| CORE-01 | 02-04 | ✓ SATISFIED | Typed schema rejects bad values (neg control) |
| CORE-02 | 02-04 | ✓ SATISFIED | Atomic write survives injected crash |
| CORE-03 | 02-04 | ✓ SATISFIED | Stale revision → ConflictError, file untouched |
| CORE-04 | 02-05 | ✓ SATISFIED | Fernet+Scrypt pyca-only; not in YAML/logs/bytes; wrong passphrase fails |
| CORE-05 | 02-06 | ✓ SATISFIED | Endpoint interface + LAN classification + non-LAN neg control |
| CORE-06 | 02-04 | ✓ SATISFIED | Reload tiers discoverable, all four + default |
| TRACE-01 | 02-07 | ✓ SATISFIED | WAL single-writer bounded queue, off hot path |
| TRACE-02 | 02-07 | ✓ SATISFIED | Schema records prompts/model/tool args+results/timings/tokens |
| TRACE-03 | 02-07 | ✓ SATISFIED | `time_to_first_audio` first-class REAL column |
| TRACE-04 | 02-09 | ✓ SATISFIED | Fake-TTS gate: accuracy+overhead+budget, cold, neg control |
| TRACE-05 | 02-07 | ✓ SATISFIED | Runtime no-egress (disable-socket) + static no-network contract |
| PRIV-01 | 02-05, 02-08 | ✓ SATISFIED | No accounts; headless/offline store; DECISIONS commitment |
| PRIV-02 | 02-05, 02-08 | ✓ SATISFIED | No telemetry; no-network-client contract; DECISIONS commitment |

All 20 phase requirement IDs are claimed by a plan and satisfied. No orphaned requirements.

### Config-System Negative Controls (SC#3 detail)

| Guard | Negative control | Result |
| --- | --- | --- |
| CORE-01 validate-on-read | `tts_volume=99.0` / `temperature="not-a-number"` | `ValidationError` raised |
| CORE-02 atomic write | monkeypatch `os.replace` to raise mid-write | original `ORIGINAL` intact, no `.cfg.*` leftover |
| CORE-03 revision conflict | on-disk rev 5, writer submits expected 3 | `ConflictError`; on-disk still rev 5 / default persona |
| CORE-04 wrong passphrase | reopen store with wrong passphrase | `InvalidPassphraseError` (not silent garbage) |
| CORE-04 not-in-bytes | grep secret in encrypted file bytes | absent; passphrase also absent (only salt at rest) |
| CORE-04 not-in-logs | consume secret, log the operation | value absent from all captured records/args |
| CORE-04 not-in-YAML | serialize `AppConfig` | secret value absent from rendered YAML |

### Secret-Store Crypto Provenance (CORE-04 / D-02)

- Crypto is **pyca `cryptography` only**: `Fernet` (AES-128-CBC + HMAC-SHA256) + `Scrypt` KDF. No `hashlib` key-stretching, no bespoke cipher wiring. `__repr__`/`__str__` scrubbed; `list_keys` returns names only; file created `0600`.
- **Passphrase-at-boot decision recorded** in `DECISIONS.md` §"Master-key provisioning — passphrase-at-boot" (key never at rest, only salt persisted; flagged tradeoff that unattended headless restart needs the passphrase re-supplied → Phase 9 owns boot-time delivery). Confirmed present.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `packages/paaf-trace/src/paaf_trace/_testing/fake_tts.py` | 55 | comment "placeholder PCM-ish payload" | ℹ️ Info | Benign — a test-payload comment, not a functional stub; contents are irrelevant to a timing gate |

No `TBD`/`FIXME`/`XXX` debt markers in any phase-modified file. No unwired stubs. Skeleton packages (`paaf-voice`, `paaf-session`, `paaf-llm`) are intentionally minimal importable stubs per D-05 so the import-linter contracts are real.

### Human Verification Required

None. This phase delivers CI/code infrastructure that is fully verifiable programmatically; every contract, gate, and negative control was executed during verification. No visual, real-time, or external-service behavior is involved.

### Gaps Summary

No gaps. All six Success Criteria are achieved with genuinely-biting negative controls, confirmed by executing (not reading) the guards:

- Import-linter contracts are KEPT on the real tree and each goes RED on a deliberate violation; the `--disable-socket` offline posture itself was proven to block AF_INET.
- The `paaf-llm` wheel installs standalone with `paaf_voice`/`paaf_core` provably absent.
- Config validation, atomic write (crash-injected), revision-conflict, and the encrypted (pyca-only) secret store all reject the bad path, and the secret is absent from YAML, logs, and ciphertext-at-rest.
- Endpoint declaration + no-DNS LAN classification, and reload-tier discovery, are complete with a non-LAN negative control.
- The trace store is WAL single-writer off the hot path, records the full TRACE-02 set, has `time_to_first_audio` as a first-class column, and the fake-TTS TTFA gate defends measurement accuracy with a negative control that a budget-only gate would miss.
- Governance docs, Apache-2.0 + SPDX rot-guard, and DCO are enforced by CI, with the anti-feature list, no-accounts/no-telemetry-ever, skills-security posture, and injection-defense constraint written publicly.

One informational note (not a gap): ROADMAP labels the phase `mode: mvp` while the goal is a non-User-Story infrastructure outcome. Per 02-CONTEXT.md the six Success Criteria are the designated contract, so verification proceeded goal-backward against those SCs rather than MVP user-flow coverage.

---

_Verified: 2026-07-25T18:55:05Z_
_Verifier: Claude (gsd-verifier)_
