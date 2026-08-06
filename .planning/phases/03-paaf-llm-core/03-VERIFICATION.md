---
phase: 03-paaf-llm-core
verified: 2026-08-06T12:00:00Z
status: gaps_found
score: 3/5 must-haves verified
behavior_unverified: 1
overrides_applied: 0
gaps:
  - truth: "SC#2 — The user names model profiles across Ollama, OpenAI-compatible endpoints and Anthropic in YAML — including two separate local servers on the LAN as distinct profiles — and `paaf chat` uses them without a line of code."
    status: partial
    reason: >-
      Naming works and two-LAN distinctness is genuinely proven, but PAAF's own
      declared credential mechanism is not wired into the shipped command:
      `cli._default_adapter` constructs `build_engine_adapter(config)` with NO
      secret store, so ANY profile that declares `api_key_ref` dies at bind with
      an EngineError. Verified by running `paaf chat` against a hand-written
      YAML. That makes the Anthropic leg (and any authenticated OpenAI-compatible
      leg) reachable only by setting the provider SDK's own environment variable,
      which routes around the CORE-04 SecretStore the schema's `api_key_ref`
      exists to use. Separately, `paaf_core.Endpoint` carries no URL path, so an
      OpenAI-compatible server mounted at `/v1` (vLLM, llama.cpp server, LM
      Studio — the named use case for that provider) cannot be addressed at all,
      and an unauthenticated local OpenAI-compatible server cannot bind because
      ChatOpenAI demands credentials the schema has no unauthenticated way to
      supply. Ollama is unaffected.
    artifacts:
      - path: "packages/paaf-llm/src/paaf_llm/cli.py:138"
        issue: "`return build_engine_adapter(config)` — the `secret_store` parameter is never passed, so LangChainAdapter._secret_store is always None in production. Every `api_key_ref` profile raises EngineError at bind."
      - path: "packages/paaf-llm/src/paaf_llm/_engine/__init__.py:326-346"
        issue: "`base_url()` derives scheme://host:port with no path; `paaf_core.net.endpoint.Endpoint` has no path field and `ModelProfile` has `extra=\"forbid\"`, so `/v1` is inexpressible."
      - path: "packages/paaf-llm/tests/test_engine_adapter.py"
        issue: "`openai_compatible` is exercised only at the provider-string level (line 175). No test binds an openai_compatible profile, which is why neither the missing-credential nor the missing-path failure was caught."
    missing:
      - "Wire a `paaf_core` SecretStore into `cli._default_adapter` (build_engine_adapter accepts `secret_store=` already — the parameter exists and is unit-tested, it is simply never supplied), or document explicitly that env-var credentials are the Phase-3 path."
      - "Add an `endpoint_path` field to ModelProfile (and a path to paaf_core Endpoint) so OpenAI-compatible servers under /v1 are addressable, OR record this as an accepted Phase-3 limitation in ROADMAP/REQUIREMENTS rather than only in a plan SUMMARY."
      - "A way to express 'this OpenAI-compatible endpoint needs no auth' so an unauthenticated LAN server can bind."
      - "A test that binds an openai_compatible profile end-to-end (the one provider with no binding-level coverage)."
  - truth: "`paaf chat` reports failures readably rather than as a Python traceback (D-01 thin-CLI / 'nothing hidden' spirit)."
    status: failed
    reason: >-
      `_chat_loop` catches only `AllProvidersFailed`. `EngineError` — which the
      engine module's own docstring designates as the class for the most likely
      real-world first-run failure (a missing or unresolvable credential, a wrong
      model name) — propagates out of `asyncio.run` as a raw traceback.
      Reproduced live twice.
    artifacts:
      - path: "packages/paaf-llm/src/paaf_llm/cli.py:244-247"
        issue: "`except AllProvidersFailed` only; no handler for EngineError (or for a mid-stream AdapterError, which the engine deliberately does not catch after first-token commit)."
    missing:
      - "Catch EngineError (and a post-commit AdapterError) in `_chat_loop` and re-raise as click.ClickException, with a test."
deferred:
  - truth: "SC#5's 'skill fragments' clause — an ACTIVE skill contributes a persona fragment to the composed prompt (PERS-02)."
    addressed_in: "Phase 6 — Skills & PyPI Release"
    evidence: "Phase 6 success criterion 2: 'Enabling or disabling an installed skill changes the composed prompt and the tool registry without uninstalling it.' Phase 3's `cli.load_skill_fragments` returns `[]` by documented design (D-09); the composer's fragment contract is pinned now by tests that repoint that source."
  - truth: "SC#5's 'runtime context' clause — time, device name, room compose into the prompt (PERS-03)."
    addressed_in: "Phase 10 — The Appliance"
    evidence: "REQUIREMENTS.md traceability table maps PERS-03 to 'Phase 10 — The Appliance'. Plan 03-07 scoped SC#5 to base + skill fragments on this basis (D-09)."
behavior_unverified_items:
  - truth: "SC#3 — Pulling the WAN mid-conversation moves the reply onto a local profile and the conversation continues."
    test: "With a real cloud profile as `active_profile` and a real local Ollama profile in `fallback_chain`, start `paaf chat`, send one turn successfully, then physically disconnect the WAN and send a second turn."
    expected: "The second turn prints `↳ fell back to <local> (connection)` and is answered by the local model, and the local model's reply demonstrates it received the first turn's history."
    why_human: >-
      Every fallback trigger is proven against the FakeAdapter and the four
      transport translations are validated against 13 real provider SDK exception
      instances, but no test in the repo contacts a real provider — the suite runs
      under `--disable-socket` by design. Cutting a real WAN link is a physical
      state change no automated check in this repo can produce. (03-VALIDATION.md
      already lists this as Manual-Only.) Partial live evidence was collected
      during this verification: an unreachable LAN Ollama endpoint did produce a
      real ConnectionFailed and the loop did advance to the next profile.
human_verification:
  - test: "Pull the WAN mid-conversation with a real cloud active profile and a real local fallback (see behavior_unverified_items)."
    expected: "Reply moves onto the local profile, one `↳ fell back to ... (connection)` notice, conversation history intact."
    why_human: "No test contacts a real provider; the suite is socket-disabled by design."
  - test: "Cold-start a 14B Ollama model and send the first turn."
    expected: "No spurious `slow_first_token` fallback inside the configured `first_token_budget_s`; `Agent.warmup()`/`LangChainAdapter.preload()` absorbs the cold-load cost."
    why_human: "03-VALIDATION.md Manual-Only row. Timing against a real cold-loading model cannot be asserted deterministically offline."
  - test: "Run `paaf chat` against a real running local Ollama server (`endpoint_host`/`endpoint_port` pointing at it) and hold a two-turn conversation."
    expected: "Both turns answer; the second turn's answer shows the model saw the first."
    why_human: "MODEL-01/02 real round-trip. Requires a live provider; excluded from the socket-disabled CI suite."
  - test: "Point two Ollama profiles at two DIFFERENT physical LAN machines and confirm each answers from its own box."
    expected: "Each named profile is served by its own server (distinct model names or `ollama ps` on each box confirms which one ran)."
    why_human: "MODEL-06's headline. Proven at the binding level (two distinct clients with distinct base_urls) but never against two real servers."
---

# Phase 3: paaf-llm Core (single agent) — Verification Report

**Phase Goal:** `paaf chat` holds a real single-agent conversation using a model the user named in YAML, survives losing its provider mid-sentence via a user-defined fallback chain, and shows the user the exact prompt it sent — while each profile also declares the capability manifest and peer-agent graph the mesh will later traverse.

**Verified:** 2026-08-06
**Status:** gaps_found
**Re-verification:** No — initial verification

> **Mode note (non-blocking).** ROADMAP.md declares `Mode: mvp` for this phase, but the
> phase goal is not in User Story form (`As a …, I want to …, so that …`). The MVP-mode
> guard would normally refuse to verify. It is bypassed here because the five Success
> Criteria are explicit and independently verifiable, and the orchestrator directed a
> goal-backward assessment against them. The User Flow Coverage table is therefore
> omitted; the mode/goal mismatch is surfaced for the maintainer to reconcile.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The `fake/` adapter is written and merged BEFORE the real adapter, and the entire `paaf-llm` suite passes against it with the agent framework uninstalled | ✓ VERIFIED | Ordering proven from git: `9d8d43f` (FakeAdapter, 2026-08-05 16:19) precedes `105fcde` (LangChainAdapter, 2026-08-05 23:46). **I ran `bash scripts/check_framework_uninstalled.sh` myself**: builds wheels, asserts the wheel ships all 11 fake-suite test files (and only deliberately excludes `test_engine_adapter.py`), installs into a clean off-repo venv, runs `pytest --pyargs paaf_llm` → **102 passed**, then asserts `langchain` and `langgraph` are both unimportable. `check_wheel_independence.sh` also PASS. |
| 2 | Model profiles across Ollama, OpenAI-compatible and Anthropic in YAML — incl. two LAN servers as distinct profiles — and `paaf chat` uses them without a line of code | ✗ FAILED (partial) | Naming and two-LAN distinctness verified (see below). **But `paaf chat` cannot use any profile that declares `api_key_ref`** — `cli.py:138` never passes a secret store. Reproduced live: `EngineError: could not bind 'anthropic:claude-sonnet-4-5': profile declares api_key_ref 'anthropic_key' but no secret store was provided`. OpenAI-compatible under `/v1` is inexpressible, and an unauthenticated local OpenAI-compatible server cannot bind. See Gaps. |
| 3 | Pulling the WAN mid-conversation moves the reply onto a local profile and the conversation continues; timeout / 5xx / 429 / slow-first-token trigger the same chain | ⚠️ PRESENT_BEHAVIOR_UNVERIFIED | All five triggers + two negative controls proven against the fake (`test_fallback.py`), with an exhaustiveness control over the whole `FallbackReason` enum and over `AdapterError.__subclasses__()`. Real-provider translation validated against 13 real SDK exception instances (`test_translation_matches_the_real_provider_exception_types`, 26/26 pass with `[engine]`). **No test contacts a real provider** — the suite is socket-disabled by design, and a WAN pull is a physical state change. Routed to human verification. |
| 4 | Each profile declares a natural-language capability manifest and peer agents in YAML; the schema validates them and `paaf chat` surfaces them, with no handoff behavior | ✓ VERIFIED | Schema: `capabilities: str` (free text), `peers: list[str]`, `constraints: list[str]`; `_check_refs` rejects dangling/self peers, dangling fallback targets, and a dangling `active_profile` (`test_peer_validation`, 4 rejection cases). Surfaced: **I ran `paaf profiles` and `paaf chat` on a hand-written YAML** and saw every manifest, peer, constraint and the inert-graph note. Inertness has a real negative control: `test_manifest_performs_no_handoff` leaves the declared peer UNPROGRAMMED so any contact raises `LookupError` (not an `AdapterError` the loop could swallow). `TurnResult.handoff` is hardcoded `None`. |
| 5 | One command prints the final composed prompt verbatim — exactly as sent, containing nothing the user did not write | ✓ VERIFIED (2 clauses deferred) | **I ran `paaf prompt` and `od -c`'d the output**: it ends at the last user character with no trailing newline. `test_prompt_byte_exact` closes the loop three ways — CLI stdout == `compose()` == the `system` message the adapter actually received on a real turn. `--provenance` segments rejoin byte-identically. Negative controls: fragments present, no labels in the raw view, no adapter constructed. The SC's "skill fragments" and "runtime context" clauses are deferred to Phases 6 and 10 respectively (see Deferred Items). |

**Score:** 3/5 truths verified (1 present, behavior-unverified; 1 failed)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC#5 "skill fragments" — an active skill contributes a fragment (PERS-02) | Phase 6 | Phase 6 SC#2: "Enabling or disabling an installed skill changes the composed prompt and the tool registry without uninstalling it." Phase 3's `load_skill_fragments` returns `[]` (D-09); the fragment contract is pinned now by tests that repoint the source. |
| 2 | SC#5 "runtime context" — time / device name / room (PERS-03) | Phase 10 | REQUIREMENTS.md traceability: `PERS-03 | Phase 10 — The Appliance`. Plan 03-07 scoped SC#5 on this basis. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/paaf-llm/src/paaf_llm/profiles.py` | ModelProfile + LlmConfig with cross-ref validator, endpoint() | ✓ VERIFIED | 168 lines. Reuses `paaf_core.config.schema.ReloadTier` and `paaf_core.net.endpoint.Endpoint` (not reinvented). `extra="forbid"` on both models, exercised by two rejection tests. |
| `packages/paaf-llm/src/paaf_llm/compose.py` | Segment + segments()/compose() | ✓ VERIFIED | 86 lines, stdlib-only, no PAAF imports. `join(segments) == compose()` invariant asserted. |
| `packages/paaf-llm/src/paaf_llm/ports.py` | Message/Usage/TurnResult/FallbackReason/AdapterError×4/AllProvidersFailed/ChatAdapter | ✓ VERIFIED | 209 lines, zero framework imports (asserted against the source text AND by import-linter). `handoff` Phase-4 seam present and always None. |
| `packages/paaf-llm/src/paaf_llm/fake/__init__.py` | FakeAdapter.program()/stream()/last_usage() | ✓ VERIFIED | 171 lines. Un-programmed profile raises `LookupError` (deliberately not an AdapterError) — that choice is what makes `test_manifest_performs_no_handoff` a real control. |
| `packages/paaf-llm/src/paaf_llm/agent.py` | ordered fallback, first-token deadline, history, trace drain | ✓ VERIFIED | 296 lines. `asyncio.timeout` wraps only the first `__anext__`; `aclose()`d on timeout; history appended only after a served turn. |
| `packages/paaf-llm/src/paaf_llm/cli.py` | chat + prompt + --show-prompt + --provenance + manifest + fallback notice | ⚠️ HOLLOW (partial) | 327 lines, all commands work. But two production wirings are absent: no secret store reaches the engine adapter, and no trace sink reaches the agent. Both parameters exist and are unit-tested; neither is ever supplied. |
| `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` | LangChainAdapter + build_engine_adapter | ✓ VERIFIED | 585 lines. `find_spec` import guard (imports nothing), lazy `_framework()`, no httpx import, structural exception classification with a bounded cause-chain walk, secret scrubbing. |
| `packages/paaf-trace/.../schema.sql` + `store.py` | additive served_by + fallback_trail | ✓ VERIFIED | Both columns present and TEXT; `RunEvent` carries them; INSERT widened. Round-trip test writes through a real store and reads the real SQLite file back. |
| `.importlinter` | provider modules forbidden + `_engine` whitelist | ✓ VERIFIED | 3 contracts kept, 0 broken (run twice: with and without the `[engine]` extra). |
| `tests/negcontrol/paaf_llm_provider_violation/` | fixture that turns the provider contract red | ✓ VERIFIED | 5 negcontrol tests pass; the `langchain_provider` contract exits nonzero on the fixture. |
| `scripts/check_framework_uninstalled.sh` | SC#1 clean-venv gate | ✓ VERIFIED | Executed. PASS. Also asserts the shipped test set matches the source set, so the gate cannot rot into three smoke assertions. |
| `.github/workflows/framework-uninstalled.yml` | SC#1 CI gate | ✓ VERIFIED | Runs the script on push+PR. |
| `.github/workflows/engine-adapter.yml` | complementary framework-PRESENT gate | ✓ VERIFIED | Installs `[engine]`, asserts the framework really imported (anti-silent-skip step), runs the 26 adapter tests, then the whole suite. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli.prompt` | `compose.PromptComposer.compose` | direct call, same `load_skill_fragments` source | ✓ WIRED | Byte-identity asserted against the message the adapter received, not just against a second call to the same function. |
| `cli.chat --show-prompt` | `agent.Agent.system_prompt` | direct call | ✓ WIRED | `test_show_prompt_echoes_what_was_sent` compares against `adapter.calls[0]`. |
| `cli.chat` | `agent.Agent.turn` | `build_agent` → `Agent.build` | ✓ WIRED | Multi-turn stdin loop tested (`test_multi_turn_conversation_continues_across_a_hop`). |
| `cli._default_adapter` | `_engine.build_engine_adapter` | lazy in-function import | ✓ WIRED | Laziness asserted three ways: source-text indentation check, in-process `sys.modules` probe, pristine-subprocess probe. |
| `cli._default_adapter` | `paaf_core` SecretStore | `build_engine_adapter(config, secret_store=…)` | ✗ NOT_WIRED | The parameter is never passed. Every `api_key_ref` profile is unusable from the CLI. **Gap 1.** |
| `cli.chat` | `paaf_trace.TraceStore` | `build_agent(..., trace=…)` | ✗ NOT_WIRED | `chat` calls `build_agent(config)` with no sink → `Agent._drain` returns immediately. No run is ever persisted in production use. 03-07's SUMMARY assigned this to plan 03-09; 03-09's `files_modified` does not include `cli.py`. **Warning.** |
| `agent._run_chain` | `ports.AdapterError.reason` | `except AdapterError as exc: trail.append(..., exc.reason.value)` | ✓ WIRED | Classification by reason, never by foreign exception type. |
| `agent._drain` | `paaf_trace.store.RunEvent` | `self._trace.emit(RunEvent(...))` | ✓ WIRED | Verified by reading rows back out of a real SQLite file. |
| `_engine.LangChainAdapter.base_url` | `paaf_core.net.endpoint.Endpoint` | `profile.endpoint()` | ⚠️ PARTIAL | Same Endpoint the offline registry classifies is the one dialed — good. But it carries no path, so `/v1` is unreachable. **Gap 1.** |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cli.render_profiles` | `config.profiles` | YAML → `LlmConfig.model_validate` | Yes — confirmed by running `paaf profiles` on a hand-written 3-provider YAML | ✓ FLOWING |
| `cli.prompt` | `config.base_prompt` + `fragments` | YAML + `load_skill_fragments` | Base prompt: yes. Fragments: **`[]` by design (D-09)** | ⚠️ STATIC (deferred to Phase 6) |
| `cli._chat_loop` | `result.text` / `result.served_by` / `result.fallback_trail` | `Agent.turn` → adapter stream | Yes | ✓ FLOWING |
| `Agent._drain` → trace DB | `RunEvent` | `self._trace` | **`None` in the CLI path** — no run row is ever written by `paaf chat` | ✗ DISCONNECTED (warning) |
| `LangChainAdapter.model_kwargs` | `api_key` | `self._secret_store.get(ref)` | **`self._secret_store` is `None` in the CLI path** | ✗ DISCONNECTED (gap) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full workspace suite (no extra) | `uv run pytest -q --disable-socket` | 174 passed, 1 skipped (the skip is `test_engine_adapter.py::importorskip langchain`) | ✓ PASS |
| Full workspace suite (with extra) | `uv sync --all-packages --extra engine && uv run pytest -q --disable-socket` | 200 passed, 0 skipped | ✓ PASS |
| Real-adapter translation seam | `uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` (extra installed) | 26 passed, 0 skipped | ✓ PASS |
| Import boundary | `uv run lint-imports --no-cache` (run with AND without the extra) | 3 contracts kept, 0 broken. With the extra installed the `_engine -> langchain` and `_engine -> langchain_core` whitelist entries MATCH, proving the carve-out is load-bearing rather than decorative | ✓ PASS |
| Negative controls bite | `uv run pytest tests/negcontrol/test_import_boundary.py -q` | 5 passed | ✓ PASS |
| SC#1 gate | `bash scripts/check_framework_uninstalled.sh` | PASS — 102 passed in a clean off-repo venv, langchain+langgraph unimportable | ✓ PASS |
| Wheel independence | `bash scripts/check_wheel_independence.sh` | PASS — paaf_voice and langchain both absent | ✓ PASS |
| `paaf prompt` byte-exactness | `uv run paaf prompt --config <yaml> \| od -c` | Output ends `p l a i n l y .` with **no trailing newline** | ✓ PASS |
| `paaf prompt --provenance` | `uv run paaf prompt --config <yaml> --provenance` | `--- base ---` + the verbatim base prompt | ✓ PASS |
| `paaf profiles` manifest surface | `uv run paaf profiles --config <yaml>` | All 3 profiles, capabilities, peers, constraints, active/fallback roles, and the inert-graph note | ✓ PASS |
| `paaf chat` against real providers | `echo hello \| uv run paaf chat --config <yaml>` | **Unhandled `EngineError` traceback.** First run: `could not bind 'openai:qwen3:32b': Missing credentials`. Second run: `profile declares api_key_ref 'anthropic_key' but no secret store was provided`. Notably the Ollama profile DID degrade correctly and the loop DID advance — real-socket ConnectionFailed translation works | ✗ FAIL |
| `paaf chat` with env-var credential | `ANTHROPIC_API_KEY=… uv run paaf chat --config <yaml>` | Reached the real Anthropic API and returned a genuine `401 invalid x-api-key`. The Anthropic binding works over the wire — but only via the SDK env var, bypassing PAAF's SecretStore | ⚠️ PARTIAL |
| Lint | `uv run ruff check packages/paaf-llm packages/paaf-trace scripts tests` | 2 errors, both the pre-existing `PLW1510` in `tests/negcontrol/test_import_boundary.py`. **No new findings from this phase's code**; the `test_wheel_smoke.py` I001 noted in `deferred-items.md` is now clean | ✓ PASS |

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/check_framework_uninstalled.sh` | `bash scripts/check_framework_uninstalled.sh` | exit 0, "PASS: the full paaf-llm fake-adapter suite passes with the agent framework uninstalled" | PASS |
| `scripts/check_wheel_independence.sh` | `bash scripts/check_wheel_independence.sh` | exit 0, "PASS: paaf-llm installs with its framework deps but WITHOUT the agent framework or paaf-voice" | PASS |

No `scripts/*/tests/probe-*.sh` exist in this repo; the two shell gates above are this phase's equivalent and both were executed by the verifier, not read from a SUMMARY.

### Requirements Coverage

Requirement IDs declared across the 9 plans' frontmatter: MODEL-01/02/03/04/05/06/08, PERS-01/02/04/05. **This is exactly the ROADMAP phase set — no orphaned and no undeclared IDs.**

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| MODEL-01 | 03-01, 03-08 | Named model profiles — provider, model, endpoint, params — with no code | ✓ SATISFIED | `ModelProfile` + `LlmConfig`; YAML loaded end-to-end by `paaf prompt`/`profiles`/`chat` |
| MODEL-02 | 03-08, 03-09 | Ollama, OpenAI-compatible, Anthropic | ✗ BLOCKED (partial) | Provider-string table + schema/table drift control pass. Ollama binds and reaches a real socket. Anthropic reaches the real API only via an SDK env var. **OpenAI-compatible cannot bind unauthenticated and cannot address a `/v1` server; no test binds one.** |
| MODEL-03 | 03-06 | Ordered fallback chain surviving an unreachable provider mid-conversation | ✓ SATISFIED (fake) + human verify | `test_fallback_connection` proves the hop AND that history carries across AND that the chain restarts from the active profile each turn. Real WAN pull → human. |
| MODEL-04 | 03-02, 03-06, 03-09 | Fallback on a degraded-but-reachable provider, not only a hard error | ✓ SATISFIED | Four triggers parametrized; `test_every_fallback_reason_has_a_trigger_in_this_file` and `test_adapter_error_subclasses_are_all_exercised` make the coverage non-vacuous |
| MODEL-05 | 03-01, 03-07 | Capability manifest + peer graph in YAML, no code | ✓ SATISFIED | Free-text manifest, validated peer graph, surfaced by two commands, inertness negatively controlled |
| MODEL-06 | 03-01, 03-08 | Same-provider multiple endpoints as distinct profiles | ✓ SATISFIED | Asserted at three levels: derived URL, cache identity, and the `base_url` on the actually-bound framework client. Plus the subtle control that two endpoint-less cloud profiles do not collide in the cache |
| MODEL-08 | 03-03, 03-05, 03-06, 03-08, 03-09 | Public API exposes only PAAF types, proven with the framework uninstalled | ✓ SATISFIED | The strongest requirement in the phase. Signature walker + its own vacuity control + positive control that it reached real annotations; pristine-subprocess import probes; import-linter with a biting negcontrol; and the clean-venv wheel gate I ran myself |
| PERS-01 | 03-04, 03-07 | User writes a base system prompt | ✓ SATISFIED | `LlmConfig.base_prompt`, surfaced verbatim |
| PERS-02 | 03-04, 03-07 | Active skills contribute persona fragments | ⚠️ PARTIAL | The composition contract is real and byte-tested; **no skill source exists** (`load_skill_fragments` → `[]`). Deferred to Phase 6 SC#2 |
| PERS-04 | 03-07 | Final composed prompt inspectable verbatim, exactly as sent | ✓ SATISFIED | Three-way byte identity including the message that crossed the port |
| PERS-05 | 03-04, 03-07 | PAAF never injects instructions the user did not write | ✓ SATISFIED | `test_no_hidden_prompt` splits the output back apart; `test_prompt_adds_no_text_of_its_own` reconstructs from raw inputs independent of the composer |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | `TODO` / `FIXME` / `XXX` / `TBD` / `HACK` / `PLACEHOLDER` | — | **None found** in any file this phase modified. The debt-marker gate is clean. |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 103-111 | `load_skill_fragments` returns `[]` | ℹ️ Info | A documented, named seam (D-09), not a hidden stub. The docstring explains why it is a function rather than an inline `[]`, and Phase 6 replaces the body. Not classified as a stub: it is the deliberate deferral point and the fragment path is proven by repointing it. |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 138 | `build_engine_adapter(config)` — optional `secret_store` silently omitted | 🛑 Blocker | See Gap 1. |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 284 | `build_agent(config)` — optional `trace` silently omitted | ⚠️ Warning | See "Additional Warnings". |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 244-247 | Only `AllProvidersFailed` handled | 🛑 Blocker | See Gap 2. |
| `tests/negcontrol/.importlinter-negcontrol` | 48-58 | `langchain_provider` contract omits the real config's `ignore_imports` whitelist | ℹ️ Info | The negcontrol proves a forbidden contract bites on a non-`_engine` importer, but does not directly prove the REAL config's whitelist cannot rescue one. Mitigated: the whitelist names `paaf_llm._engine` / `paaf_llm._engine.**` exactly (read directly), and it demonstrably matched the real `_engine -> langchain` edge once the extra was installed. Low risk. |

### Human Verification Required

#### 1. WAN pull mid-conversation (SC#3)

**Test:** Configure a real cloud profile as `active_profile` with a real local Ollama profile in `fallback_chain`. Start `paaf chat`, send one turn successfully, physically disconnect the WAN, send a second turn.
**Expected:** The second turn prints `↳ fell back to <local> (connection)`, is answered by the local model, and the local model's reply shows it received the first turn's history.
**Why human:** No test in the repo contacts a real provider (`--disable-socket` is a suite-wide default by design). Cutting a WAN link is a physical state change no automated check here can produce.

#### 2. Cold-model first-token budget (MODEL-04 / D-05)

**Test:** Cold-start a 14B Ollama model and send the first turn of a session.
**Expected:** No spurious `slow_first_token` fallback inside the configured `first_token_budget_s` — `warmup()`/`preload()` absorbs the cold-load cost.
**Why human:** Timing against a real cold-loading model cannot be asserted deterministically offline. Already listed as Manual-Only in `03-VALIDATION.md`.

#### 3. Real single-provider round-trip (MODEL-01/02)

**Test:** With Ollama running, point a profile at it and hold a two-turn conversation via `paaf chat`.
**Expected:** Both turns answer; the second shows the model saw the first.
**Why human:** Requires a live provider. (Partial evidence already collected: `paaf chat` reached the real Anthropic API and returned a genuine `401`, so the transport path is live — but no successful completion was ever observed.)

#### 4. Two physical LAN servers (MODEL-06)

**Test:** Point two Ollama profiles at two DIFFERENT physical LAN machines and confirm each is served by its own box.
**Expected:** `ollama ps` on each machine (or distinct model names) confirms which server ran.
**Why human:** Proven at the binding level (two clients, two `base_url`s) but never against two real servers.

---

## Gaps Summary

This phase is unusually well engineered. The test suite is not decorative: nearly every positive assertion is paired with a negative control that would catch the obvious cheat (an engine that always falls back; a deadline that wraps the whole stream instead of the first token; a signature walker that inspects nothing; a coverage list that silently misses a new enum member; an inspector that calls the composer twice instead of reading what crossed the port). MODEL-08 in particular is proven harder than the requirement asks — I executed the clean-venv gate myself and watched 102 tests pass with `langchain` genuinely unimportable. SC#1, SC#4 and SC#5 hold up under adversarial reading.

The gaps are all in one place, and they share one shape: **the shipped `paaf chat` command does not wire the optional collaborators the library so carefully accepts.**

**Gap 1 — `paaf chat` cannot use PAAF's own credential mechanism (blocks SC#2).**
`LangChainAdapter.__init__` takes a `secret_store`; `build_engine_adapter` takes a `secret_store`; `Agent.__init__` takes a `secret_store`. `paaf_core` ships a working `EncryptedFileSecretStore`. `ModelProfile.api_key_ref` exists precisely so the key value never touches YAML (CORE-04), and it is thoroughly unit-tested. And yet `cli._default_adapter` calls `build_engine_adapter(config)` with one argument, so in every real invocation `self._secret_store is None` and **any** profile declaring `api_key_ref` dies at bind. I reproduced this twice. The only credential path that actually works from `paaf chat` today is the provider SDK's own environment variable — which is the exact thing `api_key_ref` was built to replace. SC#2 names Anthropic explicitly; Anthropic is the provider most likely to need a key.

This is a one-line-plus-a-test fix, not a design flaw — which is why it should be closed rather than overridden.

**Gap 2 — `EngineError` escapes `paaf chat` as a raw traceback.**
`_chat_loop` catches only `AllProvidersFailed`. `EngineError` is by the engine's own design the class for the most common real first-run failure (missing credential, wrong model name) — deliberately *not* an `AdapterError` so the fallback loop cannot swallow it. But nothing else catches it either, so the user sees a 30-line Python traceback. The same hole covers a post-first-token `AdapterError` (the engine intentionally does not catch those after commit). For a phase whose whole thesis is "nothing hidden from the user, readable output," a traceback on the headline command is worth closing.

**Adjacent to SC#2, lower confidence on severity:** `paaf_core.Endpoint` has no path field, so an OpenAI-compatible server at `http://host:8080/v1` cannot be declared — that is where vLLM, llama.cpp's server and LM Studio actually serve, and the project's own tech-stack doc names all three. Plan 03-08 documented this rather than silently appending a suffix, which is the right call on the *hidden-behavior* axis. But the consequence is that the "OpenAI-compatible endpoints" leg of SC#2 is largely theoretical: combined with the missing unauthenticated-bind path, there is currently no working configuration for a local OpenAI-compatible server. It is also the one provider with zero binding-level test coverage, which is very likely why neither failure was noticed. This deserves an explicit maintainer decision: fix it, or record it in ROADMAP/REQUIREMENTS as an accepted Phase-3 limitation rather than leaving it only in a plan SUMMARY.

### Additional Warnings (not gaps)

- **`paaf chat` never writes a trace row.** Plan 03-02 added `served_by` + `fallback_trail` to the `runs` table and plan 03-06 drains them from `Agent`; both are verified against a real SQLite file. But `chat` calls `build_agent(config)` with no `trace=` sink, so `Agent._drain` returns immediately and nothing is persisted in production use. 03-07's SUMMARY explicitly assigned this wiring to plan 03-09 ("trace wiring is plan 03-09's"); 03-09's `files_modified` does not include `cli.py`. The seam is real, the wiring is missing — a wave-handoff dropped item, not a design flaw.
- **`paaf chat` prints the completed reply rather than streaming tokens.** Recorded as a Known Stub by 03-07 and accurate: `Agent.turn` aggregates and exposes no token iterator. Not required by any Phase-3 success criterion; flagged because the project's TTS design depends on token streaming later.
- **Phase mode/goal mismatch.** ROADMAP declares `Mode: mvp` but the goal is not a User Story. Reconcile with `/gsd mvp-phase 3` or drop the mode marker.
- **Verifier side effect, disclosed:** during behavioral spot-checks I ran `paaf chat` with `ANTHROPIC_API_KEY=sk-ant-fake`, which made one outbound request to `api.anthropic.com` that was rejected with a 401. No credential was used and no billable work occurred. The workspace venv was restored to `uv sync --all-packages` (no `[engine]` extra) afterwards and the suite re-confirmed at 174 passed / 1 skipped.

---

_Verified: 2026-08-06_
_Verifier: Claude (gsd-verifier)_
