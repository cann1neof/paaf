---
phase: 03-paaf-llm-core
verified: 2026-08-06T17:02:03Z
status: human_needed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2026-08-06 — 3/5
  gaps_closed:
    - "SC#2 — `paaf chat` could not use PAAF's own credential mechanism: `cli._default_adapter` never forwarded a secret store, so any `api_key_ref` profile died at bind (Gap 1, plan 03-11)"
    - "SC#2 — an OpenAI-compatible server under `/v1` was inexpressible and an unauthenticated one could not bind; no test bound an `openai_compatible` profile (Gap 3, plan 03-12)"
    - "`paaf chat` reported failures as a raw Python traceback: `_chat_loop` caught only `AllProvidersFailed`, so `EngineError` escaped (Gap 2, plan 03-10)"
    - "`paaf chat` never wrote a trace row: `build_agent(config)` was called with no `trace=` sink (Warning/Gap 4, plan 03-13)"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "SC#5's 'skill fragments' clause — an ACTIVE skill contributes a persona fragment to the composed prompt (PERS-02)."
    addressed_in: "Phase 6 — Skills & PyPI Release"
    evidence: "Phase 6 success criterion 2 (read from ROADMAP.md line 225): 'Enabling or disabling an installed skill changes the composed prompt and the tool registry without uninstalling it.' Phase 3's `cli.load_skill_fragments` returns `[]` by documented design (D-09); the composer's fragment contract is pinned now by tests that repoint that source."
  - truth: "SC#5's 'runtime context' clause — time, device name, room compose into the prompt (PERS-03)."
    addressed_in: "Phase 10 — The Appliance"
    evidence: "ROADMAP.md line 288 lists PERS-03 in Phase 10's Requirements; REQUIREMENTS.md line 265 maps `PERS-03 | Phase 10 — The Appliance`. Plan 03-07 scoped SC#5 to base + skill fragments on this basis (D-09)."
human_verification:
  - test: "With a real `ANTHROPIC_API_KEY` stored in an encrypted `paaf_core` secret store under the name a profile's `api_key_ref` declares, run `paaf chat --config <yaml> --secrets <store>` against a live Anthropic profile and hold one turn."
    expected: "A genuine completion comes back from api.anthropic.com and is printed as `<profile>> <reply>`."
    why_human: "Requires a real, billable API key. The verifier proved the whole path up to the wire — the key resolves out of a real encrypted store, the Anthropic profile BINDS with it, and it dials a real socket (an Anthropic profile pointed at a dead local port produced a real `ConnectionFailed` and hopped) — but a successful Anthropic completion cannot be produced without a credential. 03-VALIDATION.md already lists this as Manual-Only."
  - test: "With a real cloud profile as `active_profile` and a real local Ollama profile in `fallback_chain`, start `paaf chat`, send one turn successfully, then physically disconnect the WAN and send a second turn."
    expected: "The second turn prints `↳ fell back to <local> (connection)`, is answered by the local model, and that reply shows it received the first turn's history."
    why_human: "Cutting a real WAN link is a physical state change no automated check in this repo can produce. The verifier reproduced the equivalent live — an unreachable active profile produced a real ConnectionFailed, the loop hopped to a real local Ollama server, and turn 2's answer recalled turn 1's content — so what is left is confirmation that a WAN cut is indistinguishable from an unreachable endpoint."
  - test: "Cold-start a 14B Ollama model and send the first turn of a session."
    expected: "No spurious `slow_first_token` fallback inside the configured `first_token_budget_s` — `Agent.warmup()` / `LangChainAdapter.preload()` absorbs the cold-load cost."
    why_human: "03-VALIDATION.md Manual-Only row. Timing against a real cold-loading model cannot be asserted deterministically offline, and the verifier's local model is small and already warm."
  - test: "Point two Ollama profiles at two DIFFERENT physical LAN machines and confirm each answers from its own box."
    expected: "`ollama ps` on each machine (or distinct model names) confirms which server ran."
    why_human: "The verifier has one Ollama server. Distinctness was proven live at the endpoint level — two same-provider profiles at 127.0.0.1:11435 (dead) and 127.0.0.1:11434 (live) did NOT share a binding: the dead one produced a real connection failure rather than being answered by the live one's client. Two physical boxes is the remaining confirmation."
---

# Phase 3: paaf-llm Core (single agent) — Verification Report (re-verification)

**Phase Goal:** `paaf chat` holds a real single-agent conversation using a model the user named in YAML, survives losing its provider mid-sentence via a user-defined fallback chain, and shows the user the exact prompt it sent — while each profile also declares the capability manifest and peer-agent graph the mesh will later traverse.

**Verified:** 2026-08-06T17:02:03Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure by plans 03-10, 03-11, 03-12, 03-13

> **Mode note (non-blocking, carried forward).** ROADMAP.md declares `Mode: mvp` for this
> phase, but the phase goal is not in User Story form (`As a …, I want to …, so that …`).
> The MVP-mode guard would normally refuse to verify. It is bypassed here for the same
> reason as the initial pass: the five Success Criteria are explicit and independently
> verifiable, and the orchestrator directed a goal-backward assessment against them. The
> User Flow Coverage table is therefore omitted; the mode/goal mismatch remains surfaced
> for the maintainer to reconcile.

---

## Verdict In One Line

All four gaps from the 2026-08-06 initial verification are **closed in the code, not merely in the SUMMARYs** — and each closure was re-verified by running the shipped command against a real provider, not by reading a diff. Score moves 3/5 → **5/5**, with no regressions and no new gaps. What remains is four confirmations that require a paid API key, a physical WAN cut, a cold 14B model, or a second LAN machine — none of which this repo can produce.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The `fake/` adapter is written and merged BEFORE the real adapter, and the entire `paaf-llm` suite passes against it with the agent framework uninstalled | ✓ VERIFIED | **Regression check.** Ordering re-confirmed from git: `9d8d43f` (FakeAdapter, 2026-08-05 16:19) precedes `105fcde` (LangChainAdapter body, 2026-08-05 23:46); `_engine/__init__.py` existed before that only as a Phase-2 docstring marker (`5bc918d`, verified by `git show`). **I ran `bash scripts/check_framework_uninstalled.sh` myself:** builds wheels, asserts all 11 fake-suite test files ship (only `test_engine_adapter.py` deliberately excluded), installs into a clean off-repo venv, `pytest --pyargs paaf_llm` → **128 passed** (up from 102 — the gap-closure tests ship too), then asserts `langchain` and `langgraph` are both unimportable. Exit 0. |
| 2 | Model profiles across Ollama, OpenAI-compatible and Anthropic in YAML — incl. two LAN servers as distinct profiles — and `paaf chat` uses them without a line of code | ✓ VERIFIED (1 live confirmation → human) | **Was ✗ FAILED. Both blocking defects are gone, proven live.** (a) `api_key_ref` now works end to end: I wrote a **real** `EncryptedFileSecretStore` to disk, set `PAAF_SECRET_PASSPHRASE`, and an Anthropic profile declaring `api_key_ref` **bound successfully** and dialed a real socket — the failure reported was `cloud(connection)`, not the old `EngineError: … no secret store was provided`. (b) An **unauthenticated `openai_compatible` profile at `/v1`, declared entirely in YAML, held a real conversation**: `paaf chat --config oai2.yaml` → `vllm_like> banana`, exit 0, trace row `served_by=vllm_like, fallback_trail=[]`. (c) Ollama: **live two-turn conversation** (see truth 3). (d) Two same-provider endpoints are genuinely distinct bindings — live. Remaining: a real Anthropic *completion* needs a paid key → human. |
| 3 | Pulling the WAN mid-conversation moves the reply onto a local profile and the conversation continues; timeout / 5xx / 429 / slow-first-token trigger the same chain | ✓ VERIFIED | **Was ⚠️ PRESENT_BEHAVIOR_UNVERIFIED. Now proven live against a real provider, on both legs.** *Hard loss:* active profile unreachable → `↳ fell back to local (connection)` → answered by a real Ollama model; turn 2 replied **“You stated that chartreuse was your favorite color previously!”**, proving the history crossed the hop. *Degraded-but-reachable:* a **reachable** Ollama profile with `first_token_budget_s: 0.005` produced `↳ fell back to patient (slow_first_token)` and a real answer from the next profile — a live degraded trigger, not a hard connection error. Both trails were read back off a real SQLite file. timeout/5xx/429 remain proven against the fake with an enum-exhaustiveness control plus translation validated against 13 real provider SDK exception instances (35 `[engine]` tests pass). |
| 4 | Each profile declares a natural-language capability manifest and peer agents in YAML; the schema validates them and `paaf chat` surfaces them, with no handoff behavior | ✓ VERIFIED | **Regression check + new fields.** I ran `paaf profiles` and `paaf chat` on a hand-written 4-profile YAML: every `capabilities`, `peers`, `constraints`, role marker and the inert-graph note printed. The schema now additionally validates `endpoint_path` and `endpoint_unauthenticated` with named rejections (`profiles.py:131-183`). `_check_refs` still rejects dangling/self peers and dangling fallback/active targets. Inertness keeps its real negative control (`test_manifest_performs_no_handoff` leaves the declared peer UNPROGRAMMED so any contact raises `LookupError`, not a swallowable `AdapterError`); `TurnResult.handoff` is hardcoded `None` (`agent.py:208`). |
| 5 | One command prints the final composed prompt verbatim — exactly as sent, containing nothing the user did not write | ✓ VERIFIED (2 clauses deferred) | **Regression check re-run.** `uv run paaf prompt --config live.yaml \| od -c` ends `s e n t e n c e .` with **no trailing newline**. `--provenance` prints `--- base ---` plus the verbatim text. `test_prompt_byte_exact` still closes the loop three ways (CLI stdout == `compose()` == the `system` message the adapter actually received on a real turn). The trace row's `prompts` column now independently corroborates it: `'You are Ada. Answer in one short sentence.'` — byte-identical to the base prompt, read back with stdlib `sqlite3`. "skill fragments" → Phase 6, "runtime context" → Phase 10 (see Deferred Items). |

**Score:** 5/5 truths verified (0 present-but-behavior-unverified, 0 failed)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC#5 "skill fragments" — an active skill contributes a fragment (PERS-02) | Phase 6 | ROADMAP.md:225 — Phase 6 SC#2: "Enabling or disabling an installed skill changes the composed prompt and the tool registry without uninstalling it." Phase 3's `load_skill_fragments` returns `[]` (D-09), a named seam whose fragment contract is pinned now by tests that repoint the source. |
| 2 | SC#5 "runtime context" — time / device name / room (PERS-03) | Phase 10 | ROADMAP.md:288 lists PERS-03 in Phase 10's Requirements; REQUIREMENTS.md:265 maps `PERS-03 | Phase 10 — The Appliance`. |

---

## Gap-Closure Verification (the four items this re-verification exists for)

### Gap 1 — `paaf chat` could not use PAAF's own credential mechanism (plan 03-11)

**Was:** `cli._default_adapter` called `build_engine_adapter(config)` with one argument, so `LangChainAdapter._secret_store` was always `None` and every `api_key_ref` profile died at bind.

**Now — code read directly:** `cli.py:287` reads `return build_engine_adapter(config, secret_store=secret_store)`. The store is resolved by `cli.open_secret_store` (`cli.py:210-258`) and threaded `chat` → `_chat_session` → `build_agent(secret_store=…)` → `_default_adapter(config, secret_store)`.

**Now — run live:** I created a real `EncryptedFileSecretStore` at `secrets.json` (mode **0600**, verified) holding `anthropic_key`, and ran

```
PAAF_SECRET_PASSPHRASE=… paaf chat --config local.yaml --secrets secrets.json --trace-db trace.db
```

with an Anthropic profile pointed at a dead local port. Output:

```
Error: every profile in the chain degraded: cloud(connection), lan_a(connection), vllm(connection)
```

`cloud(connection)` is the load-bearing token. The Anthropic profile **bound** — meaning the key was fetched out of the encrypted store by reference — and then failed at the *socket*, which is a degraded provider. Under the old code this same run produced `EngineError: … no secret store was provided`, a config failure, before any socket. Exit 1, `grep -c Traceback` = **0**.

**Guard rails confirmed:** an `api_key_ref` config with no `--secrets` prints the named-profile guidance and exits 1 with zero tracebacks (reproduced live). `--help` confirms there is **no `--passphrase` option** — the passphrase is env-only, so it cannot land in `ps` or shell history. `test_a_config_with_no_api_key_ref_never_opens_a_store` replaces the store class with a callable that fails the test, so an all-local config provably never touches the filesystem.

**Seam pinned:** `test_the_cli_default_adapter_forwards_the_store_to_the_factory` (test_engine_adapter.py:700) intercepts `build_engine_adapter` on the module and asserts `_default_adapter`'s own body forwards the store — the one line that was executed by nothing before, which is exactly how the bug shipped past a green suite. It runs in the `[engine]` job; I ran it: **35 passed, 0 skipped.**

### Gap 2 — `EngineError` escaped `paaf chat` as a raw traceback (plan 03-10)

**Was:** `_chat_loop` caught only `AllProvidersFailed`.

**Now — code read directly:** `EngineError` is defined in `ports.py:156` (verified as the **only** definition in the repo: `grep -rn "class EngineError" packages/` → one hit). `_engine/__init__.py:79-87` imports and re-exports that exact class. I confirmed object identity at runtime:

```
paaf_llm.EngineError is paaf_llm.ports.EngineError  → True
paaf_llm._engine.EngineError is paaf_llm.ports.EngineError → True
```

`cli.py` imports it at **module scope** (`cli.py:63`) — framework-free, which is the whole point of the move. `_chat_loop` now has three named handlers (`cli.py:402-417`): `AllProvidersFailed` (keeps its own chain-exhaustion wording), `EngineError` → `CONFIG_FAILURE_NOTICE`, and a post-commit `AdapterError` → `MID_REPLY_FAILURE_NOTICE` formatted from `exc.reason.value` (the same string the trace records, so terminal and trace cannot disagree). A fourth site is covered in `_chat_session` (`cli.py:458-461`) for the factory's up-front provider validation.

**Now — run live:** all three failure surfaces produced one readable line and exit 1, with **zero** `Traceback` occurrences: the missing-`--secrets` guard, the chain-exhaustion path, and (via the test suite) the bind and mid-reply paths.

**Not a catch-all:** `test_an_unexpected_exception_still_escapes` injects a `LookupError` and asserts `isinstance(result.exception, LookupError)` — it is the single test in the file that would turn red if either handler were widened to the base exception. `test_a_failure_before_the_reply_began_still_falls_back` is the second control: it proves a *pre-commit* `AdapterError` still becomes a fallback hop rather than an error message, so the fix did not quietly convert MODEL-03/04 into an error path. Both pass.

### Gap 3 — OpenAI-compatible was unaddressable and untested at the binding level (plan 03-12)

**Was:** `paaf_core.Endpoint` carried no path (so `/v1` was inexpressible), an unauthenticated local server could not bind, and `openai_compatible` had **zero** binding-level test coverage.

**Now — code read directly:** `Endpoint` gained a defaulted, **last-declared** `path` field plus `url()` (`endpoint.py:47-63`) — defaulted-and-last so existing positional constructions are not silently reassigned. `ModelProfile` gained `endpoint_path` and `endpoint_unauthenticated` (`profiles.py:64-74`) with a validator that **rejects and never repairs** a malformed path (no leading `/`, trailing `/`, `?`/`#`, whitespace, or a path with no host/port), and rejects the flag combined with an `api_key_ref` or with a non-`openai_compatible` provider. `_engine` supplies `UNAUTHENTICATED_API_KEY = "paaf-unauthenticated"` — deliberately kept OUT of `_secret_values` because it is not a secret — and widened `cache_key` to include the flag.

**Now — run live.** The strongest single piece of evidence in this report:

```
# oai2.yaml — declared entirely in YAML, no code
provider: openai_compatible
endpoint_host: 127.0.0.1
endpoint_port: 11434
endpoint_path: /v1
endpoint_unauthenticated: true

$ printf 'Say the word banana and nothing else.\n' | env -u OPENAI_API_KEY paaf chat --config oai2.yaml --trace-db oai2.db
vllm_like> banana
EXIT=0
runs → {'served_by': 'vllm_like', 'fallback_trail': '[]'}
```

`env -u OPENAI_API_KEY` is load-bearing: no ambient credential was available, so the bind succeeded on the declared `endpoint_unauthenticated` flag alone. Direct adapter inspection confirmed the dialed URL: `base_url: http://127.0.0.1:11434/v1`, `kwargs: {'temperature': 0.7, 'base_url': 'http://127.0.0.1:11434/v1', 'api_key': 'paaf-unauthenticated'}`, bound class `langchain_openai.chat_models.base.ChatOpenAI` carrying that same base URL. The empty `fallback_trail` is the negative control — the active profile served it, no spurious hop.

**Coverage hole closed:** `test_engine_adapter.py` now has five binding-level `openai_compatible` tests, including a negative control (`test_an_openai_compatible_profile_without_the_auth_declaration_still_needs_a_credential`, which `delenv`s `OPENAI_API_KEY` so it cannot pass on an ambient credential) and `test_base_url_appends_nothing_the_user_did_not_declare` asserting `==` against the whole string so a helpfully-invented `/v1` fails there rather than at a dialed URL.

### Gap 4 / Warning — `paaf chat` never wrote a trace row (plan 03-13)

**Was:** `chat` called `build_agent(config)` with no `trace=` sink, so `Agent._drain` returned on its first line.

**Now — code read directly:** `--trace-db` option (`cli.py:505-515`) and a new `_chat_session` coroutine (`cli.py:423-465`) that constructs `TraceStore` **inside** the running loop (the store's queue and writer task belong to the loop), builds the agent there, and `await store.stop()` in a `finally`.

**Now — run live.** Two-turn conversation against a real Ollama server with `--trace-db live.db`, read back with **stdlib `sqlite3`** (not through `paaf_trace`, so a store that never wrote could not satisfy its own reader):

```
{'model': 'local', 'served_by': 'local', 'fallback_trail': '[{"from": "cloud", "to": "local", "reason": "connection"}]', 'p': 'You are Ada. Answer in one short sentence.'}
{'model': 'local', 'served_by': 'local', 'fallback_trail': '[{"from": "cloud", "to": "local", "reason": "connection"}]', 'p': 'You are Ada. Answer in one short sentence.'}
```

The `reason` string in the row is character-identical to the `(connection)` the user saw in `↳ fell back to local (connection)` — D-06's claim, verified across the terminal/disk boundary. The live `slow_first_token` run produced the matching row for the degraded trigger. `paaf chat` **without** `--trace-db` constructs nothing (confirmed by test and by the absence of any stray file).

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/paaf-llm/src/paaf_llm/ports.py` | Message/Usage/TurnResult/FallbackReason/AdapterError×4/AllProvidersFailed/**EngineError**/ChatAdapter | ✓ VERIFIED | 236 lines. Zero framework imports (`ModelProfile` under `TYPE_CHECKING` only). `EngineError` moved here with a docstring stating *why* the placement is load-bearing, not merely tidy. `handoff` Phase-4 seam present and always `None`. |
| `packages/paaf-llm/src/paaf_llm/cli.py` | chat + prompt + profiles + `--show-prompt` + `--provenance` + `--secrets` + `--trace-db` + named failure surfaces | ✓ VERIFIED | 581 lines (was 327). Both previously-missing production wirings are present and exercised live. Every user-facing string is a module constant, so tests assert against what the CLI emits rather than a copy. |
| `packages/paaf-llm/src/paaf_llm/profiles.py` | ModelProfile + LlmConfig, cross-ref validator, endpoint(), **endpoint_path / endpoint_unauthenticated** | ✓ VERIFIED | 243 lines (was 168). `extra="forbid"` on both models. New validator rejects six distinct malformed-path shapes and two invalid flag combinations, each with a named message. |
| `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` | LangChainAdapter + build_engine_adapter + secret resolution + path/no-auth binding | ✓ VERIFIED | 612 lines. `find_spec` import guard (imports nothing), lazy `_framework()`, no httpx import, structural exception classification with a bounded cause-chain walk, secret scrubbing, `UNAUTHENTICATED_API_KEY` deliberately excluded from the scrub set. |
| `packages/paaf-core/src/paaf_core/net/endpoint.py` | Endpoint with `path` + `url()`; `is_lan()` unchanged | ✓ VERIFIED | `path` declared LAST and defaulted so positional callers are not reassigned; `is_lan()` still reads host only. |
| `packages/paaf-llm/src/paaf_llm/agent.py` | ordered fallback, first-token deadline, history, trace drain | ✓ VERIFIED | 297 lines. `asyncio.timeout` wraps only the first `__anext__`; `aclose()`d on timeout; history appended only after a served turn; `_drain` writes `served_by` + JSON trail. |
| `packages/paaf-llm/src/paaf_llm/compose.py` | Segment + segments()/compose() | ✓ VERIFIED | Regression check — `join(segments) == compose()` invariant still asserted; byte-exactness re-confirmed live via `od -c`. |
| `packages/paaf-llm/src/paaf_llm/fake/__init__.py` | FakeAdapter.program()/stream()/last_usage() | ✓ VERIFIED | Un-programmed profile still raises `LookupError` (deliberately not an `AdapterError`) — the choice that makes both `test_manifest_performs_no_handoff` and `test_an_unexpected_exception_still_escapes` real controls. |
| `packages/paaf-trace/.../schema.sql` + `store.py` | additive served_by + fallback_trail | ✓ VERIFIED | Columns present in a file written by the shipped command: `PRAGMA table_info(runs)` on a CLI-created DB → `[…, 'served_by', 'fallback_trail']`. |
| `packages/paaf-llm/tests/test_inspector.py` | CLI end-to-end incl. all four gap closures | ✓ VERIFIED | 1131+ lines (was ~600). 34 tests; every gap-closure claim is paired with a negative control. |
| `packages/paaf-llm/tests/test_engine_adapter.py` | real-adapter seam incl. openai_compatible binding + factory forwarding | ✓ VERIFIED | 30 tests, **35 passed / 0 skipped** with `[engine]` installed (was 26). |
| `.importlinter` | provider modules forbidden + `_engine` whitelist | ✓ VERIFIED | 3 contracts kept, 0 broken (run twice: with and without the extra). |
| `scripts/check_framework_uninstalled.sh` | SC#1 clean-venv gate | ✓ VERIFIED | Executed by the verifier. PASS, 128 tests, langchain+langgraph unimportable. |
| `.github/workflows/engine-adapter.yml` | framework-PRESENT gate with an anti-silent-skip step | ✓ VERIFIED | Read in full. Asserts the framework really imported before running the suite, then runs the whole workspace suite under the extra. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cli.chat` | `cli.open_secret_store` | `os.environ[PAAF_SECRET_PASSPHRASE]` + `--secrets` | ✓ WIRED | Early-returns `None` before touching the filesystem when no profile names a ref (T-03-34), proven by a test that replaces the store class with a failing callable. |
| `cli._default_adapter` | `_engine.build_engine_adapter` | `secret_store=` keyword | ✓ WIRED | **Was ✗ NOT_WIRED.** `cli.py:287`. Pinned by `test_the_cli_default_adapter_forwards_the_store_to_the_factory`, and demonstrated live by an Anthropic profile binding on a store-resolved key. |
| `LangChainAdapter._secret_store` | `ModelProfile.api_key_ref` | `SecretStore.get(ref)` | ✓ WIRED | `_engine:362-386`. Resolved value added to `_secret_values` for scrubbing; never logged. |
| `cli.chat --trace-db` | `paaf_trace.TraceStore` → `Agent._drain` | `_chat_session` → `build_agent(trace=store)` | ✓ WIRED | **Was ✗ NOT_WIRED.** Rows read back off a real SQLite file with stdlib `sqlite3` after a live conversation. |
| `cli._chat_loop` | `ports.EngineError` | module-scope import, framework-free | ✓ WIRED | **Was ✗ NOT_WIRED.** `cli.py:63`; class identity confirmed at runtime across `paaf_llm`, `paaf_llm.ports` and `paaf_llm._engine`. |
| `ModelProfile.endpoint()` | `paaf_core.Endpoint.url()` | `path` travels with the endpoint | ✓ WIRED | **Was ⚠️ PARTIAL.** Live: `base_url → http://127.0.0.1:11434/v1`, and that exact string is what the bound `ChatOpenAI` carries. The value Phase-9's offline check will classify is the value dialed. |
| `ModelProfile.endpoint_unauthenticated` | `LangChainAdapter.model_kwargs` / `cache_key` | placeholder api_key + cache identity | ✓ WIRED | Two profiles differing only in the flag do not collide (tested); a profile without the flag still fails to bind with no credential (negative control, `delenv`'d). |
| `cli.prompt` | `compose.PromptComposer.compose` | same `load_skill_fragments` source | ✓ WIRED | Byte-identity asserted against the message the adapter received; corroborated by the `prompts` column of a real trace row. |
| `cli.chat --show-prompt` | `agent.Agent.system_prompt` | direct call | ✓ WIRED | `test_show_prompt_echoes_what_was_sent` compares against `adapter.calls[0]`. |
| `agent._run_chain` | `ports.AdapterError.reason` | `trail.append(..., exc.reason.value)` | ✓ WIRED | Classification by reason, never by foreign exception type. Live trail strings match the terminal notice exactly. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `cli.render_profiles` | `config.profiles` | YAML → `LlmConfig.model_validate` | Yes — ran `paaf profiles` on a hand-written 4-provider YAML incl. the new fields | ✓ FLOWING |
| `cli.prompt` | `config.base_prompt` + `fragments` | YAML + `load_skill_fragments` | Base prompt: yes. Fragments: `[]` by design (D-09) | ⚠️ STATIC (deferred to Phase 6) |
| `cli._chat_loop` | `result.text` / `served_by` / `fallback_trail` | `Agent.turn` → real provider stream | Yes — live replies from a real Ollama server over two provider bindings | ✓ FLOWING |
| `Agent._drain` → trace DB | `RunEvent` | `self._trace` = `TraceStore(--trace-db)` | **Yes** — 2 committed rows read back with stdlib sqlite3 | ✓ FLOWING (was ✗ DISCONNECTED) |
| `LangChainAdapter.model_kwargs` | `api_key` | `self._secret_store.get(ref)` | **Yes** — real encrypted store, real key, profile bound | ✓ FLOWING (was ✗ DISCONNECTED) |
| `LangChainAdapter.base_url` | `endpoint_path` | `ModelProfile.endpoint()` → `Endpoint.url()` | **Yes** — `/v1` reached a real server that answered | ✓ FLOWING (was ⚠️ PARTIAL) |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full workspace suite (no extra) | `uv run pytest -q --disable-socket` | **206 passed, 1 skipped** (skip is `test_engine_adapter.py::importorskip langchain`, confirmed with `-rs`) | ✓ PASS |
| Full workspace suite (with extra) | `uv sync --all-packages --extra engine && uv run pytest -q --disable-socket` | **241 passed, 0 skipped** | ✓ PASS |
| Real-adapter seam | `uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` (extra installed) | **35 passed, 0 skipped** | ✓ PASS |
| Named gap-closure regressions | `pytest -k "a_failing_session_still_flushes_its_rows or the_cli_default_adapter_forwards_the_store_to_the_factory or an_unauthenticated_openai_compatible_profile_binds_at_a_v1_endpoint or a_bind_failure_is_reported_readably or an_unexpected_exception_still_escapes or chat_with_a_trace_db_writes_a_run_row"` | **6 passed** | ✓ PASS |
| Import boundary | `uv run lint-imports --no-cache` (with AND without the extra) | 3 contracts kept, 0 broken. With the extra, `_engine -> langchain` and `_engine -> langchain_core` are absent from the "no matches" warnings — the whitelist matches real edges and is load-bearing, not decorative | ✓ PASS |
| SC#1 gate | `bash scripts/check_framework_uninstalled.sh` | PASS — 128 tests in a clean off-repo venv; 11 fake-suite files shipped; langchain+langgraph unimportable | ✓ PASS |
| **LIVE: two-turn Ollama conversation with a real fallback hop** | `printf '…chartreuse…\n…what colour…\n' \| paaf chat --config live.yaml --secrets secrets.json --trace-db live.db` | `↳ fell back to local (connection)` twice; `local> That sounds like an interesting choice for you!` then `local> You stated that chartreuse was your favorite color previously!` — **history crossed the hop**. Exit 0 | ✓ PASS |
| **LIVE: degraded-but-reachable trigger** | `paaf chat --config slow.yaml --trace-db slow.db` (`first_token_budget_s: 0.005` on a *reachable* server) | `↳ fell back to patient (slow_first_token)` → `patient> Hi there! How can I help you today?`; trace row records the same reason | ✓ PASS |
| **LIVE: unauthenticated openai_compatible at `/v1`** | `env -u OPENAI_API_KEY paaf chat --config oai2.yaml --trace-db oai2.db` | `vllm_like> banana`, exit 0, `served_by=vllm_like`, `fallback_trail=[]` | ✓ PASS |
| **LIVE: two same-provider endpoints are distinct bindings** | `paaf chat --config two.yaml` (11435 dead, 11434 live) | `↳ fell back to box_b (connection)` → `box_b> banana`. A shared cached client would have let box_a answer | ✓ PASS |
| **LIVE: api_key_ref through a real encrypted store** | `PAAF_SECRET_PASSPHRASE=… paaf chat --config local.yaml --secrets secrets.json` | Anthropic profile **bound** and failed at the socket (`cloud(connection)`), not at bind. Old behavior was `EngineError … no secret store was provided` | ✓ PASS |
| **LIVE: no traceback on any failure surface** | three failing invocations, `grep -c Traceback` | **0** in every case; exit 1 with one readable line | ✓ PASS |
| `paaf prompt` byte-exactness | `paaf prompt --config live.yaml \| od -c` | ends `s e n t e n c e .` — no trailing newline | ✓ PASS |
| `paaf profiles` manifest surface | `paaf profiles --config paaf.yaml` | 4 profiles, capabilities, peers, role markers, inert-graph note | ✓ PASS |
| No `--passphrase` on argv | `paaf chat --help` | Only `--config`, `--show-prompt`, `--secrets`, `--trace-db`. Passphrase is env-only | ✓ PASS |
| Lint | `uv run ruff check packages scripts tests` | **3 errors, all pre-existing and all outside this phase's changed source** — 2× `PLW1510` in `tests/negcontrol/test_import_boundary.py`, 1× `RUF022` in `packages/paaf-core/src/paaf_core/secrets/__init__.py` (git blame: `960edbb`, **Phase 2**). No new findings | ✓ PASS |
| Debt markers | `grep -rn -E "TODO\|FIXME\|XXX\|TBD\|HACK\|PLACEHOLDER"` over all `src/` and `scripts/` | **Zero matches.** The debt-marker gate is clean | ✓ PASS |
| Venv restored | `uv sync --all-packages && pytest -q` | 206 passed, 1 skipped; `langchain importable: False` — workspace returned to its pre-verification state | ✓ PASS |

---

## Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| `scripts/check_framework_uninstalled.sh` | `bash scripts/check_framework_uninstalled.sh` | exit 0 — "PASS: the full paaf-llm fake-adapter suite passes with the agent framework uninstalled"; 128 passed in a clean off-repo venv | PASS |

No `scripts/*/tests/probe-*.sh` exist in this repo; the shell gate above is this phase's equivalent and was executed by the verifier, not read from a SUMMARY. (`check_wheel_independence.sh` was executed in the initial pass and is unchanged by plans 03-10..03-13.)

---

## Requirements Coverage

Requirement IDs declared across all **13** plans' frontmatter: MODEL-01/02/03/04/05/06/08, PERS-01/02/04/05. **This is exactly the ROADMAP phase set — no orphaned and no undeclared IDs.** REQUIREMENTS.md maps no additional ID to Phase 3 (MODEL-07 → Phase 11, PERS-03 → Phase 10).

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| MODEL-01 | 03-01, 03-08, 03-11, 03-12 | Named model profiles — provider, model, endpoint, params — with no code | ✓ SATISFIED | `ModelProfile` + `LlmConfig`; four YAML configs written by hand this session drove `prompt`, `profiles` and `chat` with no code changes |
| MODEL-02 | 03-08, 03-09, 03-11, 03-12 | Ollama, OpenAI-compatible, Anthropic | ✓ SATISFIED (1 live confirmation → human) | **Was ✗ BLOCKED.** Ollama: live conversation. OpenAI-compatible: live conversation at `/v1`, unauthenticated, YAML-only. Anthropic: binds on a store-resolved key and dials a real socket; a live *completion* needs a paid key → human item 1 |
| MODEL-03 | 03-06, 03-10 | Ordered fallback chain surviving an unreachable provider mid-conversation | ✓ SATISFIED | Live: hop taken, history carried, chain restarts from the active profile each turn (two hops in a two-turn session). `test_a_failure_before_the_reply_began_still_falls_back` guards against the Gap-2 fix eating the chain |
| MODEL-04 | 03-02, 03-06, 03-09, 03-13 | Fallback on a degraded-but-reachable provider, not only a hard error | ✓ SATISFIED | **Live** `slow_first_token` against a reachable server, recorded in the trace. Four triggers parametrized against the fake with `test_every_fallback_reason_has_a_trigger_in_this_file` and `test_adapter_error_subclasses_are_all_exercised` making the coverage non-vacuous |
| MODEL-05 | 03-01, 03-07 | Capability manifest + peer graph in YAML, no code | ✓ SATISFIED | Free-text manifest, validated peer graph, surfaced by two commands, inertness negatively controlled, `TurnResult.handoff` hardcoded `None` |
| MODEL-06 | 03-01, 03-08, 03-12 | Same-provider multiple endpoints as distinct profiles | ✓ SATISFIED (physical confirmation → human) | **Live** proof two same-provider endpoints do not share a binding. Also asserted at cache-identity level, incl. two endpoint-less cloud profiles not colliding and two profiles differing only in path or auth flag not colliding |
| MODEL-08 | 03-03, 03-05, 03-06, 03-08, 03-09, 03-10 | Public API exposes only PAAF types, proven with the framework uninstalled | ✓ SATISFIED | The clean-venv gate re-run by the verifier (128 tests, langchain unimportable). `EngineError` joining the port did not weaken it — `ports.py` still imports only stdlib, and import-linter stays 3/0 |
| PERS-01 | 03-04, 03-07 | User writes a base system prompt | ✓ SATISFIED | `LlmConfig.base_prompt`, surfaced verbatim; corroborated by the trace row's `prompts` column |
| PERS-02 | 03-04, 03-07 | Active skills contribute persona fragments | ⚠️ PARTIAL | The composition contract is real and byte-tested; no skill source exists (`load_skill_fragments` → `[]`). Deferred to Phase 6 SC#2 |
| PERS-04 | 03-07 | Final composed prompt inspectable verbatim, exactly as sent | ✓ SATISFIED | Three-way byte identity including the message that crossed the port; `od -c` re-run this session |
| PERS-05 | 03-04, 03-07 | PAAF never injects instructions the user did not write | ✓ SATISFIED | `test_no_hidden_prompt` splits the output back apart; `test_prompt_adds_no_text_of_its_own` reconstructs from raw inputs independent of the composer. The trace row contains the base prompt and nothing else |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | `TODO` / `FIXME` / `XXX` / `TBD` / `HACK` / `PLACEHOLDER` | — | **None found** in any `src/` or `scripts/` file. Debt-marker gate clean |
| `packages/paaf-llm/src/paaf_llm/agent.py` | 281-285 | A provider that streams no content produces a served turn with an **empty reply**, printed as `<profile>> ` with nothing after it and exit 0 | ⚠️ Warning | **Reproduced live.** Ollama's OpenAI-compatible `/v1` shim streams a reasoning model's thinking in a non-standard `reasoning` field with `content: ""`; PAAF drops empty chunks (correctly, so the first-token deadline measures real content), and if the stream ends without content the turn is "served" silently. The behavior is documented and deliberate ("a served turn with an empty reply, not a degraded provider"), but the user gets no signal that the provider returned nothing. Not required or contradicted by any Phase-3 success criterion; flagged because "nothing hidden from the user" is this phase's thesis. Raised for a maintainer decision, not counted as a gap |
| `packages/paaf-llm/src/paaf_llm/profiles.py` | 167-181 | `endpoint_unauthenticated: true` is accepted on a profile that declares **no** `endpoint_host`/`endpoint_port` | ℹ️ Info | `base_url` is then `None`, so the self-describing placeholder credential would be sent to the provider binding's DEFAULT base URL (api.openai.com). No secret leaks and the value announces what it is, but it is a request PAAF sends on the user's behalf to a public endpoint. A one-line validator addition would close it |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 243-246 | The TTY-interactive `click.prompt(hide_input=True)` branch has no test | ℹ️ Info | The *dangerous* half is well covered — on a pipe an absent passphrase is an error and the piped first message is asserted absent from the output (T-03-35). The interactive branch itself is exercised by nothing (`grep -rn "isatty\|hide_input\|click.prompt" packages/paaf-llm/tests/` → zero hits). This is the "one error path with no coverage" the disconfirmation pass is required to name |
| trace DB file mode | — | `--trace-db` creates the SQLite file at `0644` while it stores composed prompts | ℹ️ Info | The secret store is correctly `0600` (verified). Filesystem conventions for the daemon are explicitly Phase 9/10 (APP-*), and `cli.py`'s own docstring says so, so this is a forward note rather than a Phase-3 defect |
| `packages/paaf-llm/src/paaf_llm/cli.py` | 182-190 | `load_skill_fragments` returns `[]` | ℹ️ Info | A documented, named seam (D-09), not a hidden stub. Phase 6 replaces the body; the fragment path is proven now by tests that repoint the source |
| `tests/negcontrol/test_import_boundary.py` · `paaf_core/secrets/__init__.py` | 56, 79 · 17 | 2× `PLW1510`, 1× `RUF022` | ℹ️ Info | Pre-existing, both outside this phase's changed source. `RUF022` traced by `git blame` to `960edbb` (**Phase 2**, 2026-07-25). No new lint findings from plans 03-10..03-13 |

---

## Disconfirmation Pass

Required by the verification protocol; recorded even though the phase passes.

1. **A requirement only partially met.** PERS-02 — the persona-fragment composition contract is byte-tested but there is no skill source, so `load_skill_fragments` returns `[]`. Legitimately deferred to Phase 6 SC#2, and flagged as PARTIAL rather than SATISFIED.
2. **A test that passes without testing the stated behavior.** `test_a_profile_with_api_key_ref_reaches_the_adapter_with_a_working_store` asserts on the store handed to a **spy** factory — it does not itself prove the real `build_engine_adapter` receives it. That joining line is covered only by `test_the_cli_default_adapter_forwards_the_store_to_the_factory`, which lives in the `[engine]`-gated file and therefore **skips in the default `uv run pytest` run**. Mitigated three ways and so not a gap: the dedicated `engine-adapter.yml` CI job runs it with an anti-silent-skip assertion, I ran it myself (35/35), and the live Anthropic bind is independent end-to-end evidence. Worth knowing that the default local suite alone does not cover it.
3. **An error path with no test coverage.** The TTY-interactive passphrase prompt (`cli.py:243-246`) — see Anti-Patterns. The non-TTY refusal is tested; the prompt itself is not.
4. **Does any documented DEVIATION change a must-have's meaning?** No. Plan 03-12 reversed 03-08's "record the missing path as a limitation" stance by making the path *declarable* — which strengthens rather than reinterprets SC#2, and preserves 03-08's actual principle (PAAF appends nothing the user did not write) via `test_base_url_appends_nothing_the_user_did_not_declare`.

---

## Human Verification Required

### 1. Real Anthropic completion (SC#2 / MODEL-02)

**Test:** Store a real Anthropic API key in an encrypted `paaf_core` secret store under the name a profile's `api_key_ref` declares, then `PAAF_SECRET_PASSPHRASE=… paaf chat --config <yaml> --secrets <store>` with that profile active.
**Expected:** A genuine completion from api.anthropic.com printed as `<profile>> <reply>`.
**Why human:** Requires a real, billable credential. Everything up to the wire is proven — the key resolves out of a real encrypted store, the Anthropic profile binds with it, and it opens a real socket. Only provider-side acceptance is outstanding. (03-VALIDATION.md Manual-Only. The initial verification separately observed a genuine `401` from api.anthropic.com, so the transport reaches Anthropic.)

### 2. Physical WAN pull mid-conversation (SC#3 literal wording)

**Test:** Real cloud profile active, real local Ollama in `fallback_chain`. One successful turn, then physically disconnect the WAN, then a second turn.
**Expected:** `↳ fell back to <local> (connection)`, answered locally, history intact.
**Why human:** A physical state change no automated check here can produce. The behavioral equivalent — unreachable active profile → real `ConnectionFailed` → hop to a real local model → history carried — was reproduced live during this verification, so this is confirmation that a WAN cut is indistinguishable from an unreachable endpoint.

### 3. Cold-model first-token budget (MODEL-04 / D-05)

**Test:** Cold-start a 14B Ollama model and send the first turn of a session.
**Expected:** No spurious `slow_first_token` fallback inside the configured `first_token_budget_s` — `warmup()` / `preload()` absorbs the cold-load cost.
**Why human:** 03-VALIDATION.md Manual-Only. Timing against a real cold-loading large model cannot be asserted deterministically offline; the verifier's local model is small and warm.

### 4. Two physical LAN machines (MODEL-06 headline)

**Test:** Point two Ollama profiles at two different physical LAN machines and confirm each answers from its own box (`ollama ps` on each, or distinct model names).
**Expected:** Each named profile is served by its own server.
**Why human:** Only one Ollama server is available here. Distinctness was proven live at the endpoint level (a dead port and a live port did not share a cached client) and at the cache-identity level in tests; two physical boxes is the remaining confirmation.

---

## Gaps Summary

**None.** All four gaps recorded on 2026-08-06 are closed, and each closure was verified by reading the current source and then running the shipped `paaf chat` against a real provider — not by reading a SUMMARY.

The shape of the original finding was "the shipped command does not wire the optional collaborators the library so carefully accepts." That is no longer true of any of them:

- the secret store reaches the adapter factory, and a real encrypted store's key binds a real cloud profile;
- the trace sink reaches the agent, and rows land on disk with the same reason string the user was shown;
- `EngineError` lives in the port, so a framework-free CLI names it in an `except` clause and three named failure surfaces print one line instead of a traceback;
- an OpenAI-compatible server under `/v1` with no credential is declarable in YAML and **held a real conversation**, closing the one provider that had zero binding-level coverage — the coverage hole that let both of that gap's defects ship.

The closure plans also did the harder thing: each fix ships with a negative control that would turn red if the fix became a catch-all (`test_an_unexpected_exception_still_escapes` for the error handlers, `test_a_failure_before_the_reply_began_still_falls_back` for the fallback chain, `test_a_config_with_no_api_key_ref_never_opens_a_store` for the secret store, `test_an_openai_compatible_profile_without_the_auth_declaration_still_needs_a_credential` for the no-auth flag, `test_chat_without_a_trace_db_writes_nothing` for the trace). Suite grew 174 → 206 (no extra) and 200 → 241 (with extra) with zero regressions, zero new lint findings, zero debt markers, and the import boundary still 3 kept / 0 broken.

Status is `human_needed` rather than `passed` solely because four confirmations require resources this repo cannot supply: a paid API key, a physical WAN cut, a cold 14B model, and a second LAN machine.

### Verifier Side Effects (disclosed)

- Installed the `[engine]` extra to run the framework-present suite, then **restored** the workspace with `uv sync --all-packages` and re-confirmed 206 passed / 1 skipped with `langchain importable: False`.
- Sent requests to a **local** Ollama server on `127.0.0.1:11434` (native API and its OpenAI-compatible `/v1` shim). **No outbound WAN request was made and no real credential was used** — the only Anthropic profile exercised was pointed at `127.0.0.1:9` and carried a fake key value (`sk-ant-NOT-A-REAL-KEY-…`) written into a throwaway encrypted store under the session scratchpad.
- All config files, secret stores and trace databases were written under the session scratchpad, not the repository.

---

_Verified: 2026-08-06T17:02:03Z_
_Verifier: Claude (gsd-verifier) — re-verification after gap closure_
