---
phase: 02-foundation
plan: 05
subsystem: secrets
tags: [secrets, cryptography, fernet, scrypt, kdf, core-04, priv-01, priv-02, passphrase-at-boot]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "paaf-core package with cryptography dep declared (Plan 01); AppConfig schema (Plan 04); captured_logs + --disable-socket test baseline (Plan 01)"
provides:
  - "SecretStore Protocol (set/get/delete/list_keys — names only) as the durable D-04 pluggable contract"
  - "EncryptedFileSecretStore: Fernet payload + scrypt KDF, master key derived from a passphrase at unlock (passphrase-at-boot); only a per-store salt is at rest"
  - "derive_key(passphrase, salt) helper (scrypt n=2**14,r=8,p=1, urlsafe-b64) reusable by future backends"
  - "CORE-04 negative controls: secret value proven absent from serialized YAML and from logs; wrong-passphrase raises; offline/headless under --disable-socket"
  - "DECISION for Plan 08 DECISIONS.md: master-key provisioning source = passphrase-at-boot (with the unattended-restart tradeoff flagged)"
affects: [02-08 decisions-record, 09-linux-service boot-time passphrase delivery (APP-*)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "audited crypto only (pyca cryptography Fernet + scrypt) — no hand-rolled cipher, no hashlib key stretching (D-02)"
    - "secret value never modeled in the Pydantic config tree; store is a separate encrypted file (coordinated with Plan 04)"
    - "no __repr__/__str__ that emits values — a store cannot be accidentally serialized into a log line"
    - "on-disk envelope {salt(plaintext b64), blob(Fernet token)} written via os.open(...0o600) then chmod 0600"

key-files:
  created:
    - packages/paaf-core/src/paaf_core/secrets/__init__.py
    - packages/paaf-core/src/paaf_core/secrets/interface.py
    - packages/paaf-core/src/paaf_core/secrets/fernet_backend.py
    - packages/paaf-core/tests/test_secret_store.py
  modified: []

key-decisions:
  - "Master-key provisioning source = passphrase-at-boot (developer decision at the plan checkpoint) — the strongest option; the master key is never at rest on disk. Fernet key is derived from a caller-supplied passphrase via scrypt at unlock, over a persisted per-store salt (salt at rest is fine, passphrase/key is not)."
  - "TRADEOFF FLAGGED: passphrase-at-boot BREAKS unattended restart on a headless box — every service (re)start needs the passphrase supplied by an operator or an external secrets manager. Phase 9 (Linux service, APP-*) must design boot-time passphrase delivery. The SecretStore interface keeps key-file-0600 / systemd-credential addable later with no interface change."
  - "Store persists an encrypted {} envelope on first construction so the salt is fixed and a wrong passphrase is detectable on the very next open, even before any secret is set."
  - "InvalidPassphraseError wraps Fernet's InvalidToken so a bad unlock fails loudly (never silent garbage) with a domain-level exception."

patterns-established:
  - "Pluggable SecretStore behind a runtime_checkable Protocol; Fernet file backend is v1, pyrage/age documented as the swappable alternative"
  - "Negative-control tests that prove absence (value not in YAML, not in logs, wrong-passphrase raises) rather than only asserting the happy path"

requirements-completed: [CORE-04, PRIV-01, PRIV-02]

coverage:
  - id: D1
    description: "Secrets round-trip through the Fernet backend; plaintext absent from the encrypted file; list_keys exposes names only; 0600 file"
    requirement: "CORE-04"
    verification:
      - kind: unit
        ref: "uv run pytest packages/paaf-core/tests/test_secret_store.py -q --disable-socket (16 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Secret value absent from serialized AppConfig YAML (not-in-YAML negative control)"
    requirement: "CORE-04"
    verification:
      - kind: unit
        ref: "test_secret_value_absent_from_serialized_config_yaml"
        status: pass
    human_judgment: false
  - id: D3
    description: "Secret value absent from captured_logs after a consume-and-log path (not-in-logs negative control)"
    requirement: "CORE-04"
    verification:
      - kind: unit
        ref: "test_secret_value_absent_from_logs_after_consume"
        status: pass
    human_judgment: false
  - id: D4
    description: "Store works headless/offline with no account or cloud; wrong passphrase fails loudly"
    requirement: "PRIV-01, PRIV-02"
    verification:
      - kind: unit
        ref: "test_offline_headless_round_trip_needs_no_network + test_wrong_passphrase_raises_not_silent (under --disable-socket)"
        status: pass
    human_judgment: false

# Metrics
duration: 3min
completed: 2026-07-25
status: complete
---

# Phase 02 Plan 05: Encrypted Secret Store Summary

**A pluggable `SecretStore` with a Fernet + scrypt encrypted-file backend whose master key is derived from a passphrase at unlock (passphrase-at-boot) — secrets round-trip, are proven absent from the YAML tree and the logs, and the store runs headless and offline with no account or cloud.**

## Performance

- **Duration:** ~3 min (after the decision checkpoint was resolved)
- **Completed:** 2026-07-25
- **Tasks:** 2 (plus 1 decision checkpoint)
- **Files created:** 4 (0 modified)

## Decision Checkpoint Outcome

**Master-key provisioning source = `passphrase-at-boot`** (developer decision, surfaced to the human by the orchestrator — not self-decided).

Rationale recorded for Plan 08 / DECISIONS.md: the developer chose the strongest option — the master key is never at rest on disk. The Fernet key is derived from a caller-supplied passphrase via scrypt (the already-chosen KDF, D-02) at unlock time, over a persisted per-store salt. The salt at rest is fine; the passphrase and derived key are never written. For Phase 2 the `SecretStore` just accepts the passphrase at construction/unlock; actual boot-time delivery (env var / stdin / prompt / secrets manager) is Phase 9's service concern.

### ⚠️ Known Tradeoff (flag for DECISIONS.md and Phase 9)

**`passphrase-at-boot` BREAKS unattended restart on a headless box.** Every service (re)start needs the passphrase supplied by an operator or an external secrets manager. **Phase 9 (the Linux service, APP-*) must design boot-time passphrase delivery around this.** The `SecretStore` interface keeps the `key-file-0600` and `systemd-credential` options addable later **without an interface change**, so the tradeoff is reversible at the backend level, not the contract level.

## Accomplishments

- `paaf_core/secrets/interface.py` — `SecretStore` `runtime_checkable` Protocol: `set`, `get`, `delete`, `list_keys` (names only). The durable D-04 contract; the value is never reachable through the listing API.
- `paaf_core/secrets/fernet_backend.py` — `derive_key(passphrase, salt)` (scrypt n=2**14, r=8, p=1, length 32, urlsafe-b64) and `EncryptedFileSecretStore` (JSON envelope `{salt, Fernet-token}`, file created `0600`, key held only in memory). `InvalidPassphraseError` on a bad/tampered unlock.
- `paaf_core/secrets/__init__.py` — submodule exports (does not touch top-level `paaf_core/__init__.py`).
- `tests/test_secret_store.py` — 16 tests: 12 round-trip/derive/leak-guard (Task 1) + 4 CORE-04 negative controls (Task 2).

## Task Commits

Each task committed atomically (Task 1 as TDD RED→GREEN):

1. **Task 1 RED — failing secret-store tests** — `ad0e6bc` (test)
2. **Task 1 GREEN — SecretStore interface + Fernet backend (CORE-04)** — `960edbb` (feat)
3. **Task 2 — CORE-04 negative controls (not-in-YAML / not-in-logs / offline / wrong-passphrase)** — `cd1112c` (test)

## Files Created/Modified

- `packages/paaf-core/src/paaf_core/secrets/interface.py` — `SecretStore` Protocol
- `packages/paaf-core/src/paaf_core/secrets/fernet_backend.py` — `derive_key` + `EncryptedFileSecretStore` + `InvalidPassphraseError`
- `packages/paaf-core/src/paaf_core/secrets/__init__.py` — exports
- `packages/paaf-core/tests/test_secret_store.py` — 16 tests

## Verification

- `uv run pytest packages/paaf-core/tests/test_secret_store.py -q --disable-socket` → **16 passed**
- `uv run pytest packages/paaf-core -q --disable-socket` → **33 passed** (no regressions)
- Crypto acceptance greps on `fernet_backend.py`: `Fernet` ≥1, `Scrypt` ≥1, `import hashlib` = 0, manual `Cipher(` = 0 — audited crypto only (D-02).
- Secret value proven absent from: encrypted file bytes, serialized `AppConfig` YAML, and all `captured_logs` records.

## Deviations from Plan

None — plan executed as written. The store persists an encrypted empty envelope on first construction (so a wrong passphrase is detectable on the next open even before the first `set`); this is an implementation detail within the plan's stated behavior, not a scope change.

## Threat Model Coverage

| Threat ID | Mitigation as built |
|-----------|---------------------|
| T-02-11 (secret in YAML/logs) | separate encrypted store; not-in-YAML + not-in-logs negative controls (tests) |
| T-02-12 (hand-rolled crypto) | pyca `cryptography` Fernet + scrypt only; grep-verified no `hashlib`/manual cipher |
| T-02-13 (master key at rest) | passphrase-at-boot — key derived at unlock, never persisted; only salt at rest |
| T-02-14 (account/cloud/telemetry) | full suite green under `--disable-socket`; no network/account/cloud path |
| T-02-SC (cryptography install) | dep declared+resolved in Plan 01; pyca cryptography is Approved in the RESEARCH audit |

## User Setup Required

None for Phase 2. Forward reference: from Phase 9 onward, running the assistant with a real secret store requires supplying the master **passphrase at service start** (env var / stdin / prompt / secrets manager) — unattended headless restart is not possible without it by design (see the Known Tradeoff above).

## Next Phase Readiness

- SC#3 secrets half is complete: API keys live in a separate encrypted store the YAML and logs never contain, on audited crypto, headless and offline — each absence proven by a negative control.
- Plan 08 can cite `passphrase-at-boot` (and its tradeoff) in DECISIONS.md.
- The `SecretStore` interface is the extension point for `key-file-0600` / `systemd-credential` backends without a caller-facing change.

## Self-Check: PASSED

- All 4 created files verified present on disk.
- All three task commits (`ad0e6bc`, `960edbb`, `cd1112c`) verified in git log.

---
*Phase: 02-foundation*
*Completed: 2026-07-25*
