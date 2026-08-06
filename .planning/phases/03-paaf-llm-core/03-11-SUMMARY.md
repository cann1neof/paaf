---
phase: 03-paaf-llm-core
plan: 11
subsystem: cli
tags: [python, click, secrets, credentials, core-04, tdd, gap-closure]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "LangChainAdapter(secret_store=...) and its api_key-by-reference resolution; build_engine_adapter's optional secret_store keyword; paaf_core.secrets.EncryptedFileSecretStore; ModelProfile.api_key_ref; ports.EngineError as a framework-free catchable type (03-10)"
provides:
  - "paaf chat --secrets PATH — an api_key_ref profile is served from a real paaf_core encrypted store (Gap 1 of 03-VERIFICATION closed)"
  - "cli.profiles_needing_secrets — the single place that decides whether a config needs a secret store at all"
  - "cli.open_secret_store — the unlock path, with all three failure modes named and none echoing the passphrase"
  - "PAAF_SECRET_PASSPHRASE as the passphrase channel; deliberately NOT a CLI option (T-03-32)"
  - "An executing test over the cli->factory seam, so dropping the store argument again turns the suite red rather than only failing a grep"
affects: [03-12, 03-13, 04-agent-mesh, 09-embedded-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A credential channel is chosen by threat model, not ergonomics: a passphrase on argv is visible in ps and shell history, so no --passphrase option exists at any cost in convenience"
    - "An interactive prompt must be gated on isatty() whenever the command also reads data from stdin — otherwise the prompt silently eats the user's first line"
    - "An error message about a failed unlock interpolates the PATH only; the supplied secret is the one thing that must never reach a terminal or a pasted bug report"
    - "When both sides of a seam are covered by stubs, the seam itself is uncovered — cover it with a test that executes the joining function's body"

key-files:
  created: []
  modified:
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/test_inspector.py
    - packages/paaf-llm/tests/test_engine_adapter.py

key-decisions:
  - "The --secrets help text interpolates SECRET_PASSPHRASE_ENV rather than repeating the literal string, so the variable the CLI documents and the variable it reads cannot drift. This also made the plan's 'exactly one occurrence' criterion true by construction rather than by accident."
  - "InvalidPassphraseError is imported in Task 2 where it is first used, not in Task 1 alongside EncryptedFileSecretStore as the plan's action text suggested — an import one task ahead of its use is a ruff failure, which is exactly the issue 03-10 hit and recorded."
  - "The missing-path and missing-passphrase guards landed in Task 1, not Task 2. Without them a config declaring api_key_ref invoked without --secrets dies in Path(None) and one without the env var dies in None.encode — two fresh traceback surfaces at a task boundary, in a phase whose previous plan existed to remove tracebacks."
  - "The cli->factory seam test was mutation-checked rather than merely written: cli.py's call site was temporarily reverted to build_engine_adapter(config) and the test was confirmed to fail with 'assert None is <_Secrets>'. A test asserted to be a regression control without ever being seen to fail is a claim, not a control."

patterns-established:
  - "Mutation-check a regression test before trusting it: re-introduce the exact defect it names and observe it fail"
  - "Threat-driven CLI surface design: T-03-32 removes an option, T-03-35 gates a prompt, T-03-33 constrains an error string's interpolation"

requirements-completed: [MODEL-01]

coverage:
  - id: D1
    description: "A profile declaring api_key_ref is served by paaf chat from a REAL paaf_core encrypted store — not from YAML and not from the provider SDK's own environment variable"
    requirement: MODEL-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_profile_with_api_key_ref_reaches_the_adapter_with_a_working_store"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_the_factory_carries_a_secret_store_through_to_key_resolution"
        status: pass
    human_judgment: false
  - id: D2
    description: "A config in which NO profile declares api_key_ref never opens a secret store and never asks for a passphrase"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_config_with_no_api_key_ref_never_opens_a_store"
        status: pass
    human_judgment: false
  - id: D3
    description: "A missing --secrets path, an unsupplied passphrase, and a wrong passphrase each produce one readable line naming what to do — never a traceback and never the passphrase itself"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_api_key_ref_without_a_secrets_path_is_a_readable_error"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_missing_passphrase_on_a_pipe_is_a_readable_error"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_a_wrong_passphrase_is_readable_and_never_echoed"
        status: pass
    human_judgment: false
  - id: D4
    description: "The passphrase is never accepted as a command-line argument, so it cannot appear in ps output or shell history"
    verification:
      - kind: other
        ref: "uv run paaf chat --help — lists --secrets, lists no passphrase option"
        status: pass
    human_judgment: false
  - id: D5
    description: "cli._default_adapter's forwarding of the store into build_engine_adapter is proven by a test that executes its body, not by a source grep alone"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_the_cli_default_adapter_forwards_the_store_to_the_factory"
        status: pass
      - kind: other
        ref: "mutation check — cli.py call site reverted to build_engine_adapter(config); the test failed with 'assert None is <_Secrets>'; call site restored"
        status: pass
    human_judgment: false
  - id: D6
    description: "The reproduced Gap 1 failure is encoded as a permanent test, and is NOT an AdapterError so the fallback chain can never swallow a missing credential"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_the_factory_without_a_store_fails_as_a_config_error"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-08-06
status: complete
---

# Phase 3 Plan 11: `api_key_ref` Works From `paaf chat` Summary

**The credential mechanism the schema advertises is now the one that works — `paaf chat --secrets` unlocks a real `paaf_core` encrypted store, an all-local config is never asked for a passphrase, and the passphrase has no path to `argv`**

## Performance

- **Duration:** 12 min
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 3
- **Files created:** 0

## Accomplishments

- **Closed Gap 1 of `03-VERIFICATION.md`** (blocks SC#2, classified 🛑 Blocker). `cli._default_adapter` called `build_engine_adapter(config)` with one argument, so `self._secret_store` was `None` in every real invocation and ANY profile declaring `api_key_ref` died at bind. One argument was the defect; the surrounding question — *where do the path and passphrase come from* — is what the plan actually had to answer.
- **Wired, not documented away** (D-G2). A profile naming `api_key_ref` now resolves its key out of a real `EncryptedFileSecretStore`, proven by a test that writes and unlocks an actual encrypted file on disk rather than substituting a stub resolver. A stub would have passed against a CLI that never opened a store at all — which is precisely the bug.
- **The negative control is half the feature.** `open_secret_store` returns `None` and touches nothing before it looks at a path or a passphrase, so an all-local config is never asked to unlock anything (T-03-34). The test replaces `cli.EncryptedFileSecretStore` with a callable that fails the test if constructed.
- **Covered the seam, not just its two sides.** Every test in `test_inspector.py` replaces `_default_adapter` wholesale; every engine test calls `build_engine_adapter` directly. The one line joining them was executed by nothing — and it was the line that was short an argument. That is the shape of miss that let Gap 1 ship past a green suite, and it is now covered by a test whose failure was observed, not assumed.

## Task Commits

Each task committed atomically, RED before GREEN:

1. **Task 1: `api_key_ref` resolves through `paaf chat`** — `9f5a65f` (test, RED) → `dd8d754` (feat, GREEN)
2. **Task 2: every failure mode says what to do** — `5cea3f2` (test, RED) → `ddd9c6e` (feat, GREEN)
3. **Task 3: pin the factory seam** — `e2cbfd5` (test)

No REFACTOR commits were needed.

RED was observed, not assumed:

- Task 1 RED: `AttributeError: module 'paaf_llm.cli' has no attribute 'EncryptedFileSecretStore'` — both new tests failed, 23 existing passed.
- Task 2 RED: `<Result InvalidPassphraseError('could not unlock secret store with the supplied passphrase')>` — the exception escaping `paaf chat` uncaught is visible in the failure output.
- Task 3 is a test-only task, so its RED is a **mutation check** rather than a pre-implementation failure: `cli.py`'s call site was reverted to `build_engine_adapter(config)`, `test_the_cli_default_adapter_forwards_the_store_to_the_factory` was confirmed to fail with `assert None is <_Secrets object>`, and the call site was restored (`git diff` against HEAD then reported no change to `cli.py`).

## The final text of all four constants

Recorded verbatim as the plan's `<output>` section requires. All four live in `packages/paaf-llm/src/paaf_llm/cli.py` as module constants, following the file's existing convention (`FALLBACK_NOTICE`, `CONFIG_FAILURE_NOTICE`, …) so tests assert against the text the CLI actually emits.

```python
SECRET_PASSPHRASE_ENV = "PAAF_SECRET_PASSPHRASE"

SECRETS_PATH_REQUIRED = (
    "these profiles declare an api_key_ref: {profiles}. The key value is never "
    "read from YAML, so name the encrypted store holding it with --secrets, and "
    "supply that store's passphrase in the {env} environment variable."
)

PASSPHRASE_REQUIRED = (
    "the secret store cannot be unlocked: no passphrase was supplied and stdin "
    "is not a terminal, so there is nothing to prompt. Set the passphrase in the "
    "{env} environment variable."
)

SECRET_STORE_LOCKED = (
    "the secret store at {path} could not be unlocked with the supplied "
    "passphrase. Check the passphrase, and that this is the right store file."
)
```

`SECRET_STORE_LOCKED` interpolates `{path}` and nothing else. `grep -c 'passphrase=' cli.py` returns `0` — no `.format(` call anywhere in the file passes a passphrase.

## The resolved passphrase-precedence order

Also required verbatim by the plan's `<output>`. `open_secret_store` resolves in this order, and the **early return precedes all of it**:

0. **If no profile declares `api_key_ref` → return `None` immediately.** Nothing below is reached, the filesystem is not touched, and no passphrase is looked for. An all-local config is never asked to unlock anything.
1. **`PAAF_SECRET_PASSPHRASE`** from the environment. `chat` reads it with `os.environ.get(SECRET_PASSPHRASE_ENV)` and passes the value in as the `passphrase` argument.
2. **A hidden `click.prompt`** — but only if `click.get_text_stream("stdin").isatty()`.
3. **Otherwise `PASSPHRASE_REQUIRED`**, a non-zero exit naming the environment variable.
4. **Never `argv`.** There is no `--passphrase` option at any tier (T-03-32).

Step 2's TTY gate is load-bearing rather than defensive: `paaf chat` reads the conversation itself from stdin, so prompting on a pipe would consume the user's first message and feed it to the scrypt KDF — producing a "wrong passphrase" error about a line they meant as a question (T-03-35). `test_a_missing_passphrase_on_a_pipe_is_a_readable_error` asserts the piped string is absent from the output, which is what pins it.

The TTY branch is the one path no plan-specified test reaches (`CliRunner`'s stdin is never a TTY). It was verified directly before commit by calling `open_secret_store` with `isatty()` forced true and `click.prompt` stubbed; it resolved the real store's key.

## Gap 1's reproduced `EngineError` is now a permanent test

Stated explicitly, as the plan's `<output>` requires. The verifier reproduced this twice:

```
EngineError: could not bind 'anthropic:claude-sonnet-4-5': profile declares
api_key_ref 'anthropic_key' but no secret store was provided
```

It is now covered by **`test_the_factory_without_a_store_fails_as_a_config_error`** in `packages/paaf-llm/tests/test_engine_adapter.py`. The test builds that exact profile, goes through `build_engine_adapter(config)` with no store, and asserts three things: `EngineError` is raised, the message names `"anthropic_key"`, and — the load-bearing one — `not isinstance(raised.value, AdapterError)`. If a missing credential were ever reclassified as a degraded provider, the ordered fallback chain would swallow it and quietly let another model answer for the cloud profile the user configured, leaving them believing it works.

## Files Modified

- **`packages/paaf-llm/src/paaf_llm/cli.py`** — `import os`; `from paaf_core.secrets import EncryptedFileSecretStore, InvalidPassphraseError` at module scope (safe: `paaf_core` is a declared base dependency and framework-free, unlike the adapter package whose import must stay lazy); `SecretResolver` added to the `TYPE_CHECKING` import from `.agent`; the four constants above; `profiles_needing_secrets`; `open_secret_store`; `_default_adapter` gained `secret_store` and now calls `build_engine_adapter(config, secret_store=secret_store)`; `build_agent` gained a keyword-only `secret_store`; `chat` gained `--secrets` and calls `open_secret_store` between `render_profiles` and `build_agent`.
- **`packages/paaf-llm/tests/test_inspector.py`** — `inject()` now installs a two-parameter factory; new `spy_adapter_factory`, `secret_store_at`, and `config_with_a_key_ref` helpers; five new tests across two new sections.
- **`packages/paaf-llm/tests/test_engine_adapter.py`** — `import paaf_llm._engine as engine_module` and `from paaf_llm import cli`; new `_cloud_with_a_ref` helper; three new tests; the stale docstring on `test_build_engine_adapter_is_the_factory_the_cli_imports` corrected.

**No new test file was added** (Constraint 2, confirmed). The SC#1 gate's non-vacuity guard reports `ok: all 11 fake-adapter test files ship in the wheel` — the same count as before this plan, so neither `pyproject.toml`'s `force-include` nor `EXCLUDED_FROM_WHEEL` needed touching. **No dependency was added and no `pyproject.toml` was modified** — `cryptography` already arrives through the declared `paaf-core` dependency.

## Constraints Honoured

| # | Constraint | Status |
|---|---|---|
| 1 | Do not modify `03-01`…`03-09` or any `-SUMMARY.md` | Held — no planning file touched except this new summary |
| 2 | No new test file under `packages/paaf-llm/tests/` | Held — 11 shipped test files, unchanged count |
| 3 | Tests import only `paaf_llm`/`paaf_core`/`paaf_trace` + stdlib | Held — `paaf_core.secrets` only; SC#1 clean-venv gate passes |
| 4 | No `--passphrase` option | Held — `paaf chat --help` lists none |
| 5 | `Agent.build`'s `secret_store=` stays unused | Held — `build_agent` forwards to `_default_adapter` only, and its docstring says why |
| 6 | No eager "does every declared ref resolve?" startup check | Held — the adapter's own `EngineError` remains the single implementation of that rule |

## Deviations from Plan

Three, all inside the plan's stated intent. None changed scope.

### Adjustments

**1. `InvalidPassphraseError` imported in Task 2, not Task 1**
- **Found during:** Task 1 GREEN
- **Issue:** The plan's Task 1 action text says to add `from paaf_core.secrets import EncryptedFileSecretStore, InvalidPassphraseError`. `InvalidPassphraseError` has no use until Task 2's `try`/`except`, so importing it in Task 1 is an unused import — a ruff failure at the exact task boundary. 03-10 recorded this same issue with `ServerError` imported one task before use.
- **Fix:** Task 1 imports `EncryptedFileSecretStore`; Task 2 widens the import to include `InvalidPassphraseError` where it is first used. `uv run ruff check packages/paaf-llm` reports **All checks passed** at every commit.
- **Committed in:** `dd8d754` / `ddd9c6e`

**2. [Rule 1 — Bug] The `--secrets` help text repeated the env-var literal**
- **Found during:** Task 1 acceptance-criteria check
- **Issue:** `grep -c 'PAAF_SECRET_PASSPHRASE' cli.py` returned `2`, not the required `1` — the option's help text spelled the variable out instead of going through `SECRET_PASSPHRASE_ENV`. This is not merely a count problem: the variable the CLI *documents* and the variable it *reads* were two independent strings, free to drift.
- **Fix:** The help text is now an f-string interpolating the constant (click evaluates it at decoration time). Count is `1`, and `paaf chat --help` still renders the variable name correctly — verified in the rendered output.
- **Committed in:** `dd8d754`

**3. [Rule 3 — Blocking] A pre-existing test patched `_default_adapter` outside the `inject()` helper**
- **Found during:** Task 1 GREEN
- **Issue:** `test_a_build_time_failure_is_reported_readably` (added by 03-10) monkeypatches `cli._default_adapter` with its own local one-argument `explode()` rather than going through `inject()`. Once `build_agent` began calling the factory with two positional arguments it failed with `TypeError: explode() takes 1 positional argument but 2 were given`. The plan anticipated only the `inject()` edit.
- **Fix:** Widened `explode`'s signature to `(_config, secret_store=None)`. The test's assertions are unchanged; it still passes for the reason it was written.
- **Committed in:** `dd8d754`

---

**Total deviations:** 3 (1 lint-ordering adjustment, 1 real drift bug fixed, 1 blocking signature fix)
**Impact on plan:** None on scope.

## Issues Encountered

- Ruff's isort flagged the new import block in `test_engine_adapter.py` (`import paaf_llm._engine as engine_module` placed after the `from langchain_core...` block). Fixed with `ruff check --fix` on that file. No other lint issue arose.
- Nothing else. No architectural question arose and no checkpoint was needed.

## Verification Results

All five of the plan's `<verification>` steps were run:

| # | Check | Result |
|---|-------|--------|
| 1 | `uv run pytest packages/paaf-llm packages/paaf-core -q --disable-socket` | **162 passed, 1 skipped** (the skip is `test_engine_adapter.py`'s `importorskip`) |
| 2 | `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` | **30 passed, 0 skipped** — the `importorskip` guard passed with the extra installed, so all three new tests genuinely RAN |
| 3 | `uv sync --all-packages` then `uv run pytest -q --disable-socket` (whole workspace) | **185 passed, 1 skipped** |
| 4 | `uv run lint-imports --no-cache` | **3 contracts kept, 0 broken** — `cli.py` gained a `paaf_core` import only; the adapter package's whitelist is untouched |
| 5 | `uv run paaf chat --help` | `--secrets FILE` is documented; **no passphrase option exists** |

Additional gates run beyond the plan's list:

- `bash scripts/check_framework_uninstalled.sh` — **PASS**. Builds the wheels, installs into a clean venv with no `[engine]` extra, and runs the full fake-adapter suite there (**113 passed**, up from 108 — the five new `test_inspector.py` tests ship in the wheel and run where `langchain`/`langgraph` are proven not importable). This matters specifically for Constraint 3: the new tests import `paaf_core.secrets`, and this gate is what proves `cryptography` is genuinely present in the framework-uninstalled install.
- `uv run ruff check packages/paaf-llm` — **All checks passed**.

Acceptance-criteria greps, all satisfied:

| Criterion | Required | Result |
|---|---|---|
| `grep -c 'build_engine_adapter(config, secret_store=secret_store)' cli.py` | `1` | `1` |
| `grep -c 'from ._engine import' cli.py` | `1` | `1` |
| `grep -c 'PAAF_SECRET_PASSPHRASE' cli.py` | `1` | `1` |
| `grep -c 'EncryptedFileSecretStore' test_inspector.py` | ≥ `2` | `4` |
| `grep -c 'SECRETS_PATH_REQUIRED\|PASSPHRASE_REQUIRED\|SECRET_STORE_LOCKED' cli.py` | ≥ `6` | `6` |
| `grep -c 'isatty' cli.py` | ≥ `2` | `2` |
| `grep -c 'passphrase=' cli.py` (no `.format` leaks the secret) | `0` | `0` |
| AST check: `test_build_engine_adapter_is_the_factory_the_cli_imports` docstring mentions `secret_store` and the new seam test | prints `ok` | `ok` |
| All five new `test_inspector.py` names collect | yes | yes |
| All three new `test_engine_adapter.py` names collect | yes | yes |

## Threat Model Disposition

| Threat ID | Disposition | Status |
|---|---|---|
| T-03-32 (passphrase on the command line, visible in `ps` and shell history) | mitigate | **Held.** No `--passphrase` option is declared at any level; `paaf chat --help` lists none. The passphrase arrives via `PAAF_SECRET_PASSPHRASE` or a `click.prompt(hide_input=True)` on a TTY. |
| T-03-33 (wrong-passphrase error echoing the passphrase back) | mitigate | **Held.** `SECRET_STORE_LOCKED` interpolates `{path}` only; `grep -c 'passphrase='` returns `0`. `test_a_wrong_passphrase_is_readable_and_never_echoed` asserts `"the-wrong-one"` is absent from the output. |
| T-03-34 (unlocking a store a config never asked for) | mitigate | **Held.** `open_secret_store` returns `None` before touching the filesystem when `profiles_needing_secrets` is empty. The control replaces the store class with a callable that fails the test if constructed. |
| T-03-35 (a piped stdin line consumed as a passphrase) | mitigate | **Held.** The prompt sits behind `click.get_text_stream("stdin").isatty()`; a non-TTY without the environment variable raises `PASSPHRASE_REQUIRED`. The test asserts the piped input string never appears in the output. |
| T-03-04 (existing — a provider echoing a rejected credential back) | mitigate | **Held, unchanged.** `LangChainAdapter._scrub` and `test_a_resolved_key_never_appears_in_a_raised_message` are untouched and re-ran green in the 30-test engine-adapter run. |
| T-03-SC (package installs) | mitigate | **Held vacuously, as intended.** No package was installed and no dependency list was edited; `packages/paaf-llm/pyproject.toml` is untouched. `cryptography` already arrives through the declared `paaf-core` dependency, covered by Phase 2's Package Legitimacy Audit. |

No new security-relevant surface beyond the threat register: no network endpoint, no auth path, no schema change. **One new file-access pattern** — `paaf chat` now opens a user-named file at a path supplied on the command line — and it is already the subject of T-03-33/T-03-34 above. `click.Path(exists=True, dir_okay=False, readable=True)` rejects a directory or an absent file before the store constructor sees it. No threat flags.

## Known Stubs

None. Nothing in this plan renders placeholder data or leaves a component unwired. `load_skill_fragments` remains the D-09 stub it already was — untouched by this plan.

## Scope Note — what this plan does NOT claim

- **MODEL-01** is claimed: a profile the user declared in YAML, naming its credential by reference, is now actually loadable and usable from the shipped command. That is the requirement's own property, and it was not true before this plan.
- **MODEL-02 is deliberately NOT claimed**, despite appearing in this plan's frontmatter `requirements` list. No task here adds, changes, or tests provider support. What this plan does is make the *Anthropic leg of SC#2* reachable offline-verifiably; MODEL-02's OpenAI-compatible leg is 03-12's work, exactly as 03-10 recorded. Marking MODEL-02 complete here would overstate the phase's requirement table.
- **SC#2 is not fully closed by automation.** Every acceptance criterion in this plan is checkable offline. The live Anthropic round-trip is the manual step below.
- `REQUIREMENTS.md` was intentionally **not** edited by this worktree agent — requirement bookkeeping is a shared-file write the orchestrator owns after the wave merges.

## User Setup Required

None for the tests — every check in this plan is decidable offline under `--disable-socket`.

**Manual verification this plan makes possible** (do not automate — no test may contact a real provider):

```bash
# 1. Put a real key in an encrypted store
python -c "from paaf_core.secrets import EncryptedFileSecretStore; \
  EncryptedFileSecretStore('secrets.json', 'your-passphrase').set('anthropic_key', 'sk-ant-...')"

# 2. Reference it by NAME in your config — the value never enters YAML
#    profiles: {cloud: {provider: anthropic, model: claude-sonnet-4-5,
#                       api_key_ref: anthropic_key}}

# 3. Talk to it, with ANTHROPIC_API_KEY deliberately NOT set
unset ANTHROPIC_API_KEY
export PAAF_SECRET_PASSPHRASE='your-passphrase'
echo "hello" | uv run paaf chat --config paaf.yaml --secrets secrets.json
```

Reaching the provider with `ANTHROPIC_API_KEY` unset is the live confirmation of SC#2's Anthropic leg — it proves the key came from PAAF's store rather than from the provider SDK's own environment variable, which is the entire point of `api_key_ref`.

## Next Phase Readiness

- **Gap 1 is closed.** `api_key_ref` works end to end from the shipped command. 03-12 and 03-13 touch different concerns and nothing here blocks them.
- **`open_secret_store` is the seam Phase 9 (APP-*) will want.** This plan deliberately invented no default secrets path — a guessed filesystem convention here is one the embedded app would later have to disagree with. Phase 9 owns boot-time passphrase delivery (as `fernet_backend.py` already documents); it can supply both arguments to this function without changing it.
- **Environment note for the next executor:** the worktree is left synced with `uv sync --all-packages` (no `[engine]` extra), matching the documented baseline. `packages/paaf-llm` reports **107 passed, 1 skipped** in that state; `packages/paaf-llm packages/paaf-core` together report **162 passed, 1 skipped**.

## Self-Check: PASSED

- All 3 claimed files verified present on disk.
- All 5 claimed commits verified present in `git log`.
- `git diff --diff-filter=D --name-only a967c5b HEAD` reports no deleted files — nothing was removed by this plan.
- `git diff` against HEAD confirmed `cli.py` was restored byte-identically after the Task 3 mutation check.
- Working tree clean; no uncommitted changes remained before this summary.

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-06*
