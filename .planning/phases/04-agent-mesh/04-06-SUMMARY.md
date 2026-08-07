---
phase: 04-agent-mesh
plan: 06
subsystem: llm-engine
status: complete
tags: [mesh, fallback, trace, turn-id, per-leg, handoff-attempts, d-11, sc4]
requirements: [MESH-05]

requires:
  - "paaf_llm.agent.Agent.turn's leg loop and its engine-generated turn_id (04-01)"
  - "paaf_trace.store.TurnLegEvent / HandoffEvent and the FK-free turn_legs / handoffs tables (04-02)"
  - "paaf_llm.mesh.tools_for_leg and the hop wall / home agent (04-03)"
  - "paaf_llm.agent.Agent.system_prompt(agent_name) per-leg composition (04-05)"
provides:
  - "paaf_llm.profiles.ModelProfile.fallback_chain (WARM) + _check_refs rule 4"
  - "paaf_llm.profiles.LlmConfig.keep_pre_handoff_prose (WARM, default True)"
  - "paaf_llm.agent.Agent._chain(agent_name) — the chain resolved per awake agent"
  - "paaf_llm.agent.Agent._reachable_agents() and a mesh-aware warmup()"
  - "paaf_llm.agent.Agent._drain(..., turn_id, leg_seq, agent_name) emitting RunEvent + TurnLegEvent per LEG"
  - "paaf_llm.agent.Agent._emit_handoff(...) — one handoffs row per ATTEMPT"
  - "paaf_llm.agent.HANDOFF_ACCEPTED / HANDOFF_UNDECLARED_PEER / HANDOFF_BUDGET_EXHAUSTED / PRE_HANDOFF_JOINER"
  - "packages/paaf-llm/tests/test_mesh_trace.py (7 tests, force-included)"
  - "tests/conftest.py::make_mesh_config(keep_pre_handoff_prose=...)"
affects:
  - "04-07 (the observer fills observer_verdict / observer_profile / rerouted_to on the rows this plan writes)"
  - "04-08 (the CLI / signals surface reads the same outcomes)"
  - "04-09 (marks MESH-05 complete; carries the last emit site)"

tech-stack:
  added: []
  patterns:
    - "One concept at two scopes (global default + per-agent override), never a fourth concept"
    - "Correlation by engine-generated uuid4 turn_id; new tables, never a new column (Pitfall 5)"
    - "Record the ATTEMPT, not only the outcome — a refusal runs no leg and leaves no runs row"
    - "Falsify every trace assertion by reverting the mechanism it claims to measure"

key-files:
  created:
    - packages/paaf-llm/tests/test_mesh_trace.py
  modified:
    - packages/paaf-llm/src/paaf_llm/profiles.py
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/tests/test_fallback.py
    - packages/paaf-llm/tests/test_profiles.py
    - packages/paaf-llm/tests/test_mesh.py
    - packages/paaf-llm/tests/conftest.py
    - packages/paaf-llm/pyproject.toml
    - .planning/phases/04-agent-mesh/deferred-items.md

decisions:
  - "ModelProfile.fallback_chain is an OVERRIDE of the global chain, not a replacement of the concept — an empty list means 'use the global one', so every Phase-3 config is byte-identical in behavior"
  - "The self-reference check lives on LlmConfig._check_refs, not on ModelProfile: a profile carries no name field, so a bare model cannot know it is referencing itself (deviation from the plan's <behavior> bullet)"
  - "warmup() walks the peer graph transitively AND includes default_agent — the home agent is nobody's peer by design (T-04-12) yet answers the final leg at the wall"
  - "turn() no longer records a turn-level started_at: every timestamp belongs to a LEG, and a turn's span is derived by the reader from its turn_legs rows"
  - "One attempt_seq counter spans accepted, refused and budget_exhausted rows — they are all attempts within one turn, so a single ordinal is the honest ordering"
  - "Pre-handoff prose is recorded on the accepted handoffs row's `detail`, because neither runs nor turn_legs has ever carried completion text (deviation: the plan said 'the leg's runs row')"
  - "The two budget tests now assert the COMPOSED reply rather than being opted out of D-11 — their runaway mesh speaks on every leg, so the shipped default is what they should measure"
  - "MESH-05 deliberately left Pending: 04-09 also carries it and is unexecuted (the 04-02 precedent)"

metrics:
  duration: ~65 min
  tasks: 3
  commits: 3
  files_changed: 9
  lines: +1234 / -56
  tests_added: 15
  suite: 268 passed (paaf-llm) / 355 passed (workspace) / 217 passed (clean venv, framework uninstalled)
  completed: 2026-08-07
---

# Phase 4 Plan 06: Per-Agent Resilience And The Handoff Chain On Disk Summary

A turn that bounced through three agents now leaves three rows saying who was awake on each leg and which model actually served it, plus one row per handoff attempt **including the ones that were refused** — and each leg carries its own fallback trail, so an agent that was quietly rescued by its backup is attributable to that agent rather than to the turn.

## What Was Built

**Resilience became per-agent, and it is nested inside handoff rather than beside it.** `fallback_chain` was a single global field, so SC#4's "each agent applies its own" was not implementable. `ModelProfile.fallback_chain` is now an override of the global one — empty means "use the global", which is why every Phase-3 config behaves identically and why no Phase-3 test moved. `Agent._chain(agent_name)` resolves the order for whoever is serving the current leg, so a peer that degrades on the leg it was handed falls back down *its* chain. `_run_chain` is unchanged and is called once per leg: the plan's own key link is that a second resilience mechanism for the mesh would be the anti-pattern, and none was added.

The proof's negative control is structural rather than asserted. In `test_per_agent_chain_serves_the_receiving_agents_own_fallback` the host's backup and the global backup are left **unprogrammed**, so an engine that reached for either raises `LookupError` — pointedly not an `AdapterError`, so the fallback loop cannot swallow the mistake as one more plausible hop and report a cheerful trail.

**`warmup()` now covers the whole graph, not the active chain.** This was not in the plan's letter and is the same Pitfall-2 bug the two-clock design exists to prevent: a peer that is cold when it is handed a leg spends its 3-10s load *inside* that leg's first-token deadline and false-triggers the fallback the user configured for a broken provider — and only on handoffs, which is the hardest version of that bug to reproduce. `_reachable_agents()` walks the peer graph breadth-first from the awake agent and adds `default_agent`, which a peer-only walk would miss precisely because declaring a home agent grants no handoff edge (T-04-12) while the home agent is the one that answers at the wall.

**One `runs` row per LEG, and the correlation deliberately does not live on `runs`.** `_drain` now emits a `RunEvent` — unchanged in shape, which is what keeps the Phase-3 trace contract and the TTFA path intact — *and* a `TurnLegEvent` carrying `turn_id`, `leg_seq`, the awake agent, that leg's own `served_by`, and that leg's own `fallback_trail`. Correlation is by an engine-generated `uuid4` hex, and `assert_engine_generated` asserts 32 hex characters rather than trusting it: `turn_id = 1, 2, 3` looks perfectly plausible in a single-turn test, and the fire-and-forget writer never surfaces a `lastrowid` for anyone to use. A `turn_id` column on `runs` would have been a silent no-op on every `trace.db` that already exists (Pitfall 5, reproduced out-of-band by 04-02).

**`_emit_handoff` records attempts, and the refused ones are the reason it exists.** A rejected handoff runs no leg, so it produces no `runs` row and no `turn_legs` row — meaning a turn on which the model reached for an agent it was never allowed to reach is, without an attempt record, *indistinguishable in the trace* from a turn on which it never tried. That is exactly the case MESH-05 was written for, and it would fail silently while every other row looked healthy (T-04-26). The row is written **before** `UndeclaredPeer` is re-raised, which is the only ordering that survives the exception. The wall writes one too, because a turn that quietly stopped hopping looks exactly like one that never wanted to.

**D-11 closed as a setting, with the v2 item preserved rather than absorbed.** Prose a leg emitted before handing off is kept by default and prefixed to the final answer, because PAAF does not silently edit what a model said. Empty legs are filtered before joining — plan 04-04 measured both gate models emitting the handoff call with *zero* prose, so a silent handoff is the normal turn, and an unconditional join would have put a leading blank line on every handed-off reply on the headline command. Mechanical enforcement that an agent must be silent before handing off is stated in the field comment, the module docstring and a test as a deliberate v2 item, so its absence cannot read as an oversight.

## Key Decisions

| Decision | Why |
|----------|-----|
| Per-agent chain is an OVERRIDE, empty means global | A merge would make the user's declared order not the order they declared. A replacement would break every Phase-3 config, none of which declares one. |
| The self-reference check lives on `LlmConfig` | A profile has no `name` field — its name is its dict key. `model` is the *provider's* model id (`qwen3.5:9b`), so checking against it would invent a rule the user never wrote. Identical reason the self-PEER check has always lived there. |
| `warmup()` walks the graph and includes `default_agent` | The home agent is nobody's peer by construction and still speaks the final leg. A peer-only walk misses exactly the agent that answers at the worst possible moment. |
| No turn-level `started_at` | Every row this turn writes describes a leg. A turn's span is `min(started_at)..max(ended_at)` over its `turn_legs` rows — derived by the reader, not denormalized by the writer. |
| One `attempt_seq` across all three outcomes | Accepted, refused and walled are all *attempts within one turn*. Separate counters would make "the third thing that happened" unanswerable from the table. |
| Pre-handoff prose lands on `handoffs.detail` | See deviation 1 — the trace has never had a completion-text column, and the attempt row is where the prose belongs anyway: it is the handoff that discarded it. |
| The budget tests assert the composed reply | Opting them out of D-11 would hide that the shipped default composes. Their runaway mesh speaks on every leg, so the composed text is what those turns actually produce. |
| MESH-05 stays `Pending` | 04-09 also carries it and is unexecuted. This plan is *an* emit site, not the last one — the 04-02 precedent. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan located dropped prose in the leg's `runs` row; no such column exists**

- **Found during:** Task 3
- **Issue:** Task 3's `<behavior>` and its acceptance criterion both require the dropped text to be "still readable in that leg's `runs` row", and T-04-31's mitigation rests on "the text remains in the local trace". **Neither `runs` nor `turn_legs` has a completion-text column.** `RunEvent` carries `prompts` — what was *sent* — and the trace has never recorded what came back, for any turn, since Phase 2. Adding one is forbidden twice over: phase invariant 1 bars a new column on `runs`, and adding one to `turn_legs` would hit the identical Pitfall-5 no-op on any database where 04-02's schema has already run. Written as specified, the plan would either have been unimplementable or would have made a false claim: dropping would have been a genuine loss, i.e. a hidden edit rather than a presentation choice.
- **Fix:** the accepted `handoffs` row records the pre-handoff prose verbatim in its `detail` column — a column that already exists, is already free text ("the rejection message, or the constraint cited"), and belongs to precisely the event that discarded the prose. This satisfies the plan's own `must_haves` truth ("recoverable from the trace either way") and makes T-04-31's mitigation true rather than aspirational. The prose is recorded regardless of the setting, so turning it off changes what is *shown* and nothing else. `test_pre_handoff_prose_dropped_is_still_recoverable_from_the_trace` asserts against the row, and its docstring states why the assertion is not against `runs`.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`, `packages/paaf-llm/tests/test_mesh.py`
- **Commit:** `138f3af` (the `detail=reply` emit), `0b4f332` (the setting and the test)

**2. [Rule 1 - Bug] `ModelProfile(provider="ollama", model="m", fallback_chain=["m"])` cannot raise, and must not**

- **Found during:** Task 1
- **Issue:** Task 1's first `<behavior>` bullet requires the bare constructor to reject a self-reference. It cannot: a `ModelProfile` carries no `name` field, so it does not know what it is called. The only field a model-level validator could compare against is `model`, which is the *provider's* model identifier — a profile named `kitchen-local` running `qwen3.5:9b` would then have `fallback_chain: ["qwen3.5:9b"]` flagged as a self-reference when it is really a dangling one, inventing a rule the user never wrote. The plan's own `<action>` puts both checks in `_check_refs`, so the bullet also contradicts the action.
- **Fix:** implemented in `_check_refs` rule 4 per the `<action>`, following the self-PEER precedent that has lived there since Phase 3 for the identical reason. `test_profile_fallback_chain_rejects_a_self_reference` asserts the `LlmConfig` rejection *and* documents why the bare model accepts it, with `assert "name" not in ModelProfile.model_fields` as the standing reason. Without that second half the test would have been a vacuous green: before the field existed it passed on `extra="forbid"` alone.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/profiles.py`, `packages/paaf-llm/tests/test_profiles.py`
- **Commit:** `2dc300d`

**3. [Rule 3 - Blocking] `test_fallback_chain_and_peers_are_separate_fields` asserted the field could not exist**

- **Found during:** Task 1
- **Issue:** the Phase-3 test asserted `"fallback_chain" not in ModelProfile.model_fields` — a direct statement that this plan's central field is forbidden. Left alone it is a red suite; deleted it is a lost guarantee, since it is the row that keeps resilience and handoff from collapsing into each other.
- **Fix:** rewrote it to assert what is actually true and load-bearing — `fallback_chain` on *both* models (one concept, two scopes) and `peers` on `ModelProfile` only (handoff is a per-agent graph; there is no global one) — and added `test_a_per_agent_fallback_entry_grants_no_handoff_edge` so T-04-30's separation is asserted directly rather than inferred from there being two fields.
- **Files modified:** `packages/paaf-llm/tests/test_profiles.py`
- **Commit:** `2dc300d`

**4. [Rule 2 - Missing critical functionality] `warmup()` left every peer cold**

- **Found during:** Task 1
- **Issue:** the plan's action says to widen `warmup()`, and the reason is a correctness one rather than an optimization: with `warmup()` preloading only the awake agent's chain, a peer pays its 3-10s cold load inside the first-token deadline on the leg it is handed and false-triggers the user's fallback. The plan's phrasing ("each declared peer's chain") reads as one hop, which would still leave a three-agent chain's third agent cold.
- **Fix:** `_reachable_agents()` walks the peer graph transitively, breadth-first in the user's declared order, and appends `default_agent`. `test_warmup_preloads_each_reachable_agents_own_chain` asserts the exact preload order and that the *global* backup — which nobody declared — is never loaded, so the test also proves warmup reads the per-agent chains.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`, `packages/paaf-llm/tests/test_fallback.py`
- **Commit:** `2dc300d`

**5. [Rule 3 - Blocking] `make_mesh_config` could not express D-11's setting**

- **Found during:** Task 3
- **Issue:** the drop-case test needs `keep_pre_handoff_prose=False` in a mesh config, and the shared fixture had no way to say it. `model_copy(update=...)` would have bypassed validation.
- **Fix:** added a passthrough parameter to `conftest.py::make_mesh_config`, exactly as `hop_budget` and `default_agent` are passed through, so the schema's own default stays the single source of truth.
- **Files modified:** `packages/paaf-llm/tests/conftest.py`
- **Commit:** `0b4f332`

### Falsification (per the wave-4 brief)

Every claim this plan makes about the trace was broken on purpose before being reported green. The brief named one; all five were run.

| Mechanism removed | Command | Result |
|---|---|---|
| `_chain` reverted to the global chain | `pytest test_fallback.py -k "per_agent or warmup"` | **2 failed** — the per-agent test dies on `LookupError` reaching `global_backup`, warmup on the order |
| `_drain` hoisted out of the leg loop (one row per turn) | `pytest test_mesh_trace.py -k legs` | **2 failed** — including `test_legs_carry_their_own_per_agent_fallback_trail`, exactly the row the brief demanded go red |
| The refusal-path `_emit_handoff` deleted | `pytest test_mesh_trace.py -k attempts` | **1 failed** — `len(handoffs) == 0` |
| `detail=reply` → `detail=None` (a genuinely lossy drop) | `pytest test_mesh.py -k prose` | **1 failed** — the drop test is not an absence check |
| `keep_pre_handoff_prose` ignored (always drop) | `pytest test_mesh.py -k prose` | **1 failed** — the default is measured, not assumed |

### Non-Vacuity Checks (per the wave-1 finding)

Every `-k` filter was confirmed to select a nonzero, intended set with `--collect-only -q` **before** being run.

| Command | Selected | Result |
|---|---|---|
| `test_fallback.py -k per_agent` | 1 of 21 | passed |
| `test_mesh_trace.py -k legs` | 4 of 7 | passed |
| `test_mesh_trace.py -k attempts` | 4 of 7 | passed |
| `test_mesh.py -k prose` | 3 of 31 (2 new + the 04-05 explainer row) | passed |
| `test_mesh.py -k history_clean` | 1 of 31 | passed |
| `test_inspector.py -k trace` | 5 of 60 | passed |

### Out of Scope — Logged, Not Fixed

**`uv run ruff check packages` is red at baseline on `paaf-core` (RUF022).** `packages/paaf-core/src/paaf_core/secrets/__init__.py` has an unsorted `__all__`, in a file no plan in this phase touches. Same root cause as the existing deferred item: `ruff` is unpinned and no CI job runs the check tree-wide. `uv run ruff check packages/paaf-llm packages/paaf-trace` passes. Recorded as deferred item 3 with a suggested fix. The pre-existing `ruff format` drift in `cli.py` and `_engine/__init__.py` remains under deferred item 1; every file this plan touches is format-clean individually.

## Known Stubs

Each is a plan-assigned deferral, and none blocks this plan's goal.

| Stub | File | Resolved by |
|------|------|-------------|
| `observer_verdict`, `observer_profile`, `rerouted_to` are written as NULL on every attempt row | `agent.py::_emit_handoff` | 04-07 (the observer, D-05/D-07) |
| `handoffs.outcome` values `observer_retry` / `observer_reroute` are declared in the schema with no writer | `schema.sql` | 04-07 |
| No mechanical enforcement that an agent emits no prose before calling handoff | `agent.py`, `mesh.py` | v2, deliberately — flagged by the founder as really important and preserved in D-11's Deferred Ideas, not absorbed by `keep_pre_handoff_prose` |
| A SQL error inside `TraceStore._writer` still kills the writer and deadlocks `stop()` | `paaf_trace/store.py` | unassigned — deferred item 2 from 04-02, unchanged by this plan |

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-26 Repudiation (rejected attempts invisible) | mitigated | `_emit_handoff` writes the attempt row **before** re-raising `UndeclaredPeer`; `test_attempts_record_a_rejected_target_with_null_observer_columns` asserts the row, its `detail`, its NULL observer columns and that no leg row exists for the target. Falsified: deleting the emit turns it red. |
| T-04-27 Repudiation (per-leg provenance) | mitigated | One `runs` + one `turn_legs` row per leg; `test_legs_carry_their_own_per_agent_fallback_trail` asserts two legs hold **different** trails, which a per-turn design cannot satisfy. Falsified: hoisting `_drain` out of the loop turns it red. |
| T-04-28 DoS (silent no-op schema application) | mitigated | Zero change under `packages/paaf-trace` (0 lines); no `ALTER TABLE` anywhere; correlation lives in `turn_legs`. 04-02's reopen test is the standing proof and is green. |
| T-04-29 Tampering (`HandoffEvent` / `TurnLegEvent` writes) | mitigated | The engine builds no SQL. Both events use the parameterized `as_sql()` balance-tested in 04-02; model-authored `to_agent` and `detail` cross only as bound parameters. |
| T-04-30 Elevation of Privilege (`fallback_chain` becoming a handoff edge) | mitigated | The two fields stay separate; `handoff_tools`/`resolve_handoff` read `peers` only and were not touched; `test_a_per_agent_fallback_entry_grants_no_handoff_edge` asserts a chain entry does not join the peer graph. |
| T-04-31 Info disclosure (dropped prose) | accepted, and now genuinely so | The default keeps; the user opts into dropping; and the text remains in the local trace on the accepted `handoffs` row — which is what makes the acceptance honest rather than an assertion. See deviation 1. |
| T-04-SC Dependency surface | accepted | Zero packages installed. `packages/paaf-llm/pyproject.toml` changed by exactly one line: a `force-include` test-file entry. |

**Threat flags:** none. No new network endpoint, auth path, file access pattern, or schema change was introduced — the two tables this plan writes to were declared by 04-02 and are unchanged.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest packages/paaf-llm -q` | 268 passed (257 before this plan) |
| `uv run pytest -q` (workspace) | 355 passed (338 at baseline) |
| `uv run pytest packages/paaf-trace/tests/test_trace_no_egress.py packages/paaf-trace/tests/test_ttfa_regression.py -q` | 7 passed — TRACE-05 and the TTFA gate unaffected |
| `uv run pytest packages/paaf-llm/tests/test_agent_turn.py -q` | passed — a config with no per-agent chain behaves exactly as in Phase 3 |
| `bash scripts/check_framework_uninstalled.sh` | **PASS** — 217 tests green in the clean venv; non-vacuity guard reports **all 13** test files shipped, including `tests/test_mesh.py` and `tests/test_mesh_trace.py` |
| `uv run lint-imports` | 3 contracts kept, 0 broken — **`.importlinter` unchanged**, no new carve-out |
| `uv run ruff check packages/paaf-llm packages/paaf-trace` | All checks passed |
| `uv run ruff format --check` (all 7 files this plan touches) | 7 files already formatted |
| `python -c "... ModelProfile.model_fields['fallback_chain'].json_schema_extra"` | exit 0 |
| `python -c "... c.keep_pre_handoff_prose is True"` | exit 0 |
| `python -c "... 'tests/test_mesh.py' in fi and 'tests/test_mesh_trace.py' in fi"` | exit 0 |

**Phase invariants re-checked at commit time:**

1. **No `ALTER TABLE`, no new column on `runs`** — `packages/paaf-trace` untouched (0 lines). Correlation lives in `turn_legs`.
2. **OQ-5 honoured** — one `runs` row per agent leg, correlated by the engine-generated `turn_id`, asserted to be 32 hex characters so a `lastrowid` cannot masquerade as one. `handoffs` records REJECTED attempts.
3. **Force-include** — `tests/test_mesh_trace.py` added; the gate's guard reports 13/13 shipped.
4. **`compose()` byte-exact** — `compose.py` untouched (0 lines); `test_no_hidden_prompt` passes under its own name.
5. **`paaf prompt` default output** — `cli.py` untouched (0 lines).
6. **No handoff tool call in `Agent.history`; `Role` not widened** — `test_history_clean_of_tool_calls` passes, and D-11's two new tests each assert `len(agent.history) == 2`.
7. **`langchain*` confined to `paaf_llm._engine`** — `lint-imports` green, `.importlinter` unchanged.

**04-VALIDATION.md rows green, each selected by its documented `-k` command and confirmed non-vacuous:** `legs`, `attempts`, and SC#4's `per_agent`.

## Requirements

**MESH-05 deliberately left `Pending`**, following 04-02's precedent. This plan is *an* emit site — `turn_legs` and `handoffs` now receive rows — but **04-09 also carries MESH-05 and is unexecuted**, and the observer columns 04-07 owns are still NULL on every attempt row. Marking it Complete here would let an audit read "the trace records every handoff, its verdict and any correction" as satisfied while the verdict and correction half does not exist. 04-09, the last plan carrying it, is the correct place. `roadmap update-plan-progress` was run; `requirements mark-complete` was deliberately not.

## Self-Check: PASSED

- `packages/paaf-llm/tests/test_mesh_trace.py` — FOUND
- `packages/paaf-llm/src/paaf_llm/agent.py` — FOUND
- `packages/paaf-llm/src/paaf_llm/profiles.py` — FOUND
- `.planning/phases/04-agent-mesh/deferred-items.md` — FOUND
- Commit `2dc300d` — FOUND in `git log`
- Commit `138f3af` — FOUND in `git log`
- Commit `0b4f332` — FOUND in `git log`
