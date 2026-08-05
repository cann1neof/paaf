---
phase: 03-paaf-llm-core
plan: 08
subsystem: adapter
tags: [langchain, adapter, provider-binding, exception-translation, optional-extra, secrets, import-linter]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "plan 03-05's ChatAdapter port + the four AdapterError subclasses this adapter translates into, and the FakeAdapter whose shape it mirrors"
  - phase: 03-paaf-llm-core
    provides: "plan 03-01's ModelProfile/LlmConfig (provider, model, endpoint(), api_key_ref, temperature) and paaf-llm's pyproject"
  - phase: 03-paaf-llm-core
    provides: "plan 03-03's corrected import-linter whitelist — the 14 explicit edges that make this adapter's imports legal"
  - phase: 03-paaf-llm-core
    provides: "plan 03-06's Agent.warmup() preload hook and fallback loop; plan 03-07's cli._default_adapter contract"
  - phase: 02-core-software
    provides: "paaf_core.net.endpoint.Endpoint (base_url derivation) and paaf_core.secrets.SecretStore (api key by reference)"
provides:
  - "LangChainAdapter — the real ChatAdapter over init_chat_model, binding ollama / openai_compatible / anthropic profiles"
  - "build_engine_adapter(config, secret_store=None) — the factory cli._default_adapter already imports lazily; `paaf chat` goes live with zero CLI changes"
  - "Structural exception translation: HTTP status, then exception type name, then builtin type, walked over the __cause__ chain, into the four PAAF AdapterError subclasses"
  - "EngineError — PAAF-typed, deliberately NOT an AdapterError, for config errors and unclassifiable failures"
  - "LangChainAdapter.preload — the hook Agent.warmup() calls via getattr, no longer a no-op against a real provider"
  - "paaf-llm[engine] optional extra with exact version pins"
  - "Two order-independent pristine-interpreter guards replacing two order-dependent sys.modules assertions"
affects: [03-09-trace-wiring, 04-agent-mesh, 05-tools-mcp]

# Tech tracking
tech-stack:
  added:
    - "langchain==1.3.14 (optional [engine] extra)"
    - "langgraph==1.2.10 (optional [engine] extra)"
    - "langchain-ollama==1.1.0 (optional [engine] extra)"
    - "langchain-anthropic==1.4.8 (optional [engine] extra)"
    - "langchain-openai==1.4.1 (optional [engine] extra)"
  patterns:
    - "find_spec() availability probe at module scope + the real framework import inside a function: keeps the adapter lazy while still failing at the import statement the CLI wraps in `except ImportError`"
    - "Duck-typed exception classification (status -> type name -> builtin type, over the __cause__ chain) so the adapter recognizes three provider SDKs without importing any of them"
    - "Two-tier failure taxonomy: AdapterError means 'degraded, try the next profile'; a separate non-AdapterError means 'config error, do not hide this behind a fallback'"
    - "Cache key built from the PROFILE (api_key_ref, not the key value) so a secret never becomes a dict key"
    - "Pristine-interpreter probes for import-graph guards — a sys.modules assertion over the running pytest process measures the session, not the package"

key-files:
  created:
    - packages/paaf-llm/tests/test_engine_adapter.py
  modified:
    - packages/paaf-llm/src/paaf_llm/_engine/__init__.py
    - packages/paaf-llm/pyproject.toml
    - pyproject.toml
    - uv.lock
    - packages/paaf-llm/tests/test_no_leak.py
    - packages/paaf-trace/tests/test_trace_no_egress.py

key-decisions:
  - "Exceptions are classified structurally (status code, type name, builtin type) rather than by importing openai/anthropic/ollama exception classes — importing three optional SDKs to do a job duck-typing does would put them in this module's import graph. The guess is validated against 13 real SDK exception instances so the structural assumption is tested, not assumed."
  - "An unclassifiable failure raises EngineError, not an AdapterError. A missing key or a wrong model name is not a degraded provider, and translating it into a fallback reason would print '↳ fell back to cloud (connection)' at a user whose real problem is a typo."
  - "Module scope probes find_spec('langchain') and raises ImportError when the extra is absent. Without it, cli._default_adapter's friendly 'install the extra' handler — which wraps only the import statement — could never fire, and the user would get a bare ModuleNotFoundError mid-conversation."
  - "The model cache key includes temperature and api_key_ref, not just provider+base_url: two Anthropic profiles on one model both declare no endpoint and would otherwise collide, the second silently inheriting the first's temperature and credential."
  - "preload() only warms providers that actually have a cold load (ollama). Preloading a hosted model would spend the user's tokens on every `paaf chat` start to warm something that was never cold."
  - "Empty stream chunks are dropped rather than yielded, so the engine's first-token deadline measures real content; yielding '' would satisfy the budget with nothing."
  - "Token text is coerced with str(): AIMessageChunk.text is a framework TextAccessor (a str subclass), and letting one cross the port would leak a framework type through a PAAF-typed stream."
  - "langchain-anthropic pinned at 1.4.8 rather than the 1.5.4 published hours before the pin was chosen — a same-day release is the window a compromised publish goes undetected in, and 1.4.x is the researched range."
  - "The OpenAI-compatible /v1 path problem is documented, NOT silently patched: Endpoint carries no path, and auto-appending a suffix to a user's declared endpoint is exactly the hidden behavior this project refuses."

patterns-established:
  - "Adapter-level negative controls: the classifier is proven to DECLINE on an unrecognized error, not only to succeed on recognized ones"
  - "Import-graph guards probe a child interpreter, so they survive a sibling test legitimately importing the thing they forbid"

requirements-completed: [MODEL-01, MODEL-02, MODEL-06, MODEL-08]

coverage:
  - id: D1
    description: "Named YAML profiles bind to real Ollama, OpenAI-compatible, and Anthropic providers through init_chat_model behind the unchanged port"
    requirement: MODEL-01, MODEL-02
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_provider_string_covers_every_declared_provider"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_every_schema_provider_has_a_binding"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_build_engine_adapter_is_the_factory_the_cli_imports"
        status: pass
      - kind: manual
        ref: "03-VALIDATION.md Manual-Only — live round-trip against a real Ollama box and real cloud keys"
        status: pending
    human_judgment: true
  - id: D2
    description: "Two same-provider LAN Ollama profiles bind to distinct base_urls, so two local servers serve as distinct profiles"
    requirement: MODEL-06
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_two_lan_profiles_distinct_base_urls"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_two_cloud_profiles_on_one_model_do_not_share_a_binding"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every framework/transport failure becomes the PAAF AdapterError subclass carrying the right FallbackReason, so the proven fallback loop works over real providers"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_exception_translation"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_translation_matches_the_real_provider_exception_types"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_wrapped_transport_failure_is_still_classified"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_an_unclassifiable_failure_is_not_turned_into_a_fallback_reason"
        status: pass
    human_judgment: false
  - id: D4
    description: "langchain lives ONLY inside paaf_llm._engine, is imported lazily, is an optional extra, and the adapter imports no httpx"
    requirement: MODEL-08
    verification:
      - kind: integration
        ref: "uv run lint-imports (3 contracts kept, 0 broken; langchain-confined-to-adapter now matches 2 real edges)"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_importing_paaf_llm_still_loads_no_framework"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_engine_module_refuses_to_import_without_the_extra"
        status: pass
      - kind: integration
        ref: "bash scripts/check_wheel_independence.sh (exit 0; langchain not importable from the wheel without the extra)"
        status: pass
      - kind: integration
        ref: "PYTHONPATH shim hiding langchain => test_engine_adapter.py collects as 1 skipped"
        status: pass
    human_judgment: false
  - id: D5
    description: "API keys resolve by reference through the SecretStore and never reach YAML, a log, or an error string"
    requirement: MODEL-02
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_api_key_is_resolved_by_reference_not_read_from_config"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_resolved_key_never_appears_in_a_raised_message"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_an_unresolvable_key_reference_is_a_config_error_not_a_fallback"
        status: pass
    human_judgment: false
  - id: D6
    description: "Usage is read after stream aggregation, and preload implements the hook Agent.warmup() calls"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_usage_is_read_after_aggregation"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_usage_stays_none_when_the_provider_reported_none"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_preload_warms_a_local_model_and_skips_a_hosted_one"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_preload_survives_a_provider_that_is_down"
        status: pass
    human_judgment: false

# Metrics
duration: 71min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 08: The Real LangChain Adapter Summary

**`LangChainAdapter` binds Ollama, OpenAI-compatible, and Anthropic profiles through `init_chat_model` behind the unchanged port, translating every provider failure into the PAAF exception the proven fallback loop already handles — while `langchain` stays an optional, exactly-pinned, lazily-imported extra confined to `paaf_llm._engine`.**

## Performance

- **Duration:** ~71 min
- **Tasks:** 3 (3 commits)
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- **`paaf chat` is live against real models with zero CLI changes.** `build_engine_adapter(config)` is exported with exactly the name and signature plan 03-07's `cli._default_adapter` already imports, lazily. The port did not move: `LangChainAdapter` satisfies `isinstance(adapter, ChatAdapter)` and the engine cannot tell it from the fake.
- **MODEL-06 works at the level that matters.** Two Ollama profiles at `.10` and `.11` produce two distinct `base_url`s, two distinct cache identities, and two distinct bound `ChatOllama` objects — asserted at all three levels, because only the third proves the user's second box is actually dialed.
- **The fallback loop now works over real providers without a line changing in it.** Every transport failure is classified into one of the four `AdapterError` subclasses, so `agent.py` still classifies a hop by reading `.reason`.
- **The classifier is validated against the real SDKs, not against my idea of them.** 13 genuine exception instances from `ollama`, `openai`, `anthropic`, and `httpx` are asserted to classify correctly — including the two subclass-ordering traps (`httpx.ConnectTimeout` and `openai.APITimeoutError` both subclass a *connection* error, so testing connection first would silently reclassify every timeout).
- **The phase's headline property survives.** `bash scripts/check_wheel_independence.sh` passes: `pip install paaf-llm` without the extra installs, runs its smoke suite, and `import langchain` raises `ModuleNotFoundError`. Verified separately that `test_engine_adapter.py` collects as **1 skipped** when `langchain` is unavailable.
- **`Agent.warmup()` is no longer a no-op.** `preload` exists with the `async def preload(self, profile)` signature 03-06 calls through `getattr`.

## Task Commits

1. **Task 2 — the `[engine]` extra with exact pins** — `1b8065d` (chore)
2. **Task 1 — `LangChainAdapter`** — `105fcde` (feat)
3. **Task 3 — guarded adapter tests** — `da2bdfd` (test)

Tasks 1 and 2 were executed in the reverse of the plan's listed order, because Task 1's own action requires verifying `init_chat_model`'s symbol path "against the installed version" — which needs Task 2's extra installed first. No task content changed.

## Pinned Versions (Task 2 requirement)

Verified against the PyPI JSON API on 2026-08-05:

| Package | Pinned | Latest at pin time | Note |
|---------|--------|--------------------|------|
| `langchain` | **1.3.14** | 1.3.14 | latest stable in the researched `~=1.3` range |
| `langgraph` | **1.2.10** | 1.2.10 | latest stable in `~=1.2` |
| `langchain-ollama` | **1.1.0** | 1.1.0 | latest stable in `~=1.1` |
| `langchain-anthropic` | **1.4.8** | 1.5.4 | held at newest `1.4.x` — see below |
| `langchain-openai` | **1.4.1** | 1.4.1 | the "verify at plan time" entry, resolved |

`langchain-anthropic` 1.5.4 published at 2026-08-05T19:03 — hours before this pin was chosen. A same-day release is precisely the window in which a compromised publish is still undetected, and `~=1.4` is the range the phase's research recommended, so the newest `1.4.x` was taken instead. Bumping it later is a deliberate, reviewable edit rather than a silent range resolution.

All five resolve together (`langchain-core` 1.5.3 transitively). The full family is MIT.

## Files Created/Modified

- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` (modified, +582) — `LangChainAdapter` (`provider_string`, `base_url`, `api_key`, `model_kwargs`, `cache_key`, `bind`, `stream`, `last_usage`, `preload`), `build_engine_adapter`, `classify`, `EngineError`, and the `_framework()` lazy-import site. The marker docstring's stale import-linter shorthand was corrected per plan 03-03's handoff.
- `packages/paaf-llm/pyproject.toml` (modified) — `[project.optional-dependencies] engine`, exact pins. `[project.scripts]`, `[tool.uv.sources]`, and the hatch `force-include` block are untouched.
- `pyproject.toml` (root, modified) — `-p no:langsmith_plugin` in `addopts` (deviation 1).
- `uv.lock` (modified) — regenerated so the extra resolves reproducibly in CI.
- `packages/paaf-llm/tests/test_engine_adapter.py` (created) — 26 tests behind `importorskip`.
- `packages/paaf-llm/tests/test_no_leak.py` (modified) — one guard made order-independent (deviation 2).
- `packages/paaf-trace/tests/test_trace_no_egress.py` (modified) — same (deviation 2).

## Decisions Made

- **Duck-typed exception classification over importing the provider SDKs.** Importing `openai`, `anthropic`, and `ollama` to catch their exception classes would place three optional dependencies in this module's import graph to do a job that reading a status code and a type name does. The obvious risk — that the assumed structure is wrong — is retired by `test_translation_matches_the_real_provider_exception_types`, which asserts against real instances of all 13 failure modes.
- **`EngineError` is not an `AdapterError`.** The four PAAF errors mean "this provider degraded, try the next one". A missing credential, an unmappable provider, or an unrecognized failure is a *configuration* error. Translating it into a fallback reason would report `↳ fell back to cloud (connection)` to someone whose real problem is a typo — the fallback chain would quietly mask the thing the user has to fix. `EngineError` is still PAAF-typed, so no framework exception crosses the port.
- **A `find_spec` probe at module scope.** Plan 03-07's `_default_adapter` wraps only its `from ._engine import build_engine_adapter` statement in `except ImportError`. A fully lazy `_engine` imports cleanly without the extra, so that handler could never fire and the user would meet a bare `ModuleNotFoundError` at their first turn instead of "install it with `pip install 'paaf-llm[engine]'`". `find_spec` executes no framework code, so the module stays lazy while the CLI's message stays reachable.
- **The cache key is built from the profile, not from the resolved kwargs.** This keeps the secret VALUE from ever becoming a dict key — `api_key_ref` (a name) distinguishes two credentials without holding either.
- **`preload` warms only local providers.** The two-clock rationale (Pitfall 2) is explicitly about a cold *local* model. A hosted model has no cold load, so preloading one spends real tokens and real money on every session start for no latency gain.
- **The `/v1` path gap is documented, not patched.** See "Deferred Issues".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] LangSmith's pytest plugin loads httpx/requests into every test process**

- **Found during:** Task 2, immediately after installing the extra
- **Issue:** `langsmith` arrives transitively with `langchain` and auto-registers a `pytest11` entry point. pytest loads it before any test runs, pulling `httpx`, `requests`, and `urllib3` into `sys.modules` — which turned `paaf-trace`'s TRACE-05 `test_no_http_client_in_import_graph` red. Two distinct problems: a false failure, and the LangSmith cloud machinery this project explicitly refuses being loaded into every test process without anyone asking for it.
- **Fix:** `-p no:langsmith_plugin` in the root `pyproject.toml` `addopts`. Fixing the cause rather than making the privacy guard tolerate an HTTP client, which would have weakened it. `-p no:` on an absent plugin name is ignored, so the framework-uninstalled suite is unaffected.
- **Files modified:** `pyproject.toml`
- **Verification:** suite returns to 174 passed with the extra installed.
- **Committed in:** `1b8065d`

**2. [Rule 1 - Bug] Two import-graph guards measured the pytest session, not their package**

- **Found during:** Task 3
- **Issue:** `test_no_leak.py::test_import_paaf_llm_needs_no_framework` and `test_trace_no_egress.py::test_no_http_client_in_import_graph` both assert over the *running process's* `sys.modules`. That answers "has anything in this session imported X?", not "does importing this package import X?" — so both went red the moment this plan's tests legitimately imported the framework, while `paaf_llm` and `paaf_trace` themselves stayed perfectly clean. The guards were order-dependent and would have failed for plan 03-09's engine-installed CI job too. `test_no_leak.py` already documented its pristine-interpreter twin as "immune to another test's imports", which is the correct shape.
- **Fix:** Both now probe a child interpreter and filter its module list. `test_no_leak.py` still routes through the shared `_framework_modules` detector so the existing `..._is_not_vacuous` negative control keeps guarding the assertion; `test_trace_no_egress.py` gained a positive control (`paaf_trace.store` really was imported) so its absence assertion cannot pass on a child that died early.
- **Files modified:** `packages/paaf-llm/tests/test_no_leak.py`, `packages/paaf-trace/tests/test_trace_no_egress.py`
- **Verification:** both re-verified to still go red on a planted violation — a probe that also imports `httpx` reports `['httpx']`, and one that also imports `langchain` reports a non-empty framework set.
- **Committed in:** `da2bdfd`

**3. [Rule 1 - Bug] The model cache collapsed two distinct cloud profiles into one binding**

- **Found during:** Task 1 (self-review before commit)
- **Issue:** The first cache key was `(provider_string, base_url)`. Two Anthropic profiles naming the same model both declare no endpoint, so they collided and the second silently inherited the first's temperature and credential. Silent, and it would have looked like the config simply had no effect.
- **Fix:** `cache_key(profile)` includes `temperature` and `api_key_ref` (the name, never the value).
- **Files modified:** `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- **Verification:** `test_two_cloud_profiles_on_one_model_do_not_share_a_binding`
- **Committed in:** `105fcde`

**4. [Rule 2 - Missing Critical] `temperature` was not reaching the provider**

- **Found during:** Task 1
- **Issue:** The plan's provider-mapping spec names only `base_url` and `api_key`. `ModelProfile.temperature` is a documented, user-owned, WARM-tier knob; not passing it would make a setting the user can edit do nothing.
- **Fix:** `model_kwargs` passes `temperature=profile.temperature`.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- **Committed in:** `105fcde`

**5. [Rule 2 - Missing Critical] Framework `TextAccessor` would have crossed the PAAF port**

- **Found during:** Task 1 (probing the installed `langchain-core` 1.5.3)
- **Issue:** `AIMessageChunk.text` returns a `langchain_core.messages.base.TextAccessor`, a `str` *subclass*. Yielding it would satisfy every `== "hello"` assertion while leaking a framework type through a stream the port promises is PAAF-typed — exactly the MODEL-08 leak `test_no_leak.py` exists to catch, in the one place that walker cannot see (a runtime value, not an annotation).
- **Fix:** tokens are coerced with `str()`; `test_streams_plain_str_tokens_and_maps_the_roles` asserts `type(token) is str`.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- **Committed in:** `105fcde`

### Sequencing Deviation

Tasks 1 and 2 were committed in the order 2 → 1. Task 1's action requires verifying `init_chat_model`'s exact symbol path "against the installed version", which is only possible once Task 2's extra is installed. Nothing about either task's content changed.

**Total deviations:** 5 auto-fixed (3 bugs, 2 missing-critical) + 1 sequencing
**Impact on plan:** No plan artifact was skipped or substituted. Deviations 1 and 2 touch files outside this plan's `files_modified`; both were forced by installing the extra, and both fix the cause rather than relaxing a guard.

## Issues Encountered

- **`pytest.importorskip` no longer skips on a plain `ImportError`.** While verifying the skip path with a shim that raised `ImportError`, collection *errored* instead of skipping — pytest 9 deliberately refuses to mask a module that exists but is broken. A faithful simulation of absence must raise `ModuleNotFoundError`; with that shim the module correctly collects as `1 skipped`. Worth knowing for 03-09: this is why the test file guards on `"langchain"` (genuinely absent → `ModuleNotFoundError`) rather than on `"paaf_llm._engine"` (present, raises a plain `ImportError` by design).
- **`uv pip index versions` does not exist in this uv build.** Versions were pinned from the PyPI JSON API instead.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-03-SC (supply chain — the `[engine]` family) | All five packages pinned to EXACT versions, not `~=` ranges, and recorded above. Imports confined to `_engine` and CI-enforced (`lint-imports`, 3 kept / 0 broken). `langchain-anthropic` deliberately held off a release published hours earlier. No human-verify checkpoint required — the family is pre-approved by the phase's Package Legitimacy Audit. |
| T-03-04 (info disclosure — api_key in an error or log) | The key is fetched only via `SecretStore.get(api_key_ref)` at bind time and never read from YAML. The adapter never formats a key into a message; for the case it cannot control — a provider echoing the rejected credential back inside its own error string — every resolved value is scrubbed to `***` before any raised message escapes. Asserted by `test_a_resolved_key_never_appears_in_a_raised_message`. The cache key holds `api_key_ref` (a name), never the value. |
| T-03-20 (info disclosure — a direct httpx client bypassing the no-network contract) | The adapter imports no `httpx`/`requests`/`aiohttp`; the provider bindings own the client. Asserted by the plan's source check and by `lint-imports`' `no-network-client-in-framework` contract, still KEPT. |

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest --disable-socket` (packages) | **200 passed** (baseline 174 + 26 new) |
| `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` | **45 passed** (baseline 45 — governance parametrizes over `src/` files only) |
| `uv run lint-imports` | **3 contracts kept, 0 broken** (langchain contract warnings 14 → 12: two whitelisted edges are now real) |
| `bash scripts/check_wheel_independence.sh` | exit 0 — `langchain` NOT importable from the wheel without the extra, smoke suite green |
| Plan Task-1 automated check (`no import httpx` in adapter source) | pass |
| Plan Task-2 automated check (`engine` extra has langchain; base deps do not) | pass |
| Plan Task-3 automated check (`pytest packages/paaf-llm/tests/test_engine_adapter.py`) | 26 passed |
| Skip path (PYTHONPATH shim hiding `langchain`) | **1 skipped** — the module never runs without the extra |
| `uv run ruff check` (all touched files) | All checks passed |

## Known Stubs

None. Every symbol this plan added is wired and exercised.

## Deferred Issues

- **OpenAI-compatible endpoints under `/v1` cannot be fully addressed yet.** `paaf_core.net.endpoint.Endpoint` carries scheme/host/port and no **path**, so a profile can declare `http://127.0.0.1:8080` but not `http://127.0.0.1:8080/v1` — which is where vLLM, llama.cpp's server, and LM Studio actually serve. The adapter deliberately does **not** guess a suffix: silently rewriting the user's declared endpoint is the hidden behavior this project refuses, and it would break the servers that do serve at the root. Fixing it properly means adding an `endpoint_path` field to `ModelProfile` (plan 03-01's schema, and a `paaf_core` `Endpoint` change) — an architectural change outside this plan's scope, flagged here for the phase. Ollama and Anthropic are unaffected. Documented in `LangChainAdapter.base_url`'s docstring.
- **Nothing in CI runs `test_engine_adapter.py` yet.** `.github/workflows/ci.yml` runs `uv sync --all-packages`, which does not install extras, so the module skips in CI and its 26 tests never execute there. This is plan 03-09's territory (it owns the CI gate for the engine/no-engine split); flagged rather than fixed here because `ci.yml` is a shared artifact 03-09 will edit. **Whoever adds that job should know:** the two guards fixed in deviation 2 were the exact blockers, and `-p no:langsmith_plugin` is what keeps the trace-egress control honest once the extra is present.

## Threat Flags

None. This plan introduces no network endpoint, auth path, file access pattern, or schema change beyond what the threat model already registers — the provider connections it makes are the ones `ModelProfile` already declares through `paaf_core`'s endpoint registry.

## User Setup Required

To talk to real models: `pip install 'paaf-llm[engine]'` (or `uv sync --all-packages --extra engine`), a running Ollama for local profiles, and API keys stored in the `paaf_core` SecretStore under the names each profile's `api_key_ref` declares. Nothing without the extra is affected.

## Next Phase Readiness

- **Plan 03-09 (trace wiring / CI gate):** `build_engine_adapter` and the adapter are stable. See the second deferred issue for exactly what its engine-installed CI job needs.
- **Phase 4 (mesh):** `LangChainAdapter` is the single place a provider is reached, so MESH work adds translations here and nothing else. `TurnResult.handoff` remains inert.
- **Phase 5 (tools/MCP):** `langchain-mcp-adapters` is already in the import-linter whitelist and deliberately NOT in the `[engine]` extra — it is a Phase-5 addition, and it is still the pre-1.0 package DECISIONS.md flagged.
- **For the orchestrator:** `STATE.md`, `ROADMAP.md`, and `REQUIREMENTS.md` were intentionally left untouched. This plan completes MODEL-01, MODEL-02, MODEL-06, and MODEL-08 (recorded in `requirements-completed`). Note that `pyproject.toml` (root), `packages/paaf-llm/tests/test_no_leak.py`, and `packages/paaf-trace/tests/test_trace_no_egress.py` are outside this plan's declared `files_modified` — see deviations 1 and 2 for why.

## Self-Check: PASSED

| Claim | Result |
|-------|--------|
| `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` | FOUND |
| `packages/paaf-llm/pyproject.toml` | FOUND |
| `packages/paaf-llm/tests/test_engine_adapter.py` | FOUND |
| `pyproject.toml` | FOUND |
| `packages/paaf-llm/tests/test_no_leak.py` | FOUND |
| `packages/paaf-trace/tests/test_trace_no_egress.py` | FOUND |
| Commit `1b8065d` | FOUND |
| Commit `105fcde` | FOUND |
| Commit `da2bdfd` | FOUND |

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
