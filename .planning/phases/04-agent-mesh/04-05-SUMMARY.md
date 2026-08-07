---
phase: 04-agent-mesh
plan: 05
subsystem: llm-engine
status: complete
tags: [mesh, prompt, explainer, per-agent, inspector, provenance, pers-05, mesh-04, d-17, d-18, d-19, oq-3]
requirements: [MESH-04]

requires:
  - "paaf_llm.compose.PromptComposer.segments/compose and SEGMENT_SEPARATOR (Phase 3) — widened, not replaced"
  - "paaf_llm.mesh.handoff_tools() / tools_for_leg() / _describe() (04-01, 04-03)"
  - "paaf_llm.agent.Agent.turn's per-leg message construction and the turn-local `awake` (04-01, 04-03)"
  - "paaf_llm.cli PROVENANCE_LABEL / _config_failure / load_skill_fragments (Phase 3)"
  - "paaf_llm.profiles field pattern (json_schema_extra reload_tier) and extra='forbid' (Phase 3)"
provides:
  - "paaf_llm.compose.PromptComposer.segments(base, fragments, mesh_fragments=())"
  - "paaf_llm.compose.PromptComposer.compose(base, fragments, mesh_fragments=())"
  - "paaf_llm.profiles.ModelProfile.system_prompt / .persona / .handoff_explainer (all WARM)"
  - "paaf_llm.profiles.LlmConfig.handoff_explainer_template (WARM)"
  - "paaf_llm.mesh.MESH_PERSONA_SOURCE / MESH_EXPLAINER_SOURCE / MESH_TOOL_SOURCE_PREFIX"
  - "paaf_llm.mesh.DEFAULT_EXPLAINER_TEMPLATE / EXPLAINER_PEERS_PLACEHOLDER / EXPLAINER_PEER_LINE"
  - "paaf_llm.mesh.explainer_for() / base_prompt_for() / mesh_fragments_for()"
  - "paaf_llm.agent.Agent.system_prompt(agent_name=None)"
  - "paaf_llm.cli.UNKNOWN_AGENT / _render_tool_surface() / `paaf prompt --agent <name>`"
  - "tests/conftest.py::make_mesh_config(system_prompts=, personas=, explainers=, explainer_template=)"
  - "tests/test_inspector.py::mesh_config() / surface_for()"
affects:
  - "04-06 (per-agent fallback_chain composes against the per-agent prompt this plan resolved; the per-leg `runs` row records the per-leg system prompt)"
  - "04-07 (the observer is a ModelProfile, so `paaf prompt --agent observer` already reads its prompt; the observer's own grant tools should render through _render_tool_surface)"
  - "04-08 (a retry fragment is a fourth mesh source and plugs into mesh_fragments_for with no composer change)"
  - "Phase 6 (real skill discovery replaces load_skill_fragments and lands between base and mesh, unchanged)"

tech-stack:
  added: []
  patterns:
    - "A third ORDERED input rather than a reshape: compose() was always a pure function taking the base as an argument, so per-agent composition needed a place to put text, not a new philosophy"
    - "One branchless join expression, asserted BOTH by the split-and-compare test and by a source check for one `return` and no `if`"
    - "The layer's source labels are owned by the module that owns the layer; the composer passes them through and never compares against them"
    - "str.replace, never str.format, for any template a user may have written — prose contains braces"
    - "A rendered surface derived from the ONE function the engine asks (tools_for_leg), so the inspector cannot show what the engine would not offer"
    - "Falsification-by-substitution on every new guard, including one that exposed a genuinely weak assertion"

key-files:
  created: []
  modified:
    - packages/paaf-llm/src/paaf_llm/compose.py
    - packages/paaf-llm/src/paaf_llm/profiles.py
    - packages/paaf-llm/src/paaf_llm/mesh.py
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/src/paaf_llm/cli.py
    - packages/paaf-llm/tests/conftest.py
    - packages/paaf-llm/tests/test_compose.py
    - packages/paaf-llm/tests/test_mesh.py
    - packages/paaf-llm/tests/test_inspector.py

key-decisions:
  - "The explainer names PEERS, never tool names — which is what makes OQ-3's boundary mechanically assertable in both directions"
  - "explainer_for and handoff_tools quote a peer's manifest through the SAME _describe(), so the prompt and the tool description cannot disagree about the same agent"
  - "A user template is substituted with str.replace, not str.format: a stray brace in the user's own prose would otherwise crash the one path that must always show what was sent"
  - "The tool surface renders with click.echo, not _make_console() as the plan specified — echo interprets nothing at all, which is strictly stronger than markup=False for a byte-exactness command"
  - "base_prompt_for tests `is not None`, not truthiness: `system_prompt: \"\"` is a declaration, not an absence"
  - "The per-agent explainer override is checked BEFORE the peer list, so a user's explicit text is never suppressed for looking unused"
  - "system_prompt(agent_name) raises KeyError by design; the CLI validates first and reports through _config_failure (T-04-23)"

patterns-established:
  - "Widening an invariant test in place, under its own name, rather than adding a sibling — a rename would make a later deletion look like a refactor"
  - "Falsification that finds a WEAK assertion rather than confirming a strong one, and strengthens the test data instead of the code"

requirements-completed: [MESH-04]

coverage:
  - id: D1
    description: "The explainer is generated from THIS agent's capability manifest and peer graph and appears verbatim in the prompt inspector"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_mesh.py#test_explainer_names_each_peer_and_quotes_its_manifest_verbatim"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_provenance_shows_the_generated_explainer_verbatim"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two agents can have genuinely different prompts through the one composer (D-17)"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_compose.py#test_per_agent_prompts_differ_through_one_composer"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_mesh.py#test_each_leg_carries_the_receiving_agents_own_prompt"
        status: pass
    human_judgment: false
  - id: D3
    description: "compose() still equals the joined segment texts — the byte-exact invariant widened, not replaced"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_compose.py#test_no_hidden_prompt"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_compose.py#test_compose_is_byte_exact_the_joined_segments"
        status: pass
      - kind: other
        ref: "uv run python -c \"...inspect.getsource(PromptComposer.compose)... one return, no 'if '\""
        status: pass
    human_judgment: false
  - id: D4
    description: "EVERY offered tool name and description appears in --provenance (PERS-05 made mechanical, Finding 1)"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_provenance_tool_surface_visible"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_default_output_is_byte_exact_and_carries_no_tool_surface"
        status: pass
    human_judgment: false
  - id: D5
    description: "paaf prompt --agent <name> targets a non-awake peer and the reserved observer, and refuses an unknown name readably"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_agent_flag_reads_a_peer_that_is_not_awake"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_agent_flag_reads_the_reserved_observer"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_inspector.py#test_agent_flag_rejects_an_unknown_name_readably"
        status: pass
    human_judgment: false
  - id: D6
    description: "The generated explainer encodes no routing rule, in English or otherwise (T-04-22 / MESH-01)"
    requirement: MESH-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_mesh.py#test_default_explainer_states_no_routing_rule"
        status: pass
    human_judgment: false

metrics:
  duration: ~55 min
  tasks: 3
  commits: 6
  files_changed: 9
  lines: +1252 / -57
  tests_added: 19
  suite: 251 passed (paaf-llm) / 338 passed (workspace) / 203 passed (clean venv, SC#1)
  completed: 2026-08-07
---

# Phase 4 Plan 05: Every Steering Byte Is Readable Summary

Two agents now genuinely have different prompts — each with its own system prompt, its own persona, and a handoff explainer generated from its own manifest and peer graph — and `paaf prompt` shows all of it for any declared agent, including the handoff tools' names and descriptions, which were steering the model from outside the prompt entirely.

## Performance

- **Duration:** ~55 min of active execution (across a session reset mid-Task-2)
- **Tasks:** 3, each executed TDD (RED → GREEN)
- **Files modified:** 9, none created
- **Tests added:** 19 (232 → 251 in the paaf-llm lane)

## Task Commits

1. **Task 1 (RED): widen the byte-exact invariant to the mesh layer** — `4d9517c` (test)
2. **Task 1 (GREEN): a third ordered input, per-profile prompt layers** — `e161409` (feat)
3. **Task 2 (GREEN): generate each agent's explainer from its own manifest and peers** — `cd1eef7` (feat)
4. **Task 3 (RED): the inspector must show every steering byte** — `e425e6c` (test)
5. **Task 3 (GREEN): tool surface under `--provenance`, and `--agent`** — `a8d4df0` (feat)
6. **Falsification follow-up: make the byte-exact invariant bite** — `1bd1654` (test)

Task 2's RED was written in the pre-reset session and landed in the same commit as its GREEN after the reset re-verified the 11 failing tests on disk; the failure list is recorded under Verification.

## What Was Built

**The composer gained an input, not a philosophy.** `compose(base_prompt, fragments)` was always a pure function taking the base as an *argument* — it never read `LlmConfig` — so per-agent composition was already expressible and only needed somewhere to put an agent's persona and explainer. `segments` and `compose` now take a third ordered `mesh_fragments`, and `compose` is still exactly one branchless join expression. That shape is load-bearing twice over: the widened split-and-compare test in `test_compose.py` demands the output equal `[base, *fragments, *mesh]`, and a source check demands the method contain one `return` and no `if`. A branch skipping an empty mesh layer is the obvious, harmless-looking change that would let the composed bytes and the labelled segments drift, and the `--provenance` view could then understate what crossed to the model.

**The mesh layer's labels are owned by the mesh, and the composer never compares against them.** `mesh_fragments` carry a full `source` rather than a name to be prefixed, so `mesh:persona`, `mesh:explainer` and any later source cost `compose.py` nothing. The composer stays ignorant of what a mesh is, which is the property that let it absorb Phase 4 at all.

**The explainer and the tool description are the same bytes, by construction.** `explainer_for` renders each peer through the identical `_describe()` that `handoff_tools` uses for the tool description. Two derivations would let the sentence the model reads in its prompt and the description attached to the tool it calls disagree about the same agent — and the disagreement would surface as routing that looks arbitrary. The peer with no manifest gets the same neutral one-liner in both places, and the test asserts the tool's own description string appears inside the explainer rather than re-deriving it.

**A user template is prose, so it is substituted with `str.replace`.** `str.format` would turn a stray `{oven}` in someone's own explainer into a `KeyError` — a crash in the one code path that must always be able to show the user what was sent. A template that omits `{peers}` simply gets no peer list, which is a legitimate thing to ask for rather than an error to repair.

**The generated explainer states no condition, and that is the whole of MESH-01's exposure here.** It is the one piece of steering text PAAF *writes*, so it is the one place a routing rule could arrive with no config key to reject it. It names peers, quotes their manifests, and says the choice belongs to the model. `test_default_explainer_states_no_routing_rule` scans the rendered text for the shapes a rule takes in English (`" if "`, `whenever`, `must hand`, `always hand`, `score`, `keyword`, `matches`) — a smoke check on the template PAAF ships, explicitly not a claim about anything the user writes, because the user's assistant is theirs to steer.

**D-11 is discouraged in prose and deliberately not enforced.** The last paragraph tells the agent to hand over rather than announce that it is about to, because the hand-over is silent and a "let me get someone else for that" reaches the user attached to nothing. Phase 4 ships no mechanism that strips such prose; the constant's docstring says so out loud and points at the v2 item the founder marked as really important, so the paragraph's existence cannot be mistaken for the enforcement. It also records 04-04's live finding — `qwen3.5:2b` and `qwen3.5:9b` both emit the handoff tool call with **zero** accompanying prose — so today this paragraph reinforces what the gate models already do, and every path around a handoff had to be correct with empty prose, which is the common case rather than the edge case.

**The prompt follows the handoff.** `Agent.system_prompt` takes an optional agent name, defaulting to the awake agent so no Phase-3 caller changed meaning, and `turn` composes each leg's system message for the agent serving *that* leg. Composing it once outside the loop is the natural wrong implementation and would quietly make every per-agent prompt the caller's; falsification F2 confirms three tests catch it.

**The inspector stopped showing only part of what steers the model.** A tool's name and its description are sent to the model and shape its choice, and they are not in the system prompt — so `paaf prompt` was injecting behaviour-steering text the user could not read the moment the mesh bound `transfer_to_chef` carrying chef's manifest. `--provenance` now renders the bound surface after the prompt segments, read from `mesh.tools_for_leg` — the one function that decides a leg's moves — with `hops_used=0`, the only honest answer outside a turn and the *most* the model is ever offered, since the wall only withdraws it.

**OQ-3's boundary is mechanical in both directions.** The default output is untouched: no prefix, no suffix, `nl=False`, verified with `xxd`. The mesh prompt *layer* is present there because persona and explainer really are inside the system message; the tool *surface* is absent because it never was. The control asserts `transfer_to_` and `mesh:tool:` appear nowhere in the default output — which is only assertable because the explainer names peers rather than tool names, a design choice made for exactly this reason.

## Key Decisions

| Decision | Why |
|----------|-----|
| The explainer names peers, never tool names | Duplicating generated identifiers into prose invites drift between the prose and the surface — and it is what makes OQ-3's boundary assertable, since `transfer_to_` can then be demanded absent from default output. |
| One `_describe()` for both the explainer and the tool description | Two renderings of a peer's manifest agree until the day one is edited. The test asserts the *tool's own description string* is inside the explainer, so a second derivation fails immediately. |
| `str.replace`, never `str.format`, for templates | A user's explainer is prose and prose contains braces. A `KeyError` here is a crash in the exact path whose job is to show the user what was sent. |
| The per-agent override is checked before the peer list | An agent with an explicit explainer and no peers still shows the user's own text. PAAF does not suppress a declaration for looking unused. |
| `base_prompt_for` tests `is not None` | `system_prompt: ""` is a user asking for no base prompt. Substituting the global one would be PAAF overruling an explicit declaration with a default — the mistake `endpoint_unauthenticated` exists to avoid on the credential side. |
| The surface is read from `tools_for_leg`, not `handoff_tools` | `tools_for_leg` is the single place deciding a leg's moves (04-03). Reading anything else would let the inspector show a surface the engine would not offer. |
| `click.echo` for the tool text, not `_make_console()` | See Deviations. `echo` interprets nothing whatsoever; a rich console with `markup=False` still performs its own substitutions. For a command whose entire contract is byte-exactness, "interprets nothing" beats "interprets less". |
| `system_prompt(name)` raises `KeyError` | The engine's callers already hold validated names. Making the library tolerant would move validation away from the CLI, which is where the untrusted string actually enters (T-04-23). |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_hand_back_to_prior_agent_does_not_restart` asserted the thing D-17 forbids**

- **Found during:** Task 2
- **Issue:** the 04-03 test asserted all three legs of an A→B→A turn were handed the *identical* message tuple, system message included. Once each leg carries the receiving agent's own prompt, that assertion demands `a` and `b` share a prompt — precisely what D-17 exists to make impossible. It is not a stale test: its intent ("does not restart") is about the transcript.
- **Fix:** the comparison was split. `messages[1:]` (the transcript) is still asserted identical across all three legs — the original guarantee, undiluted — and `messages[0]` is asserted to be `[a's prompt, b's prompt, a's prompt]`, which is a *stronger* statement than the old one because it now also proves the prompt followed the handoff. No assertion was removed or weakened.
- **Files modified:** `packages/paaf-llm/tests/test_mesh.py`
- **Commit:** `cd1eef7`

**2. [Rule 3 - Blocking] `make_mesh_config` could not express the per-agent prompt layer**

- **Found during:** Task 2
- **Issue:** `tests/conftest.py` is not in the plan's file list, but the fixture takes no per-agent prompt, persona, or explainer, so no D-17/D-18 test could be written against it. Same class of gap 04-03 recorded for `hop_budget` / `default_agent`.
- **Fix:** `system_prompts`, `personas`, `explainers` (all name-keyed mappings, exactly as `capabilities` is) and `explainer_template` added as pass-throughs. Crucially they use `.get(name)` and **not** `.get(name, "")`, with a comment saying why: an absent declaration must stay `None`, because only `None` falls back to the shared base.
- **Files modified:** `packages/paaf-llm/tests/conftest.py`
- **Commit:** `cd1eef7`

**3. [Rule 1 - Bug] `system_message_actually_sent` hard-coded the profile it programmed**

- **Found during:** Task 3
- **Issue:** the `test_inspector.py` helper always programmed the fake for `"local"`, which was fine when every config in the file activated `local`. As of MESH-04 the composed prompt depends on *which* agent is asked, so a mesh config activating `host` blew up with `LookupError` — and, worse, a helper that always drove one profile would silently compare against a different agent's prompt.
- **Fix:** it now programs `config.profiles[config.active_profile].model`, read off the config it was handed.
- **Files modified:** `packages/paaf-llm/tests/test_inspector.py`
- **Commit:** `a8d4df0`

**4. [Rule 1 - Bug] The plan's `_make_console()` instruction is wrong for this output**

- **Found during:** Task 3
- **Issue:** the plan says to route new rendering of user-authored text through `_make_console()` (`markup=False, highlight=False`) for the T-04-24 markup reason. But `_make_console` returns a `rich.Console`, which — markup disabled or not — still applies its own transformations, notably emoji-code substitution (`:fire:`). A capability manifest containing one would be rewritten on its way to the terminal, and `paaf prompt`'s entire contract is that what is printed is what was sent. The existing provenance path already uses `click.echo` for exactly this reason.
- **Fix:** the tool surface renders with `click.echo`, matching the segment path directly above it, with a docstring paragraph recording that this is *stronger* than `_make_console()` for T-04-24 rather than a relaxation of it: `echo` interprets nothing at all, so no markup, highlight, or substitution can reach the output.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/cli.py`
- **Commit:** `a8d4df0`

**5. [Rule 2 - Missing critical functionality] The byte-exact assertion did not bite on a normalized mesh layer**

- **Found during:** falsification, after Task 3
- **Issue:** substituting a `compose` that appended mesh fragments with `.strip()` — a plausible "tidy-up" refactor, and a *rewrite* of the user's text — left the whole suite green. Every mesh fixture happened to be already-tidy, so the normalization was invisible. This is the plan's own stated failure mode arriving through the back door: the invariant existed, but the data could not falsify it.
- **Fix:** a fragment with leading and trailing whitespace (`"  Speak quietly.\tNever shout. "`, deliberately containing no `SEP`) added to the byte-exact matrix, with a comment stating that tidying is a rewrite and `Segment.text`'s as-sent rule forbids it. Re-falsified: the substitution now turns exactly `test_compose_is_byte_exact_the_joined_segments` red.
- **Files modified:** `packages/paaf-llm/tests/test_compose.py`
- **Commit:** `1bd1654`

---

**Total deviations:** 5 auto-fixed (3 bugs, 1 blocking, 1 missing critical). None changed the plan's scope. Deviation 4 is the only one that contradicts an explicit plan instruction, and it does so in the direction of the guarantee the instruction was protecting.

### Out of Scope — Logged, Not Fixed

**Pre-existing `ruff format` drift, unchanged.** `profiles.py`, `cli.py` and `test_inspector.py` each contain lines that would be reformatted *at the commit this plan started from* — verified per file by formatting `git show HEAD:<path>` in a scratch directory rather than by touching the working tree. `mesh.py`, `agent.py`, `test_mesh.py`, `conftest.py` and `compose.py` were format-clean at baseline and are format-clean now. Every line this plan added is format-clean; the three drifting files were fixed by hand on the plan's own lines only, so no unrelated reformatting rode along. This is deferred item 1, already recorded by 04-01/04-02/04-03/04-04 (`ruff` unpinned in the dev group, no CI job runs the check).

## Known Stubs

None introduced by this plan.

**Resolved from earlier stub lists:** 04-04 recorded *"the per-agent prompt assembly (04-05)"* as open — closed here.

Still open elsewhere, unchanged: the per-leg `runs` rows and `handoffs` writes (04-06), the per-agent `fallback_chain` (04-06), the three unemitted `MeshSignalKind` members (04-07/04-08), and the observer's graceful loop-break before the wall (04-07).

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-20 Repudiation/Tampering (hidden steering text in tool names and descriptions) | mitigated | `_render_tool_surface` prints every `ToolSpec` from `mesh.tools_for_leg`. `test_provenance_tool_surface_visible` **iterates the surface** rather than naming tools, and asserts the surface is non-empty first, so a later tool added without an inspector change turns it red and a vacuous loop cannot pass. Falsified (F1). |
| T-04-21 Tampering (`compose` second derivation) | mitigated | `compose` is one branchless join, asserted by the widened split-and-compare, by the matrix test including every empty combination, and by a source check for one `return` and no `if `. Falsified (F3) — and the first falsification attempt **failed to bite**, which is how deviation 5 was found. |
| T-04-22 EoP (`DEFAULT_EXPLAINER_TEMPLATE` smuggling a routing DSL in English) | mitigated | The template names peers and quotes manifests; it states no condition. `test_default_explainer_states_no_routing_rule` scans the rendered output for seven rule-shaped tokens. |
| T-04-23 Tampering (`--agent` used as an unvalidated dict key) | mitigated | Validated against `config.profiles` and reported through `_config_failure` with the name and the declared alternatives; never used to index directly. `test_agent_flag_rejects_an_unknown_name_readably` asserts non-zero exit, no traceback, and both halves of the message. |
| T-04-24 Tampering (manifest markup on the terminal) | mitigated, more strongly than specified | `click.echo` interprets nothing — no markup, no highlight, no rich substitution. See deviation 4. |
| T-04-25 Information Disclosure (default output) | accepted | Unchanged and pipe-safe; the tool surface is opt-in. The deliberate OQ-3 trade, now asserted in both directions. |
| T-04-SC Dependency surface | accepted | Zero packages installed; `pyproject.toml` unchanged (0 lines). |

**Threat flags:** none. No new network endpoint, auth path, file access, or schema change. The one widened surface — tool names and descriptions now *displayed* — moves bytes toward the user, not away from the box.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest packages/paaf-llm -q` | **251 passed** (232 before this plan) |
| `uv run pytest -q` (workspace) | **338 passed** (319 before) |
| `bash scripts/check_framework_uninstalled.sh` | **PASS** — 203 tests green in a clean venv; the non-vacuity guard reports all 12 shipped test files, `test_engine_adapter.py` still the one deliberate exclusion |
| `uv run lint-imports` | **3 contracts kept, 0 broken**; `.importlinter` unchanged (0 lines), no new carve-out |
| `git diff --stat -- packages/paaf-llm/pyproject.toml .importlinter` | **0** — no new test file was created, so no `force-include` change was needed |
| `uv run ruff check packages/paaf-llm` | All checks passed |
| `uv run ruff format --check` (lines this plan touched) | Clean; the three drifting files drift identically at `f67a297` |
| `inspect.getsource(PromptComposer.compose)` → one `return`, no `if ` | exit 0 |
| `compose('b',[('s','f')]) == SEP.join(['b','f'])` | exit 0 — the two-argument call is byte-identical to Phase 3 |
| Reload tiers on all four new fields | exit 0 |
| `mesh.explainer_for('h', <no peers>, {}) == ''` | exit 0 |
| `paaf prompt --config … \| xxd` | ends `2e` (`.`) — **no trailing newline** (D-19 unchanged) |
| `paaf prompt --agent chef` | prints chef's prompt, no trailing newline |
| `paaf prompt --agent nope` | one-line config failure naming `'nope'` and `['chef', 'host']`, exit 1, no traceback |

### RED phases recorded

| Task | RED command | Failures |
|------|-------------|----------|
| 1 | `pytest test_compose.py` | 5 failed, 2 passed — `TypeError: segments() takes 3 positional arguments but 4 were given` |
| 2 | `pytest packages/paaf-llm` | 11 failed, 234 passed — the 10 new mesh tests plus the widened hand-back test |
| 3 | `pytest test_inspector.py` | 6 failed, 32 passed — `Error: No such option '--agent'` and the missing tool surface |

### Non-Vacuity Checks (per the wave-1 finding)

Every prescribed `-k` filter was confirmed by `--collect-only -q` to select a nonzero number of tests **before** being reported.

| Command | Selected | Result |
|---------|----------|--------|
| `test_compose.py -k byte_exact` | **1** of 7 | passed |
| `test_compose.py -k per_agent` | **1** of 7 | passed |
| `test_compose.py -k no_hidden_prompt` | **1** of 7 | passed — the Phase-3 invariant test is present under its own name |
| `test_mesh.py -k explainer` | **5** of 28 | passed |
| `test_mesh.py -k per_agent` | **1** of 28 | passed |
| `test_mesh.py -k source_imports_no_agent_framework` | **1** of 28 | passed — `mesh.py` is still stdlib-only |
| `test_inspector.py -k explainer` | **1** of 38 | passed |
| `test_inspector.py -k tool_surface_visible` | **1** of 38 | passed |
| `test_inspector.py -k agent_flag` | **3** of 38 | passed — non-awake peer, `observer`, unknown name |
| `test_inspector.py -k byte_exact` | **3** of 38 | passed |
| `test_inspector.py -k provenance_is_not_the_default` | **1** of 38 | passed |

No prescribed filter selected zero tests.

### Falsification — each guard was proved to bite

Six inversions applied out of band, each run against the full `paaf-llm` lane and reverted immediately.

| # | Inversion | Result |
|---|-----------|--------|
| F1 | Delete the `_render_tool_surface(...)` call | 1 failed — `test_provenance_tool_surface_visible` |
| F2 | Compose the leg's prompt from the awake *attribute* (`system_prompt()`) instead of this leg's agent | 3 failed — `test_each_leg_carries_the_receiving_agents_own_prompt`, `test_carries_history_to_receiving_agent`, `test_hand_back_to_prior_agent_does_not_restart` |
| F3 | Append mesh fragments in `compose` with `.strip()` (a second derivation that "tidies") | **PASSED at first** — see deviation 5. After strengthening the matrix: 1 failed — `test_compose_is_byte_exact_the_joined_segments` |
| F4 | Ignore `ModelProfile.handoff_explainer` | 1 failed — `test_explainer_override_precedence_per_agent_beats_global_beats_default` |
| F5 | Collapse `base_prompt_for` to the global base | 5 failed, including `test_base_prompt_for_falls_back_to_the_shared_base` and `test_each_leg_carries_the_receiving_agents_own_prompt` |
| F6 | Accept `--agent` and then ignore it | 3 failed — both `agent_flag` reader tests plus the explainer test's no-peer branch |

Tree restored and re-verified after each: **251 passed**, `git status --short packages/` empty.

**F3 is the one worth reading.** It is the only falsification in this phase so far that *failed to produce a red test*, and it did so against the plan's own headline invariant. The assertion was correct; the data could not falsify it. That is the failure mode a green suite hides best, and it is why the fix went into the test rather than the code.

### Phase invariants re-checked at commit time

1. **No `ALTER TABLE`, no new `runs` column** — `grep -rn "ALTER TABLE" packages/*/src` returns nothing; `packages/paaf-trace` untouched (0 lines).
2. **`force-include`** — no new test file created, so nothing to add; `packages/paaf-llm/pyproject.toml` unchanged (0 lines). The clean-venv guard reports all 12 shipped test files, so the widened `test_compose.py` and `test_inspector.py` assertions run in the SC#5 lane.
3. **`compose()` byte-exact** — widened, never replaced. `test_no_hidden_prompt` keeps its name and now splits to `[base, *fragments, *mesh]`; the source check for one `return` and no `if ` passes; the two-argument call is byte-identical to Phase 3.
4. **`paaf prompt` default output** — verified with `xxd`: no prefix, no trailing newline. Per OQ-3 the tool surface appears under `--provenance` only, asserted absent from the default output by name and by label.
5. **No handoff tool call in `Agent.history`; `Role` not widened** — `Role = Literal["system", "user", "assistant"]`, three members, `ports.py` untouched (0 lines). `test_history_clean_of_tool_calls` green.
6. **`langchain*` confined to `paaf_llm._engine`** — `lint-imports` green, `.importlinter` unchanged, no new carve-out. `mesh.py`'s own source guard still passes.
7. **PERS-05 made mechanical** — the rendered surface is derived from `mesh.tools_for_leg`, and the test iterates that same function's return value rather than a hard-coded list, so the inspector and the engine cannot drift apart.

**04-VALIDATION.md rows green:** `explainer`, `per_agent` (compose), `byte_exact`, `tool_surface_visible`, `agent_flag`.

**ROADMAP SC#3 satisfied:** the explainer is generated from the user's capability manifest and peer graph, appears verbatim in the prompt inspector, and nothing steers the model that the user cannot read — including the tool surface, which is what made this plan larger than its title.

## Issues Encountered

The session reset mid-Task-2, with `test_mesh.py`'s RED suite uncommitted. Rather than assume what had been written, the plan and the dirty file were re-read and the 11 failures re-confirmed on disk before any implementation began — which is why Task 2's RED and GREEN share a commit.

The only substantive surprise was F3, described above: the phase's headline invariant was, briefly, unfalsifiable.

## User Setup Required

None. No external service, no new dependency, no configuration. Existing configs are unaffected: all four new fields default to `None`, and a config with no peers composes byte-identically to Phase 3.

## Next Phase Readiness

- **04-06** composes against the per-agent prompt this plan resolved; the per-leg `runs` row should record `system_prompt(awake)` for that leg, which `turn` already holds in `system`.
- **04-07** gets `paaf prompt --agent observer` for free — the observer is an ordinary `ModelProfile` — and should render the observer's own grant tools through `_render_tool_surface`, since the argument in Finding 1 applies identically to a grant.
- **04-08** can add a retry fragment as a fourth mesh source with no change to `compose.py` at all; that is the property the third-input design was chosen for.
- **D-11's mechanical enforcement** is still a v2 item and is now documented at the point of discouragement, in `DEFAULT_EXPLAINER_TEMPLATE`'s docstring, together with the live measurement showing today's gate models emit no pre-handoff prose at all.

## Self-Check: PASSED

- `packages/paaf-llm/src/paaf_llm/compose.py` — FOUND (`mesh_fragments` on `segments` and `compose`)
- `packages/paaf-llm/src/paaf_llm/profiles.py` — FOUND (`system_prompt`, `persona`, `handoff_explainer`, `handoff_explainer_template`)
- `packages/paaf-llm/src/paaf_llm/mesh.py` — FOUND (`DEFAULT_EXPLAINER_TEMPLATE`, `explainer_for`, `base_prompt_for`, `mesh_fragments_for`, the three source constants)
- `packages/paaf-llm/src/paaf_llm/agent.py` — FOUND (`system_prompt(agent_name=None)`)
- `packages/paaf-llm/src/paaf_llm/cli.py` — FOUND (`UNKNOWN_AGENT`, `_render_tool_surface`, `--agent`)
- `packages/paaf-llm/tests/test_compose.py` — FOUND (7 tests, `test_no_hidden_prompt` intact)
- `packages/paaf-llm/tests/test_inspector.py` — FOUND (38 tests)
- Commit `4d9517c` — FOUND in `git log`
- Commit `e161409` — FOUND in `git log`
- Commit `cd1eef7` — FOUND in `git log`
- Commit `e425e6c` — FOUND in `git log`
- Commit `a8d4df0` — FOUND in `git log`
- Commit `1bd1654` — FOUND in `git log`

---
*Phase: 04-agent-mesh*
*Completed: 2026-08-07*
