---
phase: 03-paaf-llm-core
plan: 12
subsystem: llm-core
tags: [python, pydantic, endpoints, openai-compatible, validation, tdd, gap-closure]

# Dependency graph
requires:
  - phase: 02-core-substrate
    provides: "paaf_core.net.endpoint.Endpoint (frozen dataclass) and ReloadTier — extended here, not forked"
  - phase: 03-paaf-llm-core
    provides: "LangChainAdapter.base_url/model_kwargs/cache_key/bind; ModelProfile.endpoint(); ports.EngineError as a framework-free catchable type (03-10); build_engine_adapter's secret_store keyword (03-11)"
provides:
  - "Endpoint.path + Endpoint.url() — one answer to 'what URL does this endpoint mean', path appended verbatim"
  - "ModelProfile.endpoint_path — a URL path declarable in YAML, e.g. /v1"
  - "ModelProfile.endpoint_unauthenticated — the user's explicit statement that an endpoint needs no credential"
  - "ModelProfile._check_endpoint — six named rejections at load, none of them a repair"
  - "_engine.UNAUTHENTICATED_API_KEY — a structurally required placeholder that is NOT a credential"
  - "The first tests in the repo that BIND an openai_compatible profile (Gap 3 of 03-VERIFICATION closed)"
affects: [03-13, 04-agent-mesh, 09-embedded-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A new field on a frozen dataclass with positional callers goes LAST and carries a default — otherwise it silently reassigns every existing call site's arguments"
    - "URL assembly belongs on the endpoint type, not in each caller, so the value the offline check classifies is character-for-character the value that is dialed"
    - "Malformed untrusted config is REPORTED, never normalized: a repaired path means dialing a URL the user never wrote"
    - "An ambiguous absence is not a declaration — 'no api_key_ref' cannot be read as 'no auth needed', so the no-auth posture is its own explicit field"
    - "A test-only task's RED is a mutation check: re-introduce the exact defect the control names and observe it fail"

key-files:
  created: []
  modified:
    - packages/paaf-core/src/paaf_core/net/endpoint.py
    - packages/paaf-core/tests/test_endpoint_declaration.py
    - packages/paaf-llm/src/paaf_llm/profiles.py
    - packages/paaf-llm/tests/test_profiles.py
    - packages/paaf-llm/src/paaf_llm/_engine/__init__.py
    - packages/paaf-llm/tests/test_engine_adapter.py

key-decisions:
  - "Endpoint.url() lives on the paaf_core type rather than in the adapter, so the URL the APP-08 offline check classifies and the URL the adapter dials are produced by one line of code. Assembling it in the caller would let the two drift silently, which is the failure mode CORE-05 exists to prevent."
  - "endpoint_unauthenticated is a declared field rather than an inference from an absent api_key_ref. An absent reference is genuinely ambiguous between 'no auth is needed' and 'I forgot', and resolving that ambiguity by guessing would send credential-free requests to a server on the user's behalf."
  - "The unauthenticated placeholder is deliberately NOT added to _secret_values. It is not a secret; scrubbing it would replace an ordinary string with *** in unrelated error text, degrading messages for no security gain (T-03-38)."
  - "cache_key gained the auth flag but NOT the path — base_url already carries the path, so a separate element would be redundant. The flag is in the key because it is derivable from no other element in the tuple."
  - "Task 3's controls were mutation-checked, not merely written: an unconditional placeholder and a guessed /v1 suffix were each introduced and observed to turn them red, then reverted. A control asserted to guard something without ever being seen to fail is a claim, not a control (03-11 precedent)."

patterns-established:
  - "Positional-compatibility discipline on shared frozen dataclasses: new fields go last, defaulted, and the reason is recorded in the field's own comment"
  - "Non-vacuous attribute probing in tests: assert a value was FOUND before asserting anything about its contents"

requirements-completed: [MODEL-01, MODEL-02, MODEL-06]

coverage:
  - id: D1
    description: "A URL path is declarable in YAML, validated at load, and reaches the dialed URL through the shared paaf_core Endpoint type"
    requirement: MODEL-02
    verification:
      - kind: unit
        ref: "packages/paaf-core/tests/test_endpoint_declaration.py::TestEndpointUrl (5 tests)"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_a_declared_path_reaches_the_full_url"
        status: pass
    human_judgment: false
  - id: D2
    description: "An openai_compatible profile is exercised at the BINDING level — the coverage hole that let both Gap 3 failures ship"
    requirement: MODEL-02
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_an_unauthenticated_openai_compatible_profile_binds_at_a_v1_endpoint"
        status: pass
    human_judgment: false
  - id: D3
    description: "An unauthenticated endpoint binds with no secret store and no provider environment variable"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_an_unauthenticated_openai_compatible_profile_binds_at_a_v1_endpoint (monkeypatch.delenv OPENAI_API_KEY, LangChainAdapter() with no store)"
        status: pass
    human_judgment: false
  - id: D4
    description: "Removing the no-auth declaration reproduces the verifier's Missing credentials failure as an EngineError that is NOT an AdapterError"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_an_openai_compatible_profile_without_the_auth_declaration_still_needs_a_credential"
        status: pass
      - kind: other
        ref: "mutation check — model_kwargs made to supply the placeholder unconditionally; the control failed with '+ paaf-unauthenticated'; reverted"
        status: pass
    human_judgment: false
  - id: D5
    description: "PAAF appends nothing the user did not declare — a path-less profile derives exactly scheme://host:port"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_base_url_appends_nothing_the_user_did_not_declare"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_two_lan_profiles_distinct_base_urls (pre-existing, unchanged)"
        status: pass
      - kind: other
        ref: "mutation check — Endpoint.url() made to default an absent path to '/v1'; 4 tests failed including both path controls; reverted"
        status: pass
    human_judgment: false
  - id: D6
    description: "Profiles differing only in the path, and only in the auth flag, do not share a cached binding"
    requirement: MODEL-06
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_two_profiles_differing_only_in_the_endpoint_path_do_not_share_a_binding"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_two_profiles_differing_only_in_the_auth_declaration_do_not_share_a_binding"
        status: pass
      - kind: unit
        ref: "packages/paaf-core/tests/test_endpoint_declaration.py::TestEndpointUrl::test_two_endpoints_differing_only_in_path_are_distinct"
        status: pass
    human_judgment: false
  - id: D7
    description: "A malformed endpoint declaration is rejected at load with a message naming the field, and is never normalized"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_malformed_endpoint_declarations_are_rejected (6 ids)"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_profiles.py#test_a_path_with_whitespace_or_a_fragment_is_rejected (3 ids)"
        status: pass
    human_judgment: false

# Metrics
duration: 38min
completed: 2026-08-06
status: complete
---

# Phase 3 Plan 12: A Local OpenAI-Compatible Server Is Now a Working Configuration Summary

**`/v1` and "this endpoint needs no auth" became things the user *declares* — validated at load with six named rejections, appended verbatim, and proven at the binding level by the first tests in the repo that ever bound an `openai_compatible` profile**

## Performance

- **Duration:** ~38 min of active execution
- **Tasks:** 3 (Tasks 1–2 TDD RED → GREEN; Task 3 test-only, mutation-checked)
- **Files modified:** 6
- **Files created:** 0

## Accomplishments

- **Closed Gap 3 of `03-VERIFICATION.md`.** Before this plan there was **no working configuration for a local OpenAI-compatible server** — one of the three providers SC#2 names. Two independent defects caused that, and a third fact explains why neither was noticed.
- **The path became expressible without becoming guessable.** Plan 03-08 refused to silently append `/v1`, and that call was right on the hidden-behavior axis. This plan keeps the principle and removes the limitation: `endpoint_path` is declared, validated, and appended verbatim. `test_base_url_appends_nothing_the_user_did_not_declare` is what keeps 03-08's decision true now that the field exists.
- **The no-auth posture became a declaration rather than an inference.** The tempting shortcut — "no `api_key_ref` means no auth needed" — was rejected. An absent reference is genuinely ambiguous between *no auth is needed* and *I forgot*, and resolving it by guessing would send credential-free requests on the user's behalf. So `endpoint_unauthenticated` is its own field, and the negative control proves it changes the outcome.
- **Covered the level where both defects lived.** `openai_compatible` was exercised only at the provider-string level (one `parametrize` id). Nothing ever *bound* one — which is very likely why two shipped failures went unseen past a green suite. There are now five tests that bind one.

## Task Commits

| # | Task | Commits |
|---|------|---------|
| 1 | A `/v1` endpoint and a no-auth endpoint become declarable in YAML | `9bf66d5` (test, RED) → `fdb13d5` (feat, GREEN) |
| 2 | The adapter binds an `openai_compatible` profile at `/v1` with no credential | `9297ea5` (test, RED) → `1286b95` (feat, GREEN) |
| 3 | Prove the no-auth declaration and the path are load-bearing | `b8c063c` (test) |

No REFACTOR commits were needed. **RED was observed, not assumed:**

- **Task 1 RED:** 9 failed, 43 passed — `AttributeError: 'ModelProfile' object has no attribute 'endpoint_path'` and `Extra inputs are not permitted [type=extra_forbidden]`.
- **Task 2 RED:** collection error — `ImportError: cannot import name 'UNAUTHENTICATED_API_KEY' from 'paaf_llm._engine'`.
- **Task 3** is test-only, so its RED is a **mutation check** — see below.

## The final value of `UNAUTHENTICATED_API_KEY`

Recorded verbatim as the plan's `<output>` requires. It lives in `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` and is in that module's `__all__`, so tests assert the value the adapter actually sends rather than a copy of it.

```python
UNAUTHENTICATED_API_KEY = "paaf-unauthenticated"
```

**It is not a credential**, and the comment above it says so first. The OpenAI binding requires a non-empty `api_key` before it will construct a client at all, so an unauthenticated LAN server could not be bound without supplying *something*. This is that something: a structurally required placeholder, never sourced from the secret store, sent only to an endpoint whose profile explicitly declared `endpoint_unauthenticated: true`. The value is self-describing so a server logging its rejected `Authorization` header, or a user reading a traceback, sees what it is.

It is deliberately **not** added to `LangChainAdapter._secret_values` (T-03-38). Scrubbing it would replace an ordinary string with `***` in unrelated error text — degrading messages for no security gain.

## The six rejection rules, with their exact message texts

All six live in `ModelProfile._check_endpoint`. Every message names the field and quotes the offending value. **None of them repairs anything** (Constraint 4): a malformed path is a config error the user reads and fixes, exactly as a dangling peer name is.

| # | Rule | Message (verbatim, after pydantic's `Value error, ` prefix) |
|---|------|---------------------------------------------------------------|
| 1 | `endpoint_path` without a host/port | `endpoint_path '/v1' needs a declared endpoint_host and endpoint_port — a path alone addresses nothing` |
| 2 | path not starting with `/` | `endpoint_path 'v1' must start with '/'` |
| 3 | path ending with `/` | `endpoint_path '/v1/' must not end with '/' — the path is appended verbatim, so a trailing slash would be dialed` |
| 4 | path containing `?` or `#` | `endpoint_path '/v1?k=x' must not contain '?'; it is a path, not a query string or a fragment` |
| 5 | path containing whitespace | `endpoint_path '/v1 b' must not contain whitespace` |
| 6a | no-auth **and** `api_key_ref` | `endpoint_unauthenticated is true but api_key_ref 'k' is also declared — a profile cannot both need no credential and name one` |
| 6b | no-auth on the wrong provider | `endpoint_unauthenticated is not valid for provider 'ollama'; the flag exists for openai_compatible servers, because the local ollama binding already needs no credential and a hosted anthropic endpoint cannot be unauthenticated` |

**Each was verified to come from the validator, not from `extra="forbid"`.** This mattered: before the fields existed, all six rejection cases passed *vacuously* — `extra_forbidden` also names the field in its message, so the assertion `field in str(error)` was satisfied for entirely the wrong reason. Every message above was printed and read after the fields were added, confirming the validator is what bites.

## Which attribute the OpenAI binding exposes its base URL under

Recorded as the plan's `<output>` requires, so a future framework bump has a documented starting point.

```
bound class:  langchain_openai.chat_models.base.ChatOpenAI
  openai_api_base   = 'http://192.168.1.20:8000/v1'   ← the one that carries it
  base_url          = <absent>
  openai_base_url   = <absent>
  _base_url         = <absent>
```

Note the divergence this documents: the **Ollama** binding exposes `base_url` (asserted directly by the pre-existing `test_two_lan_profiles_distinct_base_urls`), while the **OpenAI** binding exposes `openai_api_base` and has no `base_url` attribute at all. That is why the test reads through a candidate tuple `_BASE_URL_ATTRS` rather than one name — and why it asserts a non-`None` value was **found** before asserting anything about its contents. Without that ordering, a framework bump renaming the attribute would make the test pass vacuously against `None`.

## Task 3's mutation checks

Task 3 adds only tests, so all three passed the moment they were written. A control that has never been seen to fail is a claim, not a control (03-11's precedent), so each was mutation-checked against the exact defect it names:

**Mutation A — `model_kwargs` supplies the placeholder unconditionally** (`if profile.endpoint_unauthenticated:` → `if True:`). This is the realistic wrong implementation: it satisfies every positive assertion in Task 2 while sending an invented credential to *every* OpenAI-compatible endpoint, authenticated or not.

```
FAILED test_an_openai_compatible_profile_without_the_auth_declaration_still_needs_a_credential
FAILED test_api_key_is_resolved_by_reference_not_read_from_config
FAILED test_the_factory_carries_a_secret_store_through_to_key_resolution
3 failed, 32 passed
```

**Mutation B — `Endpoint.url()` defaults an absent path to `/v1`** (the "helpful" suffix 03-08 refused).

```
FAILED test_two_lan_profiles_distinct_base_urls
FAILED test_base_url_appends_nothing_the_user_did_not_declare
FAILED test_two_profiles_differing_only_in_the_endpoint_path_do_not_share_a_binding
FAILED TestEndpointUrl::test_url_without_a_path_is_scheme_host_port
4 failed, 56 passed
```

Both were reverted; `git diff --stat` afterwards showed **only the test file modified**, confirming no mutation leaked into a commit.

## Files Modified

- **`packages/paaf-core/src/paaf_core/net/endpoint.py`** — `path: str = ""` as the **LAST** dataclass field (Constraint 3), with the positional-compatibility reason recorded in its own comment; `url()` returning `scheme://host:port{path}`. The docstring states that the path is appended exactly as declared and that a malformed one is the declaring schema's to reject, not this method's to repair.
- **`packages/paaf-core/tests/test_endpoint_declaration.py`** — a `TestEndpointUrl` class with 5 tests (6 cases). The eight pre-existing positional `Endpoint(host, port, scheme)` constructions are untouched and still pass, which is what Constraint 3 exists to protect.
- **`packages/paaf-llm/src/paaf_llm/profiles.py`** — `endpoint_path` and `endpoint_unauthenticated`, both inside the existing `endpoint_*` family with `reload_tier: RESTART`; `endpoint()` now passes `path=self.endpoint_path or ""` and its CORE-05 paragraph explains that the path travels *with* the endpoint; `_check_endpoint` as a `@model_validator(mode="after")`.
- **`packages/paaf-llm/tests/test_profiles.py`** — a `/v1` positive, an unauthenticated positive, a 6-id parametrized rejection test, a 3-id whitespace/fragment rejection test, and two new assertions in `test_profile_defaults`.
- **`packages/paaf-llm/src/paaf_llm/_engine/__init__.py`** — `UNAUTHENTICATED_API_KEY` (+ `__all__`); `base_url` delegating to `endpoint.url()` with the stale "path is inexpressible" paragraph replaced; `model_kwargs` supplying the placeholder behind the flag; `cache_key` widened by `repr(profile.endpoint_unauthenticated)`.
- **`packages/paaf-llm/tests/test_engine_adapter.py`** — `_openai_compatible` helper, `_BASE_URL_ATTRS` / `_bound_base_url`, and five new tests under a new `MODEL-02: the openai_compatible provider` section.

**No new test file was added** (Constraint 5, confirmed) — so neither `pyproject.toml`'s `force-include` nor `EXCLUDED_FROM_WHEEL` needed touching. **No dependency was added and no `pyproject.toml` was modified.** **`cli.py` was not touched** (Constraint 7 — 03-13 owns it).

## Constraints Honoured

| # | Constraint | Status |
|---|------------|--------|
| 1 | Do not modify `03-01`…`03-09` or any `-SUMMARY.md` | Held — no planning file touched except this new summary |
| 2 | Extend the Phase-2 types, do not fork them | Held — `Endpoint` gained a field and a method in place; `ModelProfile` keeps `extra="forbid"` and the new keys are declared fields |
| 3 | `Endpoint.path` must be the LAST field with a default | Held — verified by the 8 pre-existing positional constructions still passing |
| 4 | Never guess or normalize a URL path | Held — `_check_endpoint` raises on all six malformed shapes and rewrites none; mutation B proves a guessed suffix turns the suite red |
| 5 | No new test file under `packages/paaf-llm/tests/` | Held |
| 6 | No test may contact a real provider | Held — every binding assertion runs offline against real framework objects; only streaming is stubbed; `--disable-socket` throughout |
| 7 | Do not touch `cli.py` | Held — `git diff` shows `cli.py` unmodified by this plan |

## Deviations from Plan

Three, all inside the plan's stated intent. None changed scope.

### Adjustments

**1. [Rule 3 — Blocking] `uv sync --all-packages` needed before anything would run**
- **Found during:** Task 1 baseline
- **Issue:** A fresh worktree has no populated `.venv`; the suite could not be collected.
- **Fix:** Ran `uv sync --all-packages`. Environment-only; no file changed. Baseline established green (**185 passed, 1 skipped**) *before* any edit, so every RED reported above is a real RED and not an artifact of a broken environment.

**2. A separate 3-case test was added for whitespace and fragment paths**
- **Found during:** Task 1 test authoring
- **Issue:** The plan asked for one parametrized rejection test with six cases, but the "`?`, `#`, or whitespace" rule is genuinely three distinct inputs, and folding them into the six ids would have made the id list misrepresent what is covered.
- **Fix:** The 6-id parametrize covers the plan's six named rejection cases exactly (so the acceptance criterion "six ids" is literally true), and `test_a_path_with_whitespace_or_a_fragment_is_rejected` adds `/v1 beta`, `/v1\tx`, and `/v1#frag`. This is strictly more coverage than the plan specified, not a substitution.

**3. Task 3's RED is a mutation check rather than a pre-implementation failure**
- **Found during:** Task 3
- **Issue:** Task 3 is marked `tdd="true"` but adds only tests against behavior Task 2 already implemented, so a literal RED phase is impossible.
- **Fix:** Followed 03-11's established precedent — each control was mutation-checked against the exact defect it names, the failure observed, and the mutation reverted. Both mutations and their outputs are recorded above.

### Out of scope — logged, not fixed

**A pre-existing ruff finding in `packages/paaf-core/src/paaf_core/secrets/__init__.py`** (`RUF022`, `__all__` is not sorted — `"SecretStore"` should follow `"InvalidPassphraseError"`). It is unrelated to this plan, in a file this plan does not touch, and predates it: earlier plans ran `ruff check packages/paaf-llm` only, so `paaf-core` had not been linted recently. Per the executor scope boundary it was **not** fixed. `uv run ruff check packages/paaf-llm` reports **All checks passed**; `packages/paaf-core` reports this one finding, `[*] 1 fixable`.

---

**Total deviations:** 3 (1 blocking environment fix, 1 coverage addition, 1 TDD-shape adaptation) + 1 out-of-scope finding logged
**Impact on plan:** None on scope.

## Verification Results

All six of the plan's `<verification>` steps were run:

| # | Check | Result |
|---|-------|--------|
| 1 | `uv run pytest packages/paaf-core packages/paaf-llm -q --disable-socket` | **179 passed, 1 skipped** (the skip is `test_engine_adapter.py`'s `importorskip`) |
| 2 | `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` | **35 passed, 0 skipped** — all five new tests genuinely RAN, up from 30 |
| 3 | `uv sync --all-packages` then `uv run pytest -q --disable-socket` (whole workspace) | **202 passed, 1 skipped** (baseline was 185 + 1) |
| 4 | `uv run lint-imports --no-cache` | **3 contracts kept, 0 broken** |
| 5 | `bash scripts/check_wheel_independence.sh` | **PASS** — the profile schema changed; the wheel's dependency posture did not |
| 6 | `uv run ruff check packages/paaf-core packages/paaf-llm` | **No findings from this plan's files.** One pre-existing unrelated finding in `paaf_core/secrets/__init__.py` — see "Out of scope" above |

Additional gate run beyond the plan's list:

- `bash scripts/check_framework_uninstalled.sh` — **PASS**. Builds the wheels, installs into a clean venv with no `[engine]` extra, and runs the full fake-adapter suite there with `langchain`/`langgraph` proven not importable. This matters because `profiles.py` gained a validator that must work where the framework is genuinely absent.

Acceptance-criteria checks, all satisfied:

| Criterion | Required | Result |
|---|---|---|
| `Endpoint('192.168.1.20',8000,'http','/v1').url()` | `http://192.168.1.20:8000/v1` | `ok` |
| `Endpoint('192.168.1.20',8000,'http').url()` | `http://192.168.1.20:8000` | `ok` |
| a path does not change `is_lan()` | true | `ok` |
| two endpoints differing only in path: `a != b and len({a,b})==2` | true | `ok` |
| `ModelProfile(...endpoint_path='/v1'...).endpoint().url()` | full URL | `ok` |
| six rejection cases raise `ValidationError` | 6 ids pass | 6 ids pass (+3 more) |
| `grep -c 'def url' packages/paaf-core/.../endpoint.py` | `1` | `1` |
| `grep -c 'endpoint.url()' _engine/__init__.py` | `1` | `1` |
| `grep -c 'UNAUTHENTICATED_API_KEY' _engine/__init__.py` | ≥ `3` | `3` |
| `grep -c 'delenv' test_engine_adapter.py` | ≥ `2` | `4` |
| `test_base_url_appends_nothing_the_user_did_not_declare` uses `==` | yes | yes |
| the no-auth control asserts `not isinstance(raised.value, AdapterError)` | yes | yes |
| the bind test asserts a non-`None` base-URL attribute was located first | yes | yes |
| `test_two_lan_profiles_distinct_base_urls` still passes unchanged | yes | yes |

## Threat Model Disposition

| Threat ID | Disposition | Status |
|---|---|---|
| T-03-36 (a hand-edited path appended into a dialed URL) | mitigate | **Held.** `_check_endpoint` rejects all six malformed shapes at load, each naming its field and quoting the value, and normalizes nothing. 9 parametrized rejection cases, every message verified to originate in the validator rather than in `extra="forbid"`. |
| T-03-37 (an unauthenticated bind reaching a non-LAN endpoint) | accept | **Accepted as planned.** The endpoint remains a declared `paaf_core` `Endpoint`, so `is_lan()` classifies it and Phase-9's APP-08 daemon still sees it through the one interface. `test_a_path_does_not_change_classification` pins that a declared path cannot shift classification — refusing non-LAN endpoints stays APP-08's single job. |
| T-03-38 (the placeholder mistaken for a credential) | mitigate | **Held.** A module constant with a self-describing value, never sourced from the secret store, deliberately absent from `_secret_values`. It neither leaks a real key nor corrupts unrelated error text through the scrubber. |
| T-03-39 (two profiles collapsing into one cached binding) | mitigate | **Held.** `cache_key` carries the derived URL (which now carries the path) and the auth flag. Two controls assert that profiles differing only in the path, and only in the flag, bind to distinct clients. |
| T-03-40 (`model_kwargs` supplying an invented credential where one was required) | mitigate | **Held, and demonstrated.** Mutation A introduced exactly this defect and turned the suite red on three tests. |
| T-03-04 (existing — a provider echoing a rejected credential back) | mitigate | **Held, unchanged.** `_scrub` and `test_a_resolved_key_never_appears_in_a_raised_message` are untouched and re-ran green. |
| T-03-SC (package installs) | mitigate | **Held vacuously, as intended.** No package was installed and no dependency list was edited. `check_wheel_independence.sh` PASSes. |

**One new security-relevant surface, and it is the subject of the register above:** PAAF can now send an HTTP request carrying no real credential, to a user-declared host, under a user-declared path. Both halves are explicit declarations validated at load, and both are covered by negative controls. No threat flags.

## Known Stubs

None. Nothing in this plan renders placeholder data or leaves a component unwired.

## Scope Note — what this plan does NOT claim

- **MODEL-02** is claimed, and this is the plan that earns it. 03-10 and 03-11 both explicitly deferred the OpenAI-compatible leg here. A local OpenAI-compatible server is now a *working configuration* rather than a theoretical one, and it is exercised at the binding level for the first time.
- **MODEL-01 / MODEL-06** are claimed narrowly: MODEL-01 for the credential posture of an `openai_compatible` profile being declarable and load-bearing, MODEL-06 for the cache-distinctness property extended to the provider that had no binding coverage.
- **SC#2's OpenAI-compatible leg is not fully closed by automation.** Every acceptance criterion here is decidable offline under `--disable-socket`. The live round-trip is the manual step below.
- **`cli.py` is untouched**, so nothing here changes what `paaf chat` does beyond what the schema now permits. 03-13 owns that file.
- `REQUIREMENTS.md`, `STATE.md` and `ROADMAP.md` were intentionally **not** edited by this worktree agent — those are shared-file writes the orchestrator owns after the wave merges.

## User Setup Required

None for the tests — every check in this plan is decidable offline.

**Manual verification this plan makes possible** (do not automate — no test may contact a real provider):

```bash
# 1. Start vLLM, llama.cpp's server, or LM Studio on the LAN with NO auth.
#    All three serve under /v1.

# 2. Declare it — the path and the no-auth posture are both explicit:
#    profiles:
#      lan-vllm:
#        provider: openai_compatible
#        model: qwen3:32b
#        endpoint_host: 192.168.1.20
#        endpoint_port: 8000
#        endpoint_path: /v1
#        endpoint_unauthenticated: true

# 3. Hold a turn, with OPENAI_API_KEY deliberately NOT set.
unset OPENAI_API_KEY
echo "hello" | uv run paaf chat --config paaf.yaml
```

Reaching the model with `OPENAI_API_KEY` unset is the live confirmation of SC#2's OpenAI-compatible leg — it proves the endpoint was addressed at the path the user declared and accepted without a credential the user never supplied.

## Next Phase Readiness

- **Gap 3 is closed.** The third provider SC#2 names now has both a valid configuration and binding-level coverage.
- **`Endpoint.url()` is the seam Phase 9 will want.** APP-08's offline check and every future dialer can now agree on one URL string by construction rather than by convention.
- **Documented for a future framework bump:** the OpenAI binding exposes its base URL as `openai_api_base` and has no `base_url` attribute; the Ollama binding is the reverse. `_BASE_URL_ATTRS` in `test_engine_adapter.py` is where to extend if a bump renames either.
- **Environment note for the next executor:** the worktree is left synced with `uv sync --all-packages` (no `[engine]` extra), matching the documented baseline. In that state `packages/paaf-core packages/paaf-llm` reports **179 passed, 1 skipped** and the whole workspace reports **202 passed, 1 skipped**.

## Self-Check: PASSED

- All 6 claimed files verified present on disk.
- All 5 claimed commits verified present in `git log`.
- `git diff --diff-filter=D --name-only 046e781 HEAD` reports no deleted files — nothing was removed by this plan.
- Both mutation checks confirmed reverted: `git diff --stat` after each showed only the intended test file modified.
- `cli.py` confirmed unmodified by this plan (Constraint 7).

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-06*
