# Phase 2: Foundation - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 builds the **monorepo skeleton where architectural rules are build failures, not
intentions**. In scope: the uv workspace + hatchling; all five framework packages as importable
skeletons with two (`paaf-core`, `paaf-trace`) carrying real implementation; import-linter
contracts that fail CI on forbidden imports; the config system (typed schema, atomic writes,
monotonic-revision conflict rejection, encrypted secret store, network-endpoint interface, reload
tiers); the SQLite trace store with `time_to_first_audio` as a first-class CI-defended column; and
the licensing/governance docs (DECISIONS.md, CONTRIBUTING.md, architecture doc, Apache-2.0 headers,
DCO). Everything runs with **no audio hardware and no network**.

**Out of scope (belongs to later phases):** the real `paaf-llm` engine and its port interface
(designed fresh in Phase 3 per Phase-1 D-18), any real voice engine (`paaf-voice`, Phase 4+), the
turn orchestrator (`paaf-session`), and the desktop/embedded apps' actual functionality. Those
packages exist here only as importable skeletons so the import-linter contracts are real.
</domain>

<decisions>
## Implementation Decisions

### Secret store (CORE-04)
- **D-01:** API keys go in a **separate encrypted store**, never in the YAML tree, never logged,
  write-only over the API — as REQUIREMENTS specifies.
- **D-02:** The crypto MUST come from an **established, independently-audited open-source library.
  No hand-rolled crypto, no bespoke cipher.** Trustworthiness/audit history is the primary
  selection criterion — the user asked specifically for "a trustable open-source solution."
- **D-03:** It must work **headless and offline-verifiable** (the ship target is a headless Linux
  box; the project's core value is verifiable offline operation). This down-weights D-Bus/OS-keyring
  approaches that are awkward on a server.
- **D-04:** Sits behind a pluggable `SecretStore` interface so an OS-keyring backend can be added
  later without refactoring callers. Encrypted-file backend is the default/first implementation.
- **→ Research task (for gsd-phase-researcher):** select the concrete library. Leading candidates
  to evaluate on audit history, maintenance, headless fit, and Python integration:
  **`age` (FiloSottile/age)** and **`Fernet` from pyca/`cryptography`** (the de-facto audited Python
  crypto lib). Consider **SOPS/getsops** only if config-with-secrets-in-git ever becomes a goal
  (currently out of scope). Reject anything requiring an account or a cloud KMS (PRIV-01/PRIV-02).

### Monorepo scaffold scope (FOUND-01..04)
- **D-05:** Scaffold **all five framework packages as importable skeletons** (each with a version
  and a smoke test), but give real Phase-2 implementation only to **`paaf-core`** (config) and
  **`paaf-trace`** (trace store). The other three (`paaf-llm`, `paaf-voice`, `paaf-session`) are
  minimal importable stubs.
- **D-06:** Rationale is load-bearing, not cosmetic: SC#1 ("`paaf-voice` importing `paaf-llm` fails
  CI") and the import-linter contracts **cannot be tested unless those packages exist**. Skeletons
  make the contracts real from the first commit.
- **D-07:** The **two apps** (`app-embedded`, `app-desktop`) are **NOT** scaffolded in Phase 2 —
  they have no Phase-2 work. (Chosen over the "all 7" option to avoid empty structure this early.)

### TTFA regression guard (TRACE-03/04)
- **D-08:** The CI guard uses a **fake TTS** and asserts **both**: (a) **accounting accuracy +
  overhead** — the fake emits first audio after a fixed injected delay, and the recorded
  `time_to_first_audio` must match that delay within a tight tolerance while framework/measurement
  overhead stays under a small ceiling; AND (b) a **fixed budget ceiling** on the measured value.
- **D-09:** The accuracy half is the load-bearing one (it proves the *measurement* is correct with
  no real engine, which is the whole point of doing this before Phase 4). Phase-1 evidence binds
  here: real TTFA is engine- and sentence-dependent (6.27 s on mps, ~10× tail), so the fixed budget
  is a **guardrail against measurement/overhead regression, explicitly NOT a claim about shipped
  latency.** The CI job runs cold, no audio hardware, no network (SC#5, FOUND-03).

### Claude's Discretion
- **App license (FOUND-07)** — the user did not select this to discuss. **Lean, not locked:**
  framework is Apache-2.0 (required). The apps default to **Apache-2.0 for v1** to minimize
  solo-maintainer friction and ship early; **AGPL for the apps (capture-resistance) is recorded as
  an open governance question in DECISIONS.md**, to be decided deliberately rather than by default.
  Planner/researcher should not treat AGPL as chosen.
- Import-linter contract shapes, config schema library (Pydantic per stack), SQLite pragmas/queue
  design, and CI matrix details are implementation choices left to research + planning, constrained
  by the requirements and Phase-1 decisions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` — FOUND-01..07, CORE-01..06, TRACE-01..05, PRIV-01/02 (the 20 Phase-2 requirement IDs and the five-package + two-app architecture statement at the top).
- `.planning/ROADMAP.md` §"Phase 2: Foundation" — goal and the six Success Criteria (the real contract; `mode: mvp`).

### Phase-1 decisions this phase inherits
- `DECISIONS.md` (repo root) — the agent-framework decision (LangChain behind a port; the "confine framework imports to one adapter package, CI-enforced" rule that FOUND-04's import-linter contract implements) and the "no code from Phase 1 survives" note (the port is designed fresh in Phase 3, D-18).
- `.claude/CLAUDE.md` §"The constraint that makes this decision cheap" (import confinement + ruff/import-linter banned-api rule), §"Development Tools" (uv + hatchling + ruff + mypy/ty), §"Supporting Libraries" (`aiosqlite`, raw-SQL trace store, no ORM), and §"Decision 1" (adapter-package boundary).

### No external ADRs/specs yet
- No standalone ADR or SPEC.md files exist for Phase 2 — requirements + Success Criteria + the decisions above are the full contract.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None from Phase 1 survives by design** — `spike/` was deleted (SC#5/D-18). This is a greenfield
  scaffold; no existing framework code to reuse.

### Established Patterns (from Phase 1, to carry as principles not code)
- **Negative-control discipline:** a check that cannot fail is not a check. Phase 1 twice caught
  vacuously-passing assertions (the ollama no-cloud check; the render device-fallback). Every
  Phase-2 contract test (import-linter violation, stale-revision conflict, offline enforcement,
  TTFA regression) should include a proof that the guard actually fails on the bad input.
- **Adapter-package confinement works and is cheap** (~61 lines, recoverable for ~250) — FOUND-04's
  import-linter contract is the CI enforcement of exactly this.

### Integration Points
- Fresh repo root: `pyproject.toml` (uv workspace + hatchling) does not exist yet and is created
  here. Phase 1 deliberately left the root clean of any `pyproject.toml`/`pytest.ini` (Phase 2 owns
  the workspace).
</code_context>

<specifics>
## Specific Ideas

- Secret store: user's exact framing was "find an open source solution for storing secrets — it
  should be trustable." Interpreted as: established + audited + open-source, not bespoke crypto.
- Trace store TTFA: honor Phase-1's finding that real latency is engine/sentence-dependent — the CI
  number is a measurement-correctness and overhead-regression guard, not a shipped-latency promise.
</specifics>

<deferred>
## Deferred Ideas

- **AGPL licensing for the apps** (capture-resistance) — recorded as an open governance question in
  DECISIONS.md; decide deliberately, not in this phase's default.
- **OS-keyring secret backend** — the pluggable `SecretStore` interface allows it later; not
  implemented in Phase 2.
- **App scaffolding** (`app-embedded`, `app-desktop`) — deferred to their own phases; only the five
  framework packages exist after Phase 2.
- **SOPS/secrets-in-git** — only relevant if config-with-secrets-in-git ever becomes a goal; out of
  scope now.

</deferred>

---

*Phase: 2-Foundation*
*Context gathered: 2026-07-25*
