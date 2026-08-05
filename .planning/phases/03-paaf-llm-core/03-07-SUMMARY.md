---
phase: 03-paaf-llm-core
plan: 07
subsystem: cli
tags: [cli, click, rich, inspector, prompt, byte-identity, framework-free, mutation-tested]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "plan 03-06's Agent.build/turn/warmup/system_prompt and TurnResult.fallback_trail"
  - phase: 03-paaf-llm-core
    provides: "plan 03-05's ChatAdapter port, AllProvidersFailed, ConnectionFailed, and the shipped FakeAdapter"
  - phase: 03-paaf-llm-core
    provides: "plan 03-04's PromptComposer.compose/segments + SEGMENT_SEPARATOR (the one derivation)"
  - phase: 03-paaf-llm-core
    provides: "plan 03-01's LlmConfig/ModelProfile — capabilities, peers, constraints, and validate-on-read"
provides:
  - "paaf prompt — a pure dry run whose stdout IS the composed prompt, byte for byte, with no trailing newline"
  - "paaf prompt --provenance — the same content labeled base / skill:<name> (D-03)"
  - "paaf chat — a thin turn loop with --show-prompt, per-hop fallback notices, and the manifest header"
  - "paaf profiles — the non-interactive capability-manifest + peer-graph surface (MODEL-05)"
  - "cli.build_agent(config, adapter=...) — the fake-injection seam; cli._default_adapter(config) — the lazy real-adapter factory plan 03-08 fills"
  - "cli.load_skill_fragments(config) — the ONE D-09 fragment source both the agent and the inspector read"
  - "cli.load_llm_config(path) — YAML safe_load validated through LlmConfig, ValidationError rendered as a readable ClickException"
  - "packages/paaf-llm/tests/test_inspector.py — 18 tests: three-way byte-identity, 6 negative controls, 2 SC#1 guards"
affects: [03-08-engine-adapter, 03-09-trace-wiring, 04-agent-mesh, 06-skills]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The inspector prints the agent's OWN derivation (Agent.system_prompt) rather than a parallel one — byte-identity by construction, not by discipline"
    - "A named fragment-source seam (load_skill_fragments) both the agent and the inspector call, so a Phase-6 change cannot make them diverge"
    - "stdout with nl=False for correctness-bearing output: the command's stdout IS the artifact, so `> file` and `diff` are meaningful"
    - "Console(markup=False, highlight=False, soft_wrap=True) — user config text is rendered as text and can never restyle or hide the output around it"
    - "Mutation-checking a byte-identity claim: inject a hidden preamble, confirm the suite goes red, restore"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/test_inspector.py
  modified: []

key-decisions:
  - "`paaf prompt` emits NO trailing newline — stdout is byte-identical to what the model receives, so `paaf prompt > sent.txt` + `diff` is a real audit"
  - "`--show-prompt` calls Agent.system_prompt() directly instead of re-composing: the strongest available form of D-02"
  - "load_skill_fragments is a named function returning [] rather than an inline literal — it is the single seam Phase 6 replaces, and both entry points read it"
  - "Tests inject through cli._default_adapter, not by stubbing build_agent: the command's own wiring stays inside the test"
  - "Config is read with yaml.safe_load (a hand-edited config is untrusted input) and validated by LlmConfig — the CLI parses no fields and knows no defaults"
  - "rich is used for decoration only; every correctness-bearing byte goes through click.echo"
  - "A `profiles` subcommand AND a chat startup header, both rendering through one render_profiles — MODEL-05 is surfaced whether or not the user starts a conversation"

requirements-completed: [MODEL-05, PERS-01, PERS-02, PERS-04, PERS-05]

coverage:
  - id: D1
    description: "One command prints the byte-exact composed prompt, identical to the system message the adapter actually received (SC#5)"
    requirement: PERS-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_prompt_byte_exact"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_prompt_byte_exact_with_skill_fragments"
        status: pass
    human_judgment: false
  - id: D2
    description: "The printed prompt contains the base prompt and the skill fragments and NOTHING the user did not write"
    requirement: PERS-05
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_prompt_adds_no_text_of_its_own"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_provenance_is_not_the_default"
        status: pass
    human_judgment: false
  - id: D3
    description: "The base prompt (PERS-01) and each skill persona fragment (PERS-02) reach the model in the user's declared order"
    requirement: PERS-02
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_prompt_byte_exact_with_skill_fragments"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_provenance_same_content"
        status: pass
    human_judgment: false
  - id: D4
    description: "The opt-in provenance view renders the SAME content with source labels; concatenating its segments reproduces the raw view (D-03)"
    requirement: PERS-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_provenance_same_content"
        status: pass
    human_judgment: false
  - id: D5
    description: "Each profile's capability manifest and peer graph is surfaced as inert data and no handoff is performed (SC#4)"
    requirement: MODEL-05
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_manifest_surfaced"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_manifest_performs_no_handoff"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_profiles_command_surfaces_the_same_manifest"
        status: pass
    human_judgment: false
  - id: D6
    description: "NEGATIVE CONTROL — a fallback prints one brief inline notice per hop, and a healthy turn prints none (D-06)"
    requirement: MODEL-05
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_fallback_notice"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_healthy_turn_prints_no_fallback_notice"
        status: pass
    human_judgment: false
  - id: D7
    description: "NEGATIVE CONTROL — the dry run constructs no adapter, and --show-prompt is the only way the prompt reaches chat output"
    requirement: PERS-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_prompt_calls_no_model"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_chat_without_show_prompt_stays_quiet"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_show_prompt_echoes_what_was_sent"
        status: pass
    human_judgment: false
  - id: D8
    description: "The CLI runs framework-uninstalled: _engine is imported inside a function and importing paaf_llm.cli loads neither it nor the framework (SC#1)"
    requirement: PERS-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_engine_import_is_lazy_in_the_source"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_importing_the_cli_loads_no_framework_and_no_engine"
        status: pass
      - kind: integration
        ref: "uv run lint-imports (3 contracts kept, 0 broken)"
        status: pass
    human_judgment: false

# Metrics
duration: 30min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 07: Prompt Inspector + Chat CLI Summary

**`paaf prompt` now writes to stdout the exact bytes your model receives — not a rendering of them, not a reconstruction, and not one byte more, verified against the system message the adapter actually got.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 3 (3 commits)
- **Files created:** 2 (1 source, 1 test)
- **Tests added:** 18 (156 → 174 in the packages suite)

## Accomplishments

- **PERS-04 is a byte comparison, not a claim.** `test_prompt_byte_exact` asserts a *three-way* identity: the CLI's stdout, `PromptComposer.compose(...)`, and **the `system` message read back off `FakeAdapter.calls` after a real turn**. Only the third leg closes the loop — comparing the CLI to the composer alone would pass even if the agent sent something else entirely. That is the difference between "the inspector calls the composer" and "the inspector shows what crossed the port" (T-03-17/T-03-18).
- **`paaf prompt` emits no trailing newline.** stdout *is* the prompt, so `paaf prompt --config x.yaml > sent.txt` captures the exact bytes and `diff` against a captured prompt is meaningful. PERS-04 becomes a property of the byte stream rather than a paragraph about it.
- **The claim was mutation-checked, not just asserted.** Injecting a hidden `"Be helpful and safe.\n\n"` preamble into the CLI — precisely the T-03-18 threat, and precisely what the project's anti-feature list forbids — turns **4 tests red**. Silently dropping every skill fragment turns **3 red**. Both mutations were applied, observed, and reverted (`git diff --stat` clean afterward).
- **There is one fragment source, and it is a named seam.** `load_skill_fragments(config)` is called by `build_agent` *and* by `prompt`. Phase 6 replaces its body with real skill discovery and both entry points move together — byte-identity by construction rather than by anyone remembering. Because that stub returns `[]` today, a dedicated negative control re-runs the whole identity with **non-empty** fragments; without it the headline test would also pass against a CLI that silently dropped every skill.
- **`--show-prompt` calls `Agent.system_prompt()` itself.** Not "the same composer" — the agent's own method. The strongest available form of D-02.
- **MODEL-05 is surfaced and provably inert.** `test_manifest_performs_no_handoff` declares `cloud` as `local`'s peer and leaves `cloud` **unprogrammed**: the fake raises `LookupError`, which is pointedly *not* an `AdapterError` the fallback loop could swallow. A green run is positive evidence that nothing routed on the peer graph.
- **Config text cannot style the terminal.** The `rich` console is built `markup=False, highlight=False`, so a `capabilities` string containing `[/]` or `[black on black]` cannot restyle, hide, or truncate the output around it. Everything correctness-bearing bypasses rich entirely and goes through `click.echo`.

## Task Commits

1. **Task 1: `paaf chat` — turn loop, `--show-prompt`, fallback notice, manifest surface** — `923776a` (feat)
2. **Task 2: `paaf prompt` — byte-exact dry run + `--provenance`** — `1b0d02d` (feat)
3. **Task 3: `test_inspector.py` — byte-identity, provenance, manifest, notices, SC#1 guards** — `3a5261c` (test)

## Files Created

- `packages/paaf-llm/src/paaf_llm/cli.py` (created) — the `main` click group wired as the `paaf` script, with `chat` (`--show-prompt`), `prompt` (`--provenance`), and `profiles`; plus `load_llm_config`, `load_skill_fragments`, `build_agent`, `_default_adapter`, and `render_profiles`. Imports `click`, `yaml`, `pydantic`, `rich`, and three sibling PAAF modules — no agent framework, and no `_engine` at module scope.
- `packages/paaf-llm/tests/test_inspector.py` (created) — 18 tests across five groups: PERS-04 byte-identity (4, incl. 2 negative controls), D-03 provenance (2), MODEL-05 manifest (3), D-06 chat surface (5), SC#1 framework-freedom (4).

## Decisions Made

- **`paaf prompt` writes no trailing newline.** A newline is conventional but it is still a byte the user did not write, and its absence is what makes `>` + `diff` an audit rather than an approximation. Documented in the command's docstring so the omission reads as deliberate.
- **`--show-prompt` calls `Agent.system_prompt()`, `paaf prompt` calls `compose(...)` with the shared fragment source.** `prompt` must construct no adapter (a pure dry run), and `Agent` requires one, so it cannot hold an agent. Passing the *same* pure function the *same* arguments makes the two byte-identical by construction, and the test asserts it against the message the adapter received rather than trusting the argument.
- **`load_skill_fragments` exists as a function returning `[]`.** An inline `[]` in each command would be two stubs, and Phase 6 would have to find both. This is the D-09 seam, named once.
- **Tests inject through `cli._default_adapter`, not by stubbing `build_agent`.** Patching the adapter *factory* keeps the command's own wiring — config load, fragment source, agent construction, warmup — inside the test. Stubbing `build_agent` would test the stub. `build_agent(config, adapter=...)` is still exercised directly by `test_build_agent_accepts_an_injected_adapter`.
- **`yaml.safe_load`, then `LlmConfig.model_validate`.** A hand-edited config is untrusted input and the full YAML loader constructs arbitrary Python objects from it. Validation stays in the schema (CORE-01) — the CLI parses no fields and knows no defaults, so a schema change cannot leave this file quietly stale.
- **Both a `profiles` subcommand and a chat startup header, sharing one `render_profiles`.** The plan allowed either; the must-have says `paaf chat` surfaces the manifest, and a user who only wants to read the manifest should not have to start a conversation. One renderer, two entry points, no second format.
- **`rich` for decoration, `click.echo` for correctness.** The console is constructed `markup=False, highlight=False, soft_wrap=True`; the byte-exact prompt path does not touch rich at all, so no styling or wrapping decision can ever reach it.
- **A hop with no target prints `(nowhere — end of chain)`.** The engine records an empty `to` when the degraded profile was last (plan 03-06's decision). Rendering it as a blank would read as a missing profile name; naming a real one would lie.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 2's verification named a test file Task 3 creates**
- **Found during:** Task 2
- **Issue:** Task 2's `<automated>` verify is `pytest packages/paaf-llm/tests/test_inspector.py`, but the plan assigns that file's creation to Task 3. As sequenced, Task 2 was unverifiable. (Plan 03-06 hit the identical sequencing shape.)
- **Fix:** Task 2 was verified with an equivalent executable check — a `CliRunner` invocation asserting `result.output == build_agent(cfg, FakeAdapter()).system_prompt()`, plus an `xxd` dump confirming the absence of a trailing newline — and Task 3 then landed the permanent test file containing that assertion and 17 others. No verification was skipped or downgraded to inspection.
- **Files modified:** none (verification method only)
- **Commit:** `1b0d02d`

**2. [Rule 2 - Missing Critical] The plan's "reuse the paaf-core config loading path" is not reachable as written**
- **Found during:** Task 1
- **Issue:** `paaf_core.config.store.load_config` returns an `AppConfig`, and `AppConfig` has no LLM section — `LlmConfig` lives in `paaf_llm.profiles`. Adding it to `AppConfig` would make `paaf_core` import `paaf_llm`, inverting the package dependency and breaking the independence contract.
- **Fix:** The CLI reads the YAML with `yaml.safe_load` (pyyaml is already a declared `paaf-llm` dependency) and validates through `LlmConfig.model_validate`. The *intent* of the instruction — "the CLI does not reinvent parsing", validate-on-read through the typed schema — is preserved exactly: the CLI knows no field names and no defaults. `test_invalid_config_is_a_readable_error` pins that a schema rejection surfaces as a readable message rather than a traceback.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/cli.py`
- **Commit:** `923776a`

**3. [Rule 2 - Missing Critical] rich markup would let config text restyle or hide surrounding output**
- **Found during:** Task 1
- **Issue:** The plan says to render via rich. rich interprets `[...]` as markup by default, and profile `capabilities`/`constraints` are free text (D-08) that reaches the console verbatim. A capability string of `[black on black]` or an unclosed tag could hide or corrupt neighbouring output — a direct "nothing hidden from the user" (PERS-05) failure, from the very surface built to guarantee it.
- **Fix:** `Console(markup=False, highlight=False, soft_wrap=True)`, and the byte-exact prompt path uses `click.echo` so rich cannot touch it at all. Documented at the construction site and in the module docstring.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/cli.py`
- **Commit:** `923776a`

**4. [Rule 2 - Missing Critical] The headline byte-identity test is vacuous while the fragment stub is empty**
- **Found during:** Task 3
- **Issue:** `load_skill_fragments` returns `[]` this phase (D-09), so `test_prompt_byte_exact` would pass unchanged against a CLI that printed the base prompt and silently discarded every skill fragment — the exact PERS-02 regression Phase 6 will make possible.
- **Fix:** Added `test_prompt_byte_exact_with_skill_fragments` (the shared source repointed at real fragments, asserting each fragment's text appears *and* the three-way identity still holds) and `test_prompt_adds_no_text_of_its_own` (expectation rebuilt from raw inputs, independent of the composer). Confirmed non-vacuous by mutation: dropping fragments turns 3 tests red, and only these fragment-bearing ones catch it.
- **Files modified:** `packages/paaf-llm/tests/test_inspector.py`
- **Commit:** `3a5261c`

**5. [Rule 2 - Missing Critical] The plan's test list had no control proving the peer graph is inert**
- **Found during:** Task 3
- **Issue:** `test_manifest_surfaced` asserts capabilities and peers are *printed*. Printing them is not evidence that nothing routes on them — a CLI with a stray handoff would print the same text.
- **Fix:** `test_manifest_performs_no_handoff` declares a peer and leaves it **unprogrammed** in the fake. Contacting it raises `LookupError`, which is deliberately not an `AdapterError` the fallback loop could absorb, so the test cannot pass quietly. It also pins the exact adapter call list (`["local"]`).
- **Files modified:** `packages/paaf-llm/tests/test_inspector.py`
- **Commit:** `3a5261c`

---

**Total deviations:** 5 (1 verification-sequencing, 4 missing-critical). No plan artifact was skipped or substituted.

## Issues Encountered

- **`Agent.turn` returns an aggregated `TurnResult`, so the CLI cannot stream tokens.** The plan's action says "streaming the reply via rich", but the library's public turn API exposes no token iterator — aggregation happens inside `_run_chain`. The CLI prints the completed reply. Adding a streaming turn API would be new library surface, which D-01 puts outside a thin CLI's remit; recorded under Known Stubs for whoever needs token-level output (the voice pipeline will, in a later phase).
- **`ModelProfile` has no `name`** — anticipated from the hand-off notes. `render_profiles` iterates `config.profiles.items()` and carries the key; the fallback notice takes its names from `TurnResult.fallback_trail`, which the engine already populates from the same keys.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-03-17 (Info disclosure — the inspector understating what was sent) | `paaf prompt` and `--show-prompt` print the composer's / the agent's own output; `test_prompt_byte_exact` asserts a three-way identity whose third leg is the `system` message read off `FakeAdapter.calls`. Mutation-verified: a CLI that prints anything other than what was sent fails. |
| T-03-18 (Tampering — the CLI adding hidden text) | The prompt command emits `compose(...)` with `nl=False` and nothing else; `test_prompt_adds_no_text_of_its_own` rebuilds the expectation from raw inputs, independent of the composer. Injecting a `"Be helpful and safe."` preamble was applied as a mutation and turned 4 tests red before being reverted. |
| T-03-19 (Info disclosure — `api_key` surfacing in output) | No command reads `api_key_ref`'s value; `render_profiles` prints provider, model, capabilities, peers, and constraints only, and the composed prompt holds no secret by construction (keys live in the SecretStore by reference). `_default_adapter` — the only code that would ever resolve a key — is never reached by `prompt` or `profiles`, asserted by `test_prompt_calls_no_model`. |

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest --disable-socket` (packages) | 174 passed (baseline 156 + 18 new) |
| `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` | 45 passed (baseline 44; +1 SPDX-header case for `cli.py`) |
| `uv run lint-imports` | 3 contracts kept, 0 broken |
| `uv run ruff check` (this plan's 2 files) | All checks passed |
| `uv run ruff format --check` (this plan's 2 files) | Both formatted |
| `import paaf_llm.cli` framework probe (subprocess) | no `langchain*` / `langgraph*`, no `paaf_llm._engine` in `sys.modules` |
| Mutation: hidden preamble injected into `paaf prompt` | 4 tests RED (reverted; `git diff --stat` clean) |
| Mutation: skill fragments silently dropped | 3 tests RED (reverted; `git diff --stat` clean) |
| Manual smoke: `paaf profiles`, `paaf prompt`, `paaf prompt --provenance`, `paaf chat` | all as specified; `xxd` confirms no trailing newline |
| Suite runtime | `test_inspector.py` in 0.20s, no network |

## Known Stubs

- **`load_skill_fragments` returns `[]`** — the D-09 stub. Real skill discovery is Phase 6 (PERS-02) and plugs into this exact `(name, text)` signature. This is intentional and scoped by the plan; the fragment-bearing tests pin the contract *now* by repointing the source, so Phase 6 has an executable spec rather than a paragraph.
- **`_default_adapter` raises a `ClickException` until plan 03-08 lands `build_engine_adapter`** — by design. Every command that does not call a model (`prompt`, `profiles`) works today; `chat` reports exactly what is missing and how to install it. This is the SC#1 shape, not a gap.
- **`chat` prints the completed reply rather than streaming tokens** — `Agent.turn` aggregates and exposes no token iterator (see Issues Encountered). A future streaming API belongs to the library, not to a thin CLI.
- **No `--trace-db` option.** `build_agent` accepts a `trace=` sink and passes it to the agent, but no command wires one yet — trace wiring is plan 03-09's. The seam exists so 03-09 adds an option, not a parameter.

## User Setup Required

None — no external service configuration required. `paaf prompt` and `paaf profiles` work against any valid config with no model installed.

## Next Phase Readiness

- **Plan 03-08 (real adapter)** must expose `build_engine_adapter(config) -> ChatAdapter` from `paaf_llm._engine`. `cli._default_adapter` already imports exactly that name, lazily and inside a function; landing it turns `paaf chat` live with no CLI change. Keep the import lazy — `test_engine_import_is_lazy_in_the_source` and the subprocess probe both fail if it moves to module scope.
- **Plan 03-09 (trace wiring)** should add a `--trace-db`-style option to `chat` and pass the store through `build_agent(..., trace=...)`; the parameter is already threaded to `Agent.build`.
- **Phase 4 (mesh)** — `NO_HANDOFF_NOTE` and `test_manifest_performs_no_handoff` are the two places that assert inertness. Both must be updated deliberately when MESH-02 makes the peer graph live, which is the point: turning the graph on cannot happen by accident.
- **Phase 4 (PERS-05 across phases, D-10)** — the generated handoff explainer must appear verbatim in `paaf prompt`. `test_prompt_adds_no_text_of_its_own` is the enforcement point: an explainer composed outside `PromptComposer` will fail it.
- **Phase 6 (skills)** — replace the body of `cli.load_skill_fragments`. Both the agent and the inspector read it, so nothing else needs to change for PERS-02 to hold end to end.
- **For the orchestrator:** `STATE.md`, `ROADMAP.md`, and `REQUIREMENTS.md` were left untouched per worktree protocol. This plan completes **MODEL-05, PERS-01, PERS-02, PERS-04, PERS-05** (recorded in `requirements-completed`).

## Self-Check: PASSED

| Claim | Result |
|-------|--------|
| `packages/paaf-llm/src/paaf_llm/cli.py` | FOUND |
| `packages/paaf-llm/tests/test_inspector.py` | FOUND |
| Commit `923776a` | FOUND |
| Commit `1b0d02d` | FOUND |
| Commit `3a5261c` | FOUND |

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
