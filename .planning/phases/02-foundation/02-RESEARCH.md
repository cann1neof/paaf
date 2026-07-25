# Phase 2: Foundation - Research

**Researched:** 2026-07-25
**Domain:** Python monorepo build hygiene (uv/hatchling), CI-enforced import boundaries (import-linter), typed config + optimistic-concurrency + atomic writes (Pydantic), audited-crypto secret store (pyca `cryptography` / `pyrage`), async SQLite trace store (aiosqlite/WAL), and a fake-TTS latency regression gate — all under a no-hardware/no-network CI matrix.
**Confidence:** HIGH on stack and patterns; MEDIUM on the crypto-library selection (a genuine two-way decision the user should ratify — see Assumptions Log).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
**Secret store (CORE-04):**
- **D-01:** API keys go in a **separate encrypted store**, never in the YAML tree, never logged, write-only over the API.
- **D-02:** The crypto MUST come from an **established, independently-audited open-source library. No hand-rolled crypto, no bespoke cipher.** Trustworthiness/audit history is the primary selection criterion.
- **D-03:** Must work **headless and offline-verifiable** (headless Linux ship target). Down-weights D-Bus/OS-keyring approaches.
- **D-04:** Sits behind a pluggable `SecretStore` interface (OS-keyring backend addable later). Encrypted-file backend is the default/first implementation. Reject anything requiring an account or cloud KMS (PRIV-01/02).

**Monorepo scaffold scope (FOUND-01..04):**
- **D-05:** Scaffold **all five framework packages as importable skeletons** (each versioned, with a smoke test); real Phase-2 implementation only in **`paaf-core`** (config) and **`paaf-trace`** (trace store). `paaf-llm`, `paaf-voice`, `paaf-session` are minimal importable stubs.
- **D-06:** Rationale is load-bearing: SC#1 and the import-linter contracts cannot be tested unless those packages exist.
- **D-07:** The two apps (`app-embedded`, `app-desktop`) are **NOT** scaffolded in Phase 2.

**TTFA regression guard (TRACE-03/04):**
- **D-08:** CI guard uses a **fake TTS** and asserts **both**: (a) accounting accuracy + overhead (fake emits first audio after a fixed injected delay; recorded `time_to_first_audio` must match within tight tolerance while overhead stays under a small ceiling); AND (b) a fixed budget ceiling on the measured value.
- **D-09:** The accuracy half is load-bearing (proves the *measurement* is correct with no real engine). Phase-1 evidence binds: real TTFA is engine/sentence-dependent (6.27 s on mps, ~10× tail); the fixed budget is a **guardrail against measurement/overhead regression, explicitly NOT a shipped-latency claim.** Runs cold, no audio hardware, no network.

### Claude's Discretion
- **App license (FOUND-07):** Lean, not locked — framework is Apache-2.0 (required); apps default to **Apache-2.0 for v1**; AGPL is recorded as an open governance question in DECISIONS.md, not chosen. Do not treat AGPL as chosen.
- Import-linter contract shapes, config schema library (Pydantic per stack), SQLite pragmas/queue design, and CI matrix details are implementation choices left to research + planning, constrained by requirements and Phase-1 decisions.

### Deferred Ideas (OUT OF SCOPE)
- **AGPL licensing for the apps** — open governance question in DECISIONS.md; decide deliberately later.
- **OS-keyring secret backend** — allowed later by the `SecretStore` interface; not implemented in Phase 2.
- **App scaffolding** (`app-embedded`, `app-desktop`) — deferred to their own phases.
- **SOPS / secrets-in-git** — only relevant if config-with-secrets-in-git ever becomes a goal; out of scope now.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | uv workspace monorepo, five framework packages + two apps, each independently versioned | Standard Stack (uv/hatchling); Project Structure; Pattern (workspace) — apps deferred per D-07 |
| FOUND-02 | `paaf-llm` independently `pip install`-able without voice/audio deps | Pitfall 2 (clean-venv wheel job); CI shape `wheel-independence`; `src/` layout |
| FOUND-03 | CI runs full suite with no audio hardware and no network | CI matrix; `pytest-socket --disable-socket`; no audio import in graph |
| FOUND-04 | import-linter forbidden contracts fail CI (voice↔llm, langchain outside adapter) | Pattern 7 (independence + forbidden contracts); Pitfall 1 (negative controls) |
| FOUND-05 | DECISIONS.md records anti-feature list, skills-security posture, injection-defense constraint | Governance docs (repo root); Security Domain (permission-model-as-only-injection-defense) |
| FOUND-06 | CONTRIBUTING.md + architecture doc for outsiders | Project Structure (ARCHITECTURE.md, CONTRIBUTING.md) |
| FOUND-07 | Apache-2.0 framework, license headers, DCO, conventional commits, semver | Governance docs; Open Question 3 (app license lean Apache-2.0) |
| CORE-01 | One YAML tree, validated against typed schema on every read/write | Pydantic v2; Pattern 5; ruamel.yaml/PyYAML choice |
| CORE-02 | Atomic config writes (temp, fsync, rename) | Pattern 1 (atomic write) |
| CORE-03 | Monotonic revision; concurrent edits rejected as conflict | Pattern 2 (optimistic concurrency + filelock); Pitfall 1 |
| CORE-04 | API keys in separate encrypted store, write-only, never in YAML/logs | Pattern 3 (SecretStore + Fernet); Assumptions A1/A2; Security V6/V7 |
| CORE-05 | Common network-endpoint declaration interface | Pattern 4 (NetworkComponent interface + registry) |
| CORE-06 | Config keys classified into reload tiers, discoverable | Pattern 5 (reload-tier metadata) |
| TRACE-01 | SQLite WAL, single writer, bounded queue, off hot path | Pattern 6 (single-writer queue); Pitfall 5 |
| TRACE-02 | Record prompts, model, tool calls args+results, timings, tokens | Pattern 6 schema; TRACE-02 test map |
| TRACE-03 | `time_to_first_audio` is a first-class recorded metric | Pattern 6 (TTFA column); test map |
| TRACE-04 | TTFA asserted in CI vs regression threshold, cold, fake TTS | Pitfall 3 (accuracy + overhead + budget); D-08/D-09; CI `ttfa-gate` |
| TRACE-05 | Nothing in trace store leaves the device | Security Domain; import-linter (no net client) + `--disable-socket` |
| PRIV-01 | No accounts, anywhere | SecretStore rejects account/cloud (D-04); Security Domain |
| PRIV-02 | No telemetry, ever | `--disable-socket` negative control; Security Domain |

</phase_requirements>

## Summary

Phase 2 is a pure build-and-scaffold phase: no runtime product behaviour ships, only the *scaffolding that makes later architectural rules un-violable*. Everything here is standard, well-trodden Python packaging and library work — there is very little novel engineering risk. The risk that exists is in **getting the guards to actually fail on bad input** (Phase 1's negative-control lesson), not in the happy path.

The five technical pillars map cleanly onto existing, actively-maintained, audited libraries already named in `CLAUDE.md`: **uv workspace + hatchling** for the monorepo, **import-linter** for CI-enforced import boundaries, **Pydantic v2** for the typed config schema, **pyca `cryptography` (Fernet + scrypt)** for the encrypted secret store, and **aiosqlite (raw SQL, WAL)** for the trace store. The only selection genuinely delegated to research — the crypto library — resolves to a close call between pyca `cryptography` and `pyrage` (age); this document recommends **pyca `cryptography`** on the D-02 "audit history is the primary criterion" axis, with `pyrage`/age as a fully-viable runner-up, and flags it for user ratification.

The load-bearing subtlety across all six Success Criteria is **negative controls**: an import-linter contract, a stale-revision rejection, a TTFA accuracy assertion, and a no-network guard each need a companion test proving the guard *fails* on the bad input. Phase 1 twice caught vacuously-passing checks; the same discipline is the single most important thing the planner must bake into every Phase-2 verification step.

**Primary recommendation:** Scaffold a uv workspace with five hatchling-built packages (real impl only in `paaf-core` + `paaf-trace`), enforce boundaries with import-linter `independence`/`forbidden` contracts *plus a deliberate-violation test that must go red*, build the config system on Pydantic v2 with `os.replace`-based atomic writes and an optimistic monotonic-revision guard, store secrets via a `SecretStore` interface backed by pyca `cryptography` Fernet, and run a fake-TTS TTFA gate that asserts measurement *accuracy* (not just a ceiling) on a deterministic clock. Everything runs under `pytest-socket --disable-socket` with no audio deps in the import graph.

## Architectural Responsibility Map

> This is a single-process Python library monorepo, not a multi-tier web app. "Tier" here = the owning **package/layer** the capability belongs to. The map's job is to stop capabilities landing in the wrong package and quietly creating the coupling that FOUND-04 exists to forbid.

| Capability | Primary Tier (package) | Secondary Tier | Rationale |
|------------|------------------------|----------------|-----------|
| Typed config schema, validation, atomic write, revision guard (CORE-01/02/03) | `paaf-core` | — | Config is foundational; every other package reads it, nothing about it is voice/llm specific |
| Encrypted secret store + `SecretStore` interface (CORE-04) | `paaf-core` | — | Secrets are cross-cutting; the interface must not depend on llm/voice |
| Network-endpoint declaration interface (CORE-05) | `paaf-core` | consumed by all packages | The common interface lives in core; each component *implements* it. Enforcement daemon is Phase 9 (APP-08) |
| Reload-tier classification + discovery (CORE-06) | `paaf-core` | — | Tier metadata rides on the config schema, which core owns |
| SQLite trace store, WAL, bounded-queue writer (TRACE-01/02/05) | `paaf-trace` | depends on `paaf-core` for config only | Trace is its own package so llm/voice can emit without a heavy dep; must never leave device |
| `time_to_first_audio` first-class column + CI gate (TRACE-03/04) | `paaf-trace` | CI job | The metric is a trace-schema concern; the gate is CI tooling using a fake TTS |
| Import-boundary contracts (FOUND-04) | repo-root tooling (import-linter) | CI | Not a package; a lint contract over the whole graph |
| uv workspace + wheel independence (FOUND-01/02) | repo-root `pyproject.toml` + per-package `pyproject.toml` | CI | Build-system concern; the clean-venv wheel job is CI |
| Governance docs, license headers, DCO (FOUND-05/06/07) | repo root | — | Repository-level artifacts, not code |
| `paaf-llm`, `paaf-voice`, `paaf-session` | importable **stubs only** | — | Exist so the import contracts are real (D-05/D-06); no Phase-2 logic |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **uv** | 0.11.31 (installed, verified locally) | Workspace/venv/lockfile mgmt | Project standard (CLAUDE.md); the 2026 default; native `[tool.uv.workspace]` + `--package` builds `[VERIFIED: local uv --version]` |
| **hatchling** | 1.31.0 (2026-07-08) | Build backend for every package | PyPA-official, uv-recommended, minimal-config `pyproject`-native backend `[VERIFIED: PyPI JSON]` |
| **import-linter** | 2.13 (2026-07-03) | CI-enforced import contracts (FOUND-04) | The de-facto Python import-boundary tool; `forbidden`/`independence`/`layers` contracts in `pyproject.toml` `[VERIFIED: PyPI JSON + official docs]` |
| **Pydantic** | 2.13.4 (2026-05-06) | Typed config schema + validation (CORE-01) | Project standard; validate-on-read/write, JSON-schema export for the desktop app, field-level metadata for reload tiers `[VERIFIED: PyPI JSON]` |
| **pyca `cryptography`** | 49.0.0 (2026-06-12) | Encrypted secret store (CORE-04) — **recommended** | Most-audited Python crypto lib (~1.4B downloads/mo); Fernet = safe AEAD recipe, scrypt/Argon2 KDFs available; pure local, no account/cloud `[VERIFIED: PyPI JSON + pypistats]` |
| **aiosqlite** | 0.22.1 (2025-12-23) | Async SQLite trace store (TRACE-01) | Project standard; thin async wrapper over stdlib `sqlite3`, single-writer-task friendly, no ORM `[VERIFIED: PyPI JSON]` |
| **pytest** + **pytest-asyncio** | 9.1.1 / 1.4.0 (Phase-1 baseline) | Test runner | Established in Phase 1; async support for queue/aiosqlite tests `[VERIFIED: STATE.md Phase-1 baseline]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ruamel.yaml** | 0.19.1 (2026-01-02) | YAML round-trip read/write of the config tree (CORE-01) | Use when the desktop app writes config back and comments/key-order must survive. If comment preservation is not required, stdlib-adjacent `PyYAML safe_load` is simpler `[VERIFIED: PyPI JSON]` |
| **filelock** | 3.32.0 (2026-07-21) | Cross-process lock around the config read-modify-write critical section (CORE-03) | Wrap the load→check-revision→write sequence so two writers cannot interleave; complements (does not replace) the revision guard `[VERIFIED: PyPI JSON]` |
| **pytest-socket** | latest | Enforce "no network" in CI (FOUND-03) | `--disable-socket` fails any test that opens a socket; the negative control for PRIV-01/02 offline posture `[ASSUMED — verify on registry before install]` |
| **ruff** | latest | Lint/format + optional `banned-api` for `langchain` confinement | Project standard; a *second* line of defense on the langchain rule, but import-linter is the SC#1 authority `[CITED: CLAUDE.md]` |
| **pyrage** | 1.3.0 (2025-06-14) | **Alternative** secret-store crypto (age format) | If the team prefers the modern age format / multi-recipient / future secrets-in-git story over max audit history. See Alternatives + Assumptions Log `[VERIFIED: PyPI JSON; name discovered via CONTEXT+websearch]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyca `cryptography` (Fernet) | **`pyrage`** (Python bindings to Rust `rage`, the age format) | age is a modern, well-regarded, minimal format (X25519 + ChaCha20-Poly1305 + scrypt passphrase) by Filippo Valsorda; `pyrage` is by William Woodruff / Trail of Bits (MIT). Pros: complete audited *format* with multi-recipient + a natural path to secrets-in-git later (SOPS-adjacent). Cons vs `cryptography`: far smaller audit/review surface for the *binding* specifically (~158k dl/mo vs ~1.4B), a Rust-extension wheel (build/availability consideration, though Linux+macOS wheels ship), and it does not also give you general KDF primitives. **D-02 makes "audit history" the primary criterion → `cryptography` wins on that axis; `pyrage` wins on format modernity.** |
| pyca `cryptography` (Fernet) | **SOPS / age-in-git** | Explicitly out of scope (CONTEXT deferred): only relevant if config-with-secrets-in-git becomes a goal. Do not adopt now. |
| OS keyring | encrypted-file backend | D-03/D-04: keyring/D-Bus is awkward headless; encrypted-file is the default backend, keyring is a *later* pluggable backend behind `SecretStore` |
| ruamel.yaml | PyYAML `safe_load` | PyYAML is lighter but loses comments/formatting on write-back; acceptable if the API fully owns the file and re-emits from the Pydantic model |
| import-linter for langchain rule | ruff `flake8-tidy-imports.banned-api` | Both work; SC#1 says the violation must fail **on import-linter**, so import-linter is authoritative and ruff is a bonus (CLAUDE.md mentions ruff banned-api) |

**Installation:**
```bash
# workspace tooling (uv already installed: 0.11.31)
# runtime deps declared per-package pyproject; representative set:
uv add --package paaf-core   pydantic ruamel.yaml cryptography filelock
uv add --package paaf-trace  aiosqlite
# dev/CI tooling at workspace root:
uv add --dev import-linter pytest pytest-asyncio pytest-socket ruff mypy
```

**Version verification:** All versions above were read live from the PyPI JSON API on 2026-07-25 (`https://pypi.org/pypi/<pkg>/json`), except uv (local `uv --version`) and pytest/pytest-asyncio (Phase-1 baseline in STATE.md). `pip index versions` returned nothing in the sandbox (network-restricted); the PyPI JSON API and pypistats did respond and are the source of the dates/versions here.

## Package Legitimacy Audit

> The `gsd-tools package-legitimacy check` seam flagged every package `SUS` **solely** with reason `unknown-downloads` (and `no-repository`/`too-new` where the seam's registry mirror lagged) because it could not fetch download stats in this sandboxed network. That is a tooling artifact, not a real signal. Each package below was cross-verified independently via the PyPI JSON API, pypistats, and known-maintainer identity. None is a hallucination; all are long-established.

| Package | Registry | Age / Published | Downloads (indep.) | Source Repo | Verdict | Disposition |
|---------|----------|-----------------|--------------------|-------------|---------|-------------|
| cryptography | PyPI | 49.0.0, 2026-06-12 | ~1.4B/mo | github.com/pyca/cryptography | OK (seam: SUS=unknown-downloads only) | Approved |
| pydantic | PyPI | 2.13.4, 2026-05-06 | very high | github.com/pydantic/pydantic | OK | Approved |
| hatchling | PyPI | 1.31.0, 2026-07-08 | very high (PyPA) | github.com/pypa/hatch | OK | Approved |
| import-linter | PyPI | 2.13, 2026-07-03 | ~12M/mo | github.com/seddonym/import-linter | OK | Approved |
| aiosqlite | PyPI | 0.22.1, 2025-12-23 | very high | github.com/omnilib/aiosqlite | OK | Approved |
| ruamel.yaml | PyPI | 0.19.1, 2026-01-02 | very high | sourcehut/PyPI (MIT) | OK | Approved |
| filelock | PyPI | 3.32.0, 2026-07-21 | very high | github.com/tox-dev/py-filelock | OK | Approved |
| pyrage | PyPI | 1.3.0, 2025-06-14 | ~159k/mo | github.com/woodruffw/pyrage (Trail of Bits author, MIT) | OK | Approved (alternative) |
| pytest-socket | PyPI | latest | high | github.com/miketheman/pytest-socket | OK | Verify version at install |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none genuinely suspicious. The seam's blanket `SUS` here is an `unknown-downloads` false positive from sandbox network limits; the planner does **not** need a `checkpoint:human-verify` for the established packages. **Do** confirm the exact `pytest-socket` version against the registry at install time (it was not version-pinned this session).

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────────┐
   git commit (signed-off)│  Repo root: pyproject.toml (uv workspace)    │
   Apache-2.0 + DCO       │  LICENSE, DECISIONS.md, CONTRIBUTING.md,     │
        │                 │  ARCHITECTURE.md, .importlinter contracts    │
        ▼                 └───────────────┬─────────────────────────────┘
   ┌─────────┐                            │ resolves members
   │   CI    │                            ▼
   │ matrix  │      ┌──────────────┬──────────────┬─────────────┬──────────────┐
   │(no HW,  │      │  paaf-core   │  paaf-trace  │  paaf-llm   │  paaf-voice  │  paaf-session
   │ no net) │      │  (REAL)      │  (REAL)      │  (stub)     │  (stub)      │  (stub)
   └────┬────┘      └──────┬───────┴──────┬───────┴─────────────┴──────────────┘
        │                  │              │
        │  ┌───────────────┘              └──────────────┐
        │  ▼                                             ▼
        │ CONFIG SUBSYSTEM (paaf-core)          TRACE SUBSYSTEM (paaf-trace)
        │ ┌─────────────────────────────┐       ┌────────────────────────────────┐
        │ │ YAML file ──▶ Pydantic model │       │ producers (llm/voice/session)  │
        │ │   ▲            │ validate     │       │        │ put_nowait (never block)│
        │ │   │ os.replace │ revision++   │       │        ▼                        │
        │ │ atomic write◀──┤ check rev    │       │  bounded asyncio.Queue          │
        │ │ (tmp+fsync+    │ (conflict?)  │       │        │                        │
        │ │  rename+dirfsync)             │       │        ▼ single writer task     │
        │ │ SecretStore ──▶ encrypted     │       │  aiosqlite conn (WAL,           │
        │ │  (Fernet)      secrets file   │       │  synchronous=NORMAL)            │
        │ │ EndpointDecl ──▶ registry     │       │        │                        │
        │ │ ReloadTier  ──▶ per-key map   │       │        ▼ runs / tool_calls      │
        │ └─────────────────────────────┘       │  time_to_first_audio REAL col   │
        │                                        └────────────────┬───────────────┘
        │                                                         │
        └── CI gate: fake-TTS injects fixed delay ───▶ assert recorded TTFA ≈ delay
            (accuracy) AND overhead < ceiling AND TTFA < budget    (never touches disk audio)
```

Data flow to trace for the primary "config edit" use case: API/caller → build new Pydantic model → `SecretStore.set()` for any secret fields (never into YAML) → acquire filelock → reload current revision → if `expected_revision != current` raise `ConflictError` → else `revision += 1`, serialize, atomic write, release lock. The trace store's TTFA path is exercised only by the fake-TTS CI gate in this phase.

### Recommended Project Structure
```
paaf/                              # repo root
├── pyproject.toml                 # [tool.uv.workspace] members; dev deps; [tool.importlinter]
├── uv.lock                        # single lockfile for the whole workspace
├── LICENSE                        # Apache-2.0
├── DECISIONS.md                   # exists (Phase 1) — extend with anti-features/injection posture
├── CONTRIBUTING.md                # DCO sign-off, conventional commits, how to run tests
├── ARCHITECTURE.md                # the map an outsider needs (FOUND-06)
├── .importlinter                  # OR contracts under [tool.importlinter] in pyproject
├── packages/
│   ├── paaf-core/
│   │   ├── pyproject.toml         # real deps: pydantic, ruamel.yaml, cryptography, filelock
│   │   ├── src/paaf_core/
│   │   │   ├── config/            # schema.py, store.py (atomic+revision), reload_tiers.py
│   │   │   ├── secrets/           # interface.py (SecretStore), fernet_backend.py
│   │   │   └── net/               # endpoint.py (declaration interface + registry)
│   │   └── tests/
│   ├── paaf-trace/
│   │   ├── pyproject.toml         # real deps: aiosqlite  (+ paaf-core if needed)
│   │   ├── src/paaf_trace/        # schema.sql, store.py (queue+writer), metrics.py
│   │   └── tests/
│   ├── paaf-llm/                  # STUB: __init__.py (version), one smoke test
│   ├── paaf-voice/               # STUB
│   └── paaf-session/             # STUB
└── .github/workflows/ci.yml       # matrix: full suite (no HW/net) + clean-venv wheel job + TTFA gate
```
Use a `src/` layout per package so the clean-venv wheel test actually imports the *installed* package, not the source tree (this is what makes FOUND-02 real).

### Pattern 1: Atomic config write (CORE-02)
**What:** Never write in place. Write to a temp file in the *same directory*, fsync it, atomically rename over the target, then fsync the directory.
**When to use:** Every config persist.
**Example:**
```python
# Source: standard POSIX durable-rename pattern (os.replace is atomic same-filesystem)
import os, tempfile

def atomic_write_bytes(path: str, data: bytes) -> None:
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".cfg.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())          # durability of file contents
        os.replace(tmp, path)             # atomic swap; readers see old-or-new, never partial
        dfd = os.open(d, os.O_DIRECTORY)
        try:
            os.fsync(dfd)                 # durability of the rename itself
        finally:
            os.close(dfd)
    except Exception:
        try: os.unlink(tmp)
        finally: raise
```

### Pattern 2: Optimistic monotonic-revision write (CORE-03)
**What:** Config carries an integer `revision`. A write submits the `expected_revision` it read. If the on-disk revision has moved, reject with a conflict instead of overwriting.
**When to use:** Every config mutation, especially from the desktop app.
**Example:**
```python
# Source: standard optimistic-concurrency (compare-and-swap) pattern
from filelock import FileLock

class ConflictError(Exception): ...

def write_config(path, lock_path, new_model, expected_revision: int):
    with FileLock(lock_path):                      # serialize the read-modify-write
        current = load_config(path)                # validated Pydantic model
        if current.revision != expected_revision:  # negative control: this MUST raise on stale input
            raise ConflictError(
                f"stale write: expected {expected_revision}, on disk {current.revision}")
        new_model.revision = current.revision + 1  # monotonic
        atomic_write_bytes(path, serialize(new_model))
        return new_model.revision
```

### Pattern 3: SecretStore interface + Fernet backend (CORE-04)
**What:** A `Protocol`/ABC with `get`/`set`/`delete`/`list_keys`; secrets live in a separate encrypted file, never in the YAML, never logged, write-only over the (future) API.
**When to use:** Any API key or credential.
**Example:**
```python
# Source: pyca cryptography Fernet recipe + scrypt KDF (audited primitives)
from typing import Protocol
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

class SecretStore(Protocol):
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...      # used only where a secret is CONSUMED, never logged
    def delete(self, key: str) -> None: ...
    def list_keys(self) -> list[str]: ...           # names only, never values

def derive_key(passphrase: bytes, salt: bytes) -> bytes:
    import base64
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(passphrase))

# EncryptedFileSecretStore: keeps salt + Fernet-encrypted {key: value} blob on disk (0600).
# Master secret provisioned from an operator-supplied source (systemd credential / env / dev key file),
# NOT from the YAML. Offline + headless + no account/cloud (PRIV-01/02, D-03).
```
> **Key-provisioning is the real decision inside CORE-04**, and CORE-04 only requires *separate + encrypted + write-only-API + not-in-YAML + not-in-logs* — it does **not** mandate passphrase-at-boot. For a headless auto-restarting service, a `0600` key file (or a systemd credential / env var) is acceptable for v1; a passphrase-at-start mode is the stronger option. The `SecretStore` interface lets both coexist. Flag this for the planner as a checkpoint decision.

### Pattern 4: Network-endpoint declaration interface (CORE-05)
**What:** One common interface every network-touching component implements, so offline enforcement (Phase 9, APP-08) is architectural, not scattered `if offline:` checks.
**Example:**
```python
# Source: project requirement CORE-05 (interface designed here; enforcement daemon = Phase 9)
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    scheme: str
    def is_lan(self) -> bool: ...   # RFC1918 / loopback / .local classification

class NetworkComponent(Protocol):
    def declare_endpoints(self) -> list[Endpoint]: ...

# A registry collects declarations. Phase 2 ships the interface + registry + tests.
# Phase 9's APP-08 iterates the registry and refuses to start on any non-LAN endpoint.
```

### Pattern 5: Reload-tier metadata on config fields (CORE-06)
**What:** Each config key is classified hot / warm / cold / restart-only, and the tier is *discoverable* (a function returns `{key_path: tier}`).
**Example:**
```python
# Source: Pydantic v2 field metadata (json_schema_extra) — discoverable via model_fields
from enum import Enum
from pydantic import BaseModel, Field

class ReloadTier(str, Enum):
    HOT = "hot"; WARM = "warm"; COLD = "cold"; RESTART = "restart-only"

class VoiceConfig(BaseModel):
    tts_volume: float = Field(1.0, json_schema_extra={"reload_tier": ReloadTier.HOT})
    stt_model: str   = Field("large-v3-turbo", json_schema_extra={"reload_tier": ReloadTier.COLD})

def reload_tiers(model_cls) -> dict[str, ReloadTier]:
    # walk model_fields (recursively for nested models), read json_schema_extra["reload_tier"]
    ...
```

### Pattern 6: SQLite trace store — single writer behind a bounded queue (TRACE-01/05)
**What:** WAL mode, one writer task owning the aiosqlite connection, producers hand rows to a bounded `asyncio.Queue`. Off the hot path means producers **never block on audio** — use `put_nowait` and drop-with-counter on overflow rather than await.
**Example:**
```python
# Source: aiosqlite + asyncio single-writer pattern; raw SQL, no ORM (CLAUDE.md)
import asyncio, aiosqlite

PRAGMAS = ("PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;",
           "PRAGMA foreign_keys=ON;", "PRAGMA busy_timeout=5000;")

class TraceStore:
    def __init__(self, path, maxsize=1000):
        self._q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._path = path; self._dropped = 0

    def emit(self, event) -> None:          # called from hot path; MUST NOT await
        try: self._q.put_nowait(event)
        except asyncio.QueueFull: self._dropped += 1   # observable backpressure, never blocks audio

    async def _writer(self):
        async with aiosqlite.connect(self._path) as db:
            for p in PRAGMAS: await db.execute(p)
            await db.commit()
            while True:
                event = await self._q.get()
                await db.execute(*event.as_sql()); await db.commit()
```
> WAL + a single writer sidesteps SQLite's writer-lock contention; multiple readers (the desktop Logs page, later) proceed concurrently. `synchronous=NORMAL` is the standard WAL durability/throughput tradeoff.

### Pattern 7: import-linter contracts (FOUND-04)
**What:** Declare boundaries as data; CI fails on violation. Use `independence` for the mutual `paaf-voice ↔ paaf-llm` ban, and `forbidden` for `langchain` outside the adapter.
**Example:**
```toml
# Source: import-linter official docs (contract_types) — pyproject.toml form
[tool.importlinter]
root_packages = ["paaf_core", "paaf_trace", "paaf_llm", "paaf_voice", "paaf_session"]

[[tool.importlinter.contracts]]
name = "voice and llm are independent"
type = "independence"
modules = ["paaf_voice", "paaf_llm"]      # no imports in EITHER direction, even indirect

[[tool.importlinter.contracts]]
name = "langchain confined to the adapter"
type = "forbidden"
source_modules = ["paaf_core", "paaf_trace", "paaf_voice", "paaf_session", "paaf_llm"]
forbidden_modules = ["langchain", "langgraph", "langchain_core", "langchain_mcp_adapters"]
# the ONE allowed edge is whitelisted explicitly once the Phase-3 adapter exists, e.g.:
# ignore_imports = ["paaf_llm._engine.* -> langchain*"]
```
> In Phase 2, `paaf-llm` is a stub with **no** langchain import, so the forbidden contract can list all five packages with no exceptions and pass. SC#1 requires the *designated adapter package* to exist so the exception is real — create `paaf_llm/_engine/__init__.py` as the marked adapter subpackage now (empty), and record in a comment that Phase 3 adds the `ignore_imports` whitelist for exactly that subpackage. **Confirm the exact `ignore_imports` glob syntax against import-linter 2.13 docs when wiring the exception** (the whitelist path form is `importer -> imported`).

### Anti-Patterns to Avoid
- **A guard that cannot fail.** The single biggest Phase-2 risk (Phase-1 caught this twice). Every contract/rejection/threshold test needs a companion test that feeds the *bad* input and asserts red.
- **Writing config in place / `open(path,'w')`.** A crash mid-write corrupts config. Always temp+fsync+rename.
- **A `revision` guard without a lock.** Two processes can both read rev N and both write rev N+1. Wrap the read-modify-write in a filelock (Pattern 2).
- **Secrets reachable from the YAML model or logs.** Keep secret *values* out of the Pydantic config model entirely; store only key *references*. Never `log.info(config)` if it could contain a secret.
- **Awaiting the trace queue on the hot path.** `put_nowait` + drop-counter, never `await put()`, or audio stalls behind disk I/O.
- **An ORM for the trace store.** CLAUDE.md forbids it; it is an append-mostly event log — raw SQL + aiosqlite.
- **`pip install -e` making the wheel job pass falsely.** The clean-venv job must install the *built wheel* with no workspace on `sys.path`, or FOUND-02 rots undetected.
- **Wall-clock `sleep` in the TTFA accuracy test.** Flaky. Inject a controllable clock so the accuracy assertion is deterministic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Encrypting secrets | A custom cipher / XOR / raw AES wiring | pyca `cryptography` **Fernet** (or `pyrage`/age) | D-02: audited library mandatory. Fernet removes every "choose IV/mode/MAC" foot-gun |
| Key derivation | Homemade hash-stretching | `cryptography` **scrypt/Argon2** | Tuned, audited, side-channel-aware |
| Import boundaries | grep/AST scripts in CI | **import-linter** contracts | Handles indirect/transitive imports; SC#1 names it |
| Cross-process config lock | flock plumbing | **filelock** | Portable, battle-tested, context-manager API |
| Atomic file swap | copy+delete | stdlib **`os.replace`** + fsync | `os.replace` is atomic on the same filesystem; POSIX-guaranteed |
| Async SQLite | threads + a queue over sqlite3 | **aiosqlite** | Purpose-built async wrapper; keep single-writer discipline |
| Config schema/validation | dict-poking + manual checks | **Pydantic v2** | Typed, JSON-schema export for the desktop app, field metadata for tiers |
| No-network CI enforcement | mocking every client | **pytest-socket `--disable-socket`** | Fails the build on *any* real socket; a true negative control |
| YAML round-trip w/ comments | regex editing | **ruamel.yaml** | Preserves comments/order on programmatic write-back |

**Key insight:** This phase is almost entirely "wire well-known, audited libraries together correctly." The value is not in code volume; it is in the *guards being real*. Custom crypto or custom import-checking here would be strictly worse and, for crypto, explicitly forbidden by D-02.

## Runtime State Inventory

> This is a **greenfield scaffold** (D-05; `spike/` deleted per SC#5/D-18). No prior framework code, datastore, service config, or OS registration exists to migrate. Included for completeness because the phase touches on-disk formats that later phases inherit.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None yet. The SQLite trace DB schema and the YAML config format are *created* here and become the durable contract downstream phases read. | Define schema + config layout carefully; they are the migration baseline |
| Live service config | None — no running services; no target hardware (STATE.md). | None |
| OS-registered state | None — nothing registered with systemd/launchd/scheduler yet. | None (Phase 9 introduces the Linux service) |
| Secrets / env vars | None pre-existing. The secret-store master-key *provisioning source* (env / systemd credential / key file) is **defined** here for the first time. | Decide + document the master-key source (checkpoint) |
| Build artifacts | None — root has no `pyproject.toml`/`.venv` yet (Phase 1 kept root clean, STATE.md 01-01). The uv workspace + per-package wheels are new. | Create workspace; ensure `.gitignore` covers `dist/`, `*.egg-info`, `.venv` |

**Nothing found in categories 1–4** — verified: repo root contains only `.planning/`, `DECISIONS.md`, `project-docs/`, `skills-lock.json`, `.agents/`, `.claude/` (no source packages, no `pyproject.toml`, no DB).

## Common Pitfalls

### Pitfall 1: The vacuous guard (project's #1 historical failure)
**What goes wrong:** An import-linter contract, a stale-revision check, or a no-network assertion passes because it was never actually exercised against a violation.
**Why it happens:** Contracts pass trivially when the forbidden import/edge simply doesn't exist yet; a happy-path test never submits a stale revision.
**How to avoid:** For every guard, add a paired negative-control test: a fixture module that *does* the forbidden import (xfail/expected-fail on the contract), a write with a deliberately stale `expected_revision` asserting `ConflictError`, and a test asserting `pytest-socket` actually blocks a socket. Phase 1 caught the ollama no-cloud check and the render device-fallback both passing vacuously (STATE.md).
**Warning signs:** A contract/threshold test that has never been seen to fail; a PR that adds a guard with only a green test.

### Pitfall 2: Clean-venv wheel job that isn't clean (FOUND-02)
**What goes wrong:** The "independently installable" job imports `paaf_llm` from the workspace source tree rather than the built wheel, so a hidden dependency on `paaf-core`/voice would still pass.
**Why it happens:** `PYTHONPATH`/cwd leakage, editable installs, or running from the repo root.
**How to avoid:** `uv build --package paaf-llm`; create a *fresh* venv in a temp dir; `pip install dist/paaf_llm-*.whl`; `cd` out of the repo; run smoke tests via `pytest --pyargs paaf_llm`. Assert `paaf_voice`/`paaf_core` are *not* importable if they're not declared deps.
**Warning signs:** The job passes even when you deliberately add a `paaf_voice` import to `paaf_llm`.

### Pitfall 3: TTFA gate that measures the wrong thing (TRACE-04, D-08/09)
**What goes wrong:** The gate asserts only "TTFA < ceiling" and silently accepts a *broken measurement* (e.g. TTFA recorded as 0, or as the whole round trip) as long as the number is small/large in the right direction.
**Why it happens:** Only the budget half (D-08b) is implemented; the accuracy half (D-08a/D-09, the load-bearing one) is skipped.
**How to avoid:** Fake TTS emits first audio after a *fixed injected delay D*; assert `abs(recorded_ttfa - D) < tol` (accuracy) AND `framework_overhead < small_ceiling` AND `recorded_ttfa < budget`. Use a controllable/monotonic clock so accuracy is deterministic, not wall-clock flaky. Remember (D-09, Phase-1 evidence): the budget is a **measurement/overhead-regression guardrail, explicitly NOT a shipped-latency claim** (real TTFA was 6.27 s on mps with a ~10× tail).
**Warning signs:** The accuracy assertion is absent; the test would pass if the recorder returned a constant.

### Pitfall 4: Config value loss on write-back
**What goes wrong:** Round-tripping YAML through PyYAML strips comments and reorders keys, silently mangling a user-authored file.
**Why it happens:** `yaml.safe_load` → `yaml.safe_dump` discards presentation.
**How to avoid:** If the API writes config back, use ruamel.yaml round-trip mode; or make the API fully own the file (emit from the Pydantic model with a documented, stable ordering) and never expect user hand-edits to survive a write.
**Warning signs:** User reports lost comments after saving from the desktop app.

### Pitfall 5: SQLite writer contention / lost writes under WAL
**What goes wrong:** Multiple writers, or `synchronous=FULL` on the hot path, cause `database is locked` errors or stalls.
**Why it happens:** Not enforcing single-writer; missing `busy_timeout`; awaiting the queue on the audio path.
**How to avoid:** Exactly one writer task owns the connection; WAL + `synchronous=NORMAL` + `busy_timeout`; producers use `put_nowait` with a drop-counter.
**Warning signs:** Intermittent `OperationalError: database is locked`; audio jitter correlated with trace volume.

## Code Examples

(See Patterns 1–7 above — each carries a runnable, source-attributed snippet.) Additional CI shape:

### No-hardware / no-network CI matrix (FOUND-03, SC#1/#2/#5)
```yaml
# Source: standard GitHub Actions + uv + pytest-socket composition
jobs:
  suite:                       # SC#1 + full green suite, no HW, no net
    steps:
      - run: uv sync --all-packages
      - run: uv run lint-imports          # import-linter contracts (FOUND-04)
      - run: uv run pytest --disable-socket   # pytest-socket => any socket fails the build
      # negative control: a job/test that ADDS a forbidden import must go RED
  wheel-independence:          # SC#2 (FOUND-02)
    steps:
      - run: uv build --package paaf-llm
      - run: python -m venv /tmp/clean && /tmp/clean/bin/pip install dist/paaf_llm-*.whl
      - run: cd /tmp && /tmp/clean/bin/pytest --pyargs paaf_llm   # smoke, no workspace present
  ttfa-gate:                   # SC#5 (TRACE-04) — fake TTS, cold, no HW/net
      - run: uv run pytest packages/paaf-trace/tests/test_ttfa_regression.py --disable-socket
```
> No `sounddevice`/audio import may appear in `paaf-core`/`paaf-trace`/`paaf-llm` import graphs, so "no audio hardware" is satisfied by construction, not by mocking a device.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Poetry / setuptools multi-repo | uv workspace + hatchling, single lockfile | uv workspaces mature 2024→2026 | One `uv.lock`, `--package` builds, editable inter-deps; the project standard |
| Pydantic v1 `.dict()`/validators | Pydantic v2 `model_fields`, `json_schema_extra`, `model_validate` | v2 (2023+) | Field metadata carries reload tiers; JSON-schema export feeds the desktop app |
| GPG for file secrets | age format (`pyrage`) / Fernet recipe | age gained traction 2021+ | Modern, minimal, no config foot-guns; both are valid here |
| Manual `flake8` import rules | import-linter declarative contracts | mature by 2.x | Catches indirect imports; the SC#1 authority |
| threads-over-sqlite3 | aiosqlite single-writer + WAL | standard by 2023 | Clean async, no writer contention |

**Deprecated/outdated:**
- `pip index versions` was unusable in this sandbox (no output) — the PyPI JSON API is the reliable version source.
- Do **not** reach for SOPS/secrets-in-git (out of scope, CONTEXT) or OS-keyring (deferred, D-04) as the Phase-2 default.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | **pyca `cryptography` (Fernet+scrypt) is the right secret-store lib over `pyrage`/age.** Both are viable; the recommendation rests on D-02 weighting "audit history" highest. This is a genuine decision the user delegated and should ratify. | Standard Stack / Alternatives | Low technical risk (both work). If the user prefers the age format's modernity/multi-recipient/secrets-in-git path, switch to `pyrage`. Behind `SecretStore`, the swap is cheap |
| A2 | A `0600` key file (or systemd credential / env) as the master-key source satisfies CORE-04 for v1; passphrase-at-boot is optional. | Pattern 3 | If the user requires passphrase-at-boot for the threat model, the provisioning path (and headless restart UX) changes. Flag as a planner checkpoint |
| A3 | `pytest-socket --disable-socket` is the chosen no-network enforcement mechanism. | Supporting / CI | Low. If unsuitable, a `socket`-blocking autouse fixture is a drop-in replacement. Verify exact version on registry before install |
| A4 | ruamel.yaml (not PyYAML) for config write-back, to preserve comments. | Supporting / Pitfall 4 | Low. If the API fully owns the file and hand-edits need not survive, PyYAML is simpler |
| A5 | Exact import-linter `ignore_imports` glob form for the adapter exception (`importer -> imported`) is as documented; the Phase-2 stub needs no exception yet. | Pattern 7 | Low. Confirm against import-linter 2.13 docs when Phase 3 wires the whitelist |
| A6 | Package versions are current as of 2026-07-25 (read from PyPI JSON API). | Standard Stack | Low. Re-pin at implementation via `uv add` which resolves latest-compatible |

## Open Questions

1. **Which crypto library — `cryptography` (Fernet) or `pyrage` (age)?**
   - What we know: both are audited-ecosystem, MIT/BSD, offline, headless, no account/cloud. `cryptography` wins on audit surface/downloads; `pyrage` wins on format modernity + future secrets-in-git path.
   - What's unclear: the user's relative weighting of "most-audited primitive lib" vs "complete modern audited format." D-02 tilts toward `cryptography`.
   - Recommendation: default to **pyca `cryptography` Fernet**, keep `SecretStore` swappable; raise as a one-line ratification in discuss/plan.

2. **Master-key provisioning source for the encrypted secret store.**
   - What we know: CORE-04 requires separate + encrypted + write-only-API + not-in-YAML + not-in-logs; it does not mandate a specific key source.
   - What's unclear: key file (0600) vs systemd credential vs passphrase-at-boot — a UX/threat-model tradeoff for a headless auto-restarting service.
   - Recommendation: v1 = key file / env / systemd credential behind `SecretStore`; document the tradeoff; a `checkpoint:human-verify` before locking it.

3. **App license posture (FOUND-07).**
   - What we know: framework = Apache-2.0 (required). CONTEXT: apps *lean* Apache-2.0 for v1; AGPL recorded as an open governance question, **not chosen**.
   - Recommendation: write DECISIONS.md with Apache-2.0 as the current app default and AGPL as an explicit open question; do not treat AGPL as decided.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Workspace/build (FOUND-01/02) | ✓ | 0.11.31 | — |
| Python | Runtime | ✓ (Phase-1 baseline) | 3.12.13 | — |
| git (for DCO sign-off) | FOUND-07 | ✓ | repo present | — |
| PyPI network access (install time) | deps | ⚠ intermittent in sandbox | — | Resolve/lock on a networked machine; CI installs from lockfile |
| Rust toolchain | only if `pyrage` chosen (has wheels) | n/a | — | `pyrage` ships Linux+macOS wheels; only source-builds need Rust |

**Missing dependencies with no fallback:** none blocking. All required tooling for scaffolding is present locally.
**Missing dependencies with fallback:** reliable PyPI access — resolve `uv.lock` where network is stable; CI restores from the lockfile.

## Validation Architecture

> nyquist_validation is enabled (config.json `workflow.nyquist_validation: true`).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (Phase-1 baseline) |
| Config file | none at root yet — **Wave 0 creates** root `pyproject.toml` `[tool.pytest.ini_options]` + per-package test dirs |
| Quick run command | `uv run pytest packages/<pkg>/tests -x -q --disable-socket` |
| Full suite command | `uv run pytest --disable-socket && uv run lint-imports` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOUND-01 | Workspace resolves; each package versioned + smoke test | unit | `uv run pytest -k smoke --disable-socket` | ❌ Wave 0 |
| FOUND-02 | Built `paaf-llm` wheel installs+imports in clean venv | integration (CI job) | wheel-independence job (see CI shape) | ❌ Wave 0 |
| FOUND-03 | Full suite green, no HW, no net | suite | `uv run pytest --disable-socket` | ❌ Wave 0 |
| FOUND-04 | Forbidden import fails CI **+ negative control goes red** | contract | `uv run lint-imports` + xfail violation fixture | ❌ Wave 0 |
| FOUND-05/06/07 | Governance docs / headers / DCO present | doc-presence | test asserting files + SPDX headers exist | ❌ Wave 0 |
| CORE-01 | Invalid config rejected by schema | unit | `pytest test_config_schema.py` | ❌ Wave 0 |
| CORE-02 | Crash mid-write cannot corrupt (temp+fsync+rename) | unit | `pytest test_atomic_write.py` (simulate failure between write and replace) | ❌ Wave 0 |
| CORE-03 | Stale-revision write rejected as conflict | unit (+neg control) | `pytest test_revision_conflict.py` | ❌ Wave 0 |
| CORE-04 | Secret round-trips; never in YAML/logs | unit | `pytest test_secret_store.py` (+ assert absence in serialized YAML & captured logs) | ❌ Wave 0 |
| CORE-05 | Component declares endpoints via common interface | unit | `pytest test_endpoint_declaration.py` | ❌ Wave 0 |
| CORE-06 | Each key reports its reload tier | unit | `pytest test_reload_tiers.py` | ❌ Wave 0 |
| TRACE-01 | WAL + single-writer bounded queue, off hot path | unit/async | `pytest test_trace_queue.py` (assert emit never awaits/blocks) | ❌ Wave 0 |
| TRACE-02 | Run records prompts/model/tool args+results/timings/tokens | unit | `pytest test_trace_schema.py` | ❌ Wave 0 |
| TRACE-03 | `time_to_first_audio` is a first-class column | unit | `pytest test_trace_schema.py::test_ttfa_column` | ❌ Wave 0 |
| TRACE-04 | Fake-TTS TTFA gate: accuracy + overhead + budget, cold | integration | `pytest test_ttfa_regression.py --disable-socket` | ❌ Wave 0 |
| TRACE-05 | Trace store has no network egress | contract/unit | import-linter (no net client) + `--disable-socket` test | ❌ Wave 0 |
| PRIV-01/02 | No accounts / no telemetry anywhere | doc + negative | doc assertion + `--disable-socket` suite (no phone-home) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/<changed-pkg>/tests -x -q --disable-socket`
- **Per wave merge:** `uv run pytest --disable-socket && uv run lint-imports`
- **Phase gate:** full suite green + all three CI jobs (suite / wheel-independence / ttfa-gate) green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] Root `pyproject.toml` with `[tool.uv.workspace]`, `[tool.pytest.ini_options]`, `[tool.importlinter]`
- [ ] Per-package `tests/` dirs + `conftest.py` (shared fixtures: tmp config path, controllable clock, captured-log fixture)
- [ ] `pytest-socket` installed and `--disable-socket` wired as the no-network default
- [ ] Negative-control fixtures: a module that performs a forbidden import (for the contract), a stale-revision write, a socket-open test
- [ ] Controllable/monotonic clock fixture for the deterministic TTFA accuracy assertion
- [ ] `.github/workflows/ci.yml` with the three jobs

## Security Domain

> security_enforcement is enabled (config.json), ASVS level 1, block_on high.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 2) | Device pairing/PIN is Phase 9/10 (APP-06) |
| V3 Session Management | no | — |
| V4 Access Control | partial | Secret store is write-only over the (future) API; interface enforces get-for-consume-only |
| V5 Input Validation | **yes** | **Pydantic v2** validates the config tree on every read/write (CORE-01) |
| V6 Cryptography | **yes** | **pyca `cryptography`** (Fernet + scrypt) — audited lib, no hand-rolled crypto (D-02, CORE-04) |
| V7 Errors & Logging | **yes** | Secret *values* never enter the config model or logs; assert absence in tests (CORE-04) |
| V14 Configuration | **yes** | Atomic writes + monotonic-revision conflict rejection (CORE-02/03); no secrets in YAML |

### Known Threat Patterns for {Python config/secret/trace foundation}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret leaked into YAML tree or logs | Information Disclosure | Separate encrypted `SecretStore`; keys not values in the model; log-redaction + test asserting absence (CORE-04) |
| Config corruption on crash | Tampering / DoS | Atomic temp+fsync+rename (CORE-02) |
| Lost/overwritten concurrent edit | Tampering | Optimistic monotonic-revision + filelock (CORE-03) |
| Hand-rolled or misconfigured crypto | Information Disclosure | Audited `cryptography` Fernet recipe; scrypt KDF; no primitive assembly (D-02) |
| Silent telemetry / phone-home | Information Disclosure | No telemetry deps; `pytest-socket --disable-socket` proves no egress (PRIV-02) |
| Trace data leaving device | Information Disclosure | `paaf-trace` has no network client (import-linter) + `--disable-socket` (TRACE-05) |
| Architectural erosion (langchain/voice↔llm coupling) | Tampering (integrity of boundaries) | import-linter contracts fail CI, with negative controls (FOUND-04) |
| Prompt-injection defense posture | (documentation constraint) | Document that the **permission model is the only injection defense**, no hidden filters (FOUND-05 / TOOL-07) — written down in DECISIONS.md this phase |

## Sources

### Primary (HIGH confidence)
- PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`), queried 2026-07-25 — versions, licenses, upload dates for cryptography 49.0.0, pydantic 2.13.4, hatchling 1.31.0, import-linter 2.13, aiosqlite 0.22.1, ruamel.yaml 0.19.1, filelock 3.32.0, pyrage 1.3.0.
- pypistats.org recent-downloads API — cryptography ~1.4B/mo, import-linter ~12M/mo, pyrage ~159k/mo.
- Local `uv --version` — uv 0.11.31.
- `.claude/CLAUDE.md`, `DECISIONS.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `02-CONTEXT.md` — project-authoritative decisions and Phase-1 evidence.

### Secondary (MEDIUM confidence)
- import-linter official docs (readthedocs, contract_types) — forbidden/independence/layers contract fields (`source_modules`, `forbidden_modules`, `ignore_imports`, `as_packages`).
- uv official docs (docs.astral.sh) — workspace members, `[tool.uv.sources] workspace=true`, `uv build --package`.
- woodruffw/pyrage README + FiloSottile/awesome-age — pyrage capabilities, age format identity types.

### Tertiary (LOW confidence)
- General web results on age security/audit history (no specific third-party audit doc surfaced this session) — treat age's audit maturity as "younger than pyca cryptography," which is the crux of the A1 recommendation.
- `pytest-socket` version not pinned this session — verify on registry before install.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions read live from PyPI JSON API; all packages long-established and project-named.
- Architecture/patterns: HIGH — standard, well-documented Python patterns (atomic write, optimistic concurrency, single-writer SQLite, Pydantic metadata, import-linter contracts).
- Crypto-library selection: MEDIUM — a genuine two-way decision (A1); recommendation defensible on D-02 but should be user-ratified.
- Pitfalls: HIGH — grounded in Phase-1's recorded negative-control failures and standard SQLite/packaging gotchas.

**Research date:** 2026-07-25
**Valid until:** ~2026-08-24 (30 days; stable ecosystem — re-pin versions via `uv add` at implementation, and confirm import-linter `ignore_imports` syntax + `pytest-socket` version when wiring).
