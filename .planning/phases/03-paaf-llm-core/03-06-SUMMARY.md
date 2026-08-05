---
phase: 03-paaf-llm-core
plan: 06
subsystem: api
tags: [engine, fallback, asyncio, streaming, timeout, trace, tdd, framework-free]

# Dependency graph
requires:
  - phase: 03-paaf-llm-core
    provides: "plan 03-05's ChatAdapter port, the four AdapterError subclasses, AllProvidersFailed, TurnResult, and the shipped FakeAdapter + conftest fixtures"
  - phase: 03-paaf-llm-core
    provides: "plan 03-01's LlmConfig/ModelProfile (active_profile + fallback_chain drive the loop; first_token_budget_s is the deadline)"
  - phase: 03-paaf-llm-core
    provides: "plan 03-04's PromptComposer (the one system-prompt derivation, called verbatim)"
  - phase: 03-paaf-llm-core
    provides: "plan 03-02's served_by + fallback_trail columns on the runs table"
provides:
  - "Agent.build/turn/warmup — the pure-PAAF turn loop: composed prompt, ephemeral history, ordered fallback, first-token deadline"
  - "Agent.system_prompt() — the single derivation the CLI's prompt inspector calls (D-02, no re-derivation)"
  - "A first-token deadline that classifies SLOW_FIRST_TOKEN itself, which no framework built-in can express"
  - "Per-turn trace draining: one RunEvent carrying served_by, the JSON fallback trail, and post-aggregation token counts"
  - "TraceSink / SecretResolver — narrow local Protocols so the engine is not typed against a whole store"
  - "packages/paaf-llm/tests/test_fallback.py — 5 triggers, 2 negative controls, 2 coverage controls"
  - "packages/paaf-llm/tests/test_agent_turn.py — the walking skeleton + two source assertions"
affects: [03-07-cli, 03-08-engine-adapter, 03-09-trace-wiring, 04-agent-mesh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.timeout around ONLY the first __anext__ — a per-profile time-to-first-token deadline, never a stopwatch on the whole stream"
    - "The chain carries (name, profile) pairs because the name lives in the config dict key and does not cross the port"
    - "Narrow consumer-side Protocols (TraceSink, SecretResolver) instead of importing a collaborator's concrete type into a signature"
    - "Coverage controls: a test asserting the parametrization spans the WHOLE enum / every exception subclass, so a new trigger cannot ship untested"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/tests/test_agent_turn.py
    - packages/paaf-llm/tests/test_fallback.py
  modified: []

key-decisions:
  - "The chain is iterated as (name, profile) pairs: ModelProfile has no .name, so served_by and every trail hop are reported from the config key the loop already holds"
  - "A hop's `to` is the empty string when the degraded profile was LAST in the chain — inventing a target would misreport where the conversation went"
  - "An empty fallback trail is written as \"[]\", never NULL: 'the active profile served it' is a recorded fact, not an absence"
  - "A failed turn is NOT appended to history — the next turn must not ship a user message the model never replied to"
  - "StopAsyncIteration on the first token is a SERVED turn with an empty reply, not a degraded provider: falling back would hide a real answer"
  - "The chain restarts from the user's active profile every turn — fallback is not sticky, so a recovered provider is used again immediately"
  - "aclose() is called through getattr: the port promises an AsyncIterator, which does not guarantee an aclose()"
  - "Agent is deliberately NOT re-exported from paaf_llm.__init__ — its build() signature names paaf_trace, and the no-leak walker's allowed roots are stdlib/paaf_llm/paaf_core only"

patterns-established:
  - "Source assertions pin structural invariants a fake cannot express (the deadline's scope, the absence of a framework import)"
  - "A negative control per behavioral claim: healthy-does-not-hop AND slow-later-token-does-not-abort"

requirements-completed: [MODEL-03, MODEL-04]

coverage:
  - id: D1
    description: "A multi-turn conversation: a streamed reply enters in-memory history and the next turn sees it"
    requirement: MODEL-03
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_it_talks"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_multi_turn_history"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unreachable provider mid-conversation moves the reply onto the next profile and the conversation continues"
    requirement: MODEL-03
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_fallback_connection"
        status: pass
    human_judgment: false
  - id: D3
    description: "All four degraded-but-reachable triggers (timeout, 5xx, 429, slow first token) fire the same ordered chain"
    requirement: MODEL-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_fallback_degraded"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_every_fallback_reason_has_a_trigger_in_this_file"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_adapter_error_subclasses_are_all_exercised"
        status: pass
    human_judgment: false
  - id: D4
    description: "NEGATIVE CONTROL — a healthy provider does not fall back, and a slow LATER token does not abort a committed stream (D-04 scope = first token only)"
    requirement: MODEL-04
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_healthy_no_fallback"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_fallback.py#test_no_mid_stream_fallback"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_first_token_deadline_wraps_only_the_first_anext"
        status: pass
    human_judgment: false
  - id: D5
    description: "Each fallback reason and the served-by profile land in the trace; usage is read once after aggregation"
    requirement: MODEL-04
    verification:
      - kind: integration
        ref: "packages/paaf-llm/tests/test_fallback.py#test_fallback_traced"
        status: pass
      - kind: integration
        ref: "packages/paaf-llm/tests/test_fallback.py#test_trace_records_the_served_profile_and_the_prompt"
        status: pass
      - kind: integration
        ref: "packages/paaf-llm/tests/test_fallback.py#test_usage_aggregated_reaches_the_trace"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_usage_aggregated"
        status: pass
    human_judgment: false
  - id: D6
    description: "The engine is framework-free and sends the composer's output verbatim"
    requirement: MODEL-08
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_agent_source_imports_no_agent_framework"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_agent_turn.py#test_the_system_message_is_the_composers_output_verbatim"
        status: pass
      - kind: integration
        ref: "uv run lint-imports (3 contracts kept, 0 broken)"
        status: pass
    human_judgment: false

# Metrics
duration: 25min
completed: 2026-08-05
status: complete
---

# Phase 3 Plan 06: Agent Turn Loop + Ordered Fallback Summary

**The assistant now holds a conversation and survives losing the model that was holding it: a pure-PAAF turn loop composes the prompt once, streams a reply, keeps it in memory, and walks the user's ordered chain — on an unreachable provider, a timeout, a 5xx, a 429, or a first token that never arrives — recording every hop's reason and who finally answered.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 (task 1 TDD → 4 commits)
- **Files created:** 3 (1 source, 2 test)
- **Tests added:** 26 (8 turn + 18 fallback/trace)

## Accomplishments

- **The walking skeleton talks.** `Agent.turn("hi")` composes the system prompt through plan 03-04's composer (byte-identical, asserted — so plan 03-07's inspector cannot drift from what was sent), streams the reply, and appends the exchange to in-memory history. Turn 2 demonstrably ships turn 1 across the port: `test_multi_turn_history` reads the actual message list the adapter received.
- **The one hand-rolled thing is hand-rolled, and it earns it.** The fallback loop is stdlib + PAAF only. It runs with the agent framework uninstalled (SC#1), and it expresses the trigger no framework built-in can: `asyncio.timeout(profile.first_token_budget_s)` wraps ONLY the first `__anext__`, so a provider that answers `200` and then stalls is classified `slow_first_token` and the chain advances. A framework fallback fires only when *creating* the stream raises, which this failure never does.
- **All five triggers fire, and two controls prove the loop is not just always falling back.** `test_healthy_no_fallback` asserts the healthy active profile serves *and that the fallback profile is never contacted*. `test_no_mid_stream_fallback` uses a purpose-built local adapter that is fast to the first token and then pauses for five budgets — an engine that wrapped the whole stream in the deadline would abort that healthy reply and would look correct in every other test in the file, because the shipped fake cannot be slow after its first token.
- **The trace answers "why not the model I picked?".** One `RunEvent` per turn carries the composed prompt, `served_by`, and the `{from,to,reason}` trail as JSON; the tests read the rows back out of the real SQLite file rather than asserting against an in-memory list. Token counts are read once via `last_usage()` after the stream aggregates (SPIKE-05) and are non-`None` end to end.
- **Coverage is guarded against its own future.** Two controls assert the parametrization spans the whole `FallbackReason` enum and every `AdapterError` subclass — a sixth reason added later cannot ship untested while this file still looks exhaustive.

## Task Commits

1. **Task 1 (RED): failing turn/history/deadline tests** — `5a0e2b7` (test)
2. **Task 1 (GREEN): `agent.py` — the loop, the deadline, warmup** — `4716280` (feat)
3. **Task 2: trace draining (served_by + reasons + aggregated usage)** — `9ebe24b` (feat)
4. **Task 3: the four triggers, the negative controls, history across a hop** — `431de21` (test)

## Files Created

- `packages/paaf-llm/src/paaf_llm/agent.py` (created) — `Agent.build/turn/warmup/system_prompt`, `_run_chain` (the ordered loop + first-token deadline), `_drain` (the single `RunEvent`), plus the `TraceSink` and `SecretResolver` Protocols. Imports `asyncio`, `json`, `time`, `paaf_trace.store.RunEvent`, and three sibling PAAF modules — no agent framework.
- `packages/paaf-llm/tests/test_agent_turn.py` (created) — 8 tests: it-talks, multi-turn history, composed-prompt-verbatim, aggregated usage, `AllProvidersFailed` (with the history-untouched invariant), warmup-visits-the-chain, and the two source assertions.
- `packages/paaf-llm/tests/test_fallback.py` (created) — 18 tests: `test_fallback_connection`, `test_fallback_degraded` (×5), `test_fallback_traced` (×5), the served-by/prompt trace row, the aggregated-usage trace row, tracing-is-optional, `test_healthy_no_fallback`, `test_no_mid_stream_fallback`, and the two coverage controls.

## Decisions Made

- **The chain is `[(name, profile), ...]`, not `[profile, ...]`.** `ModelProfile` has no `name` field (plan 03-01 keyed profiles by the `LlmConfig.profiles` dict key), so RESEARCH Pattern 2's `self._served_by = profile.name` would `AttributeError`. The loop resolves each chain entry to its profile and carries the name it already had. Flagged by plan 03-05's executor; verified against `profiles.py` before writing a line.
- **A hop's `to` is `""` when the degraded profile was last.** The trail is provenance, and "there was nowhere to go" is the truth in that case. Naming a nonexistent target would misreport where the conversation went.
- **An empty trail serializes to `"[]"`, not `NULL`.** "The active profile served it" is a fact worth recording; a `NULL` reads as "nothing was written", which is a different claim.
- **A failed turn leaves history untouched.** Asserted explicitly (`test_all_providers_failed_...`). Appending the user message anyway would make the next turn ship a question the model never answered, and the model would see a conversation that never happened.
- **An empty stream is a served turn, not a degraded provider.** `StopAsyncIteration` on the first token returns an empty reply from that profile. Falling back there would hide a real (if useless) answer and would misattribute `served_by`.
- **Fallback is not sticky.** Every turn restarts at the user's `active_profile`, so a provider that comes back is used again on the very next turn. Asserted in `test_fallback_connection` by the exact call order `["local", "cloud", "local", "cloud"]` — a design fact, now pinned.
- **`Agent` is NOT re-exported from `paaf_llm.__init__`.** Its `build()` signature names a trace sink; the no-leak walker in `test_no_leak.py` allows only stdlib / `paaf_llm` / `paaf_core` roots across `__all__`. Callers import `from paaf_llm.agent import Agent`. Plan 03-07's CLI should do the same.
- **`TraceSink` and `SecretResolver` are local Protocols.** The engine drains into `paaf-trace` but should not be *typed against* the whole store; a four-line object satisfies the sink. `SecretResolver` is held and unused this phase — key resolution belongs to the real adapter (plan 03-08), and typing the parameter says so better than a bare `None` default.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Task 2 could not be verified without its tests existing**
- **Found during:** Task 2
- **Issue:** Task 2's verify command is `pytest packages/paaf-llm/tests/test_fallback.py -k "traced or usage"`, but the plan assigns the creation of `test_fallback.py` to Task 3. Task 2 was unverifiable as sequenced.
- **Fix:** Task 2 created `test_fallback.py` containing only its own trace/usage coverage (`test_fallback_traced` ×5, the served-by row, the aggregated-usage row, tracing-is-optional, and the two coverage controls); Task 3 appended the trigger and negative-control tests to the same file. Both commits are independently green.
- **Files modified:** `packages/paaf-llm/tests/test_fallback.py`
- **Commits:** `9ebe24b` (task 2 half), `431de21` (task 3 half)

**2. [Rule 2 - Missing Critical] `aclose()` is not guaranteed by the port's return type**
- **Found during:** Task 1
- **Issue:** The plan says to `await gen.aclose()` on the deadline path, but `ChatAdapter.stream` is declared to return an `AsyncIterator[str]`, which has no `aclose`. A class-based adapter implementing the port literally would raise `AttributeError` on the timeout path — i.e. exactly when a provider is already misbehaving.
- **Fix:** `aclose = getattr(gen, "aclose", None)` then `await aclose()` when present. The source assertion in `test_first_token_deadline_wraps_only_the_first_anext` still matches the literal `aclose()`.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `4716280`

**3. [Rule 2 - Missing Critical] An empty stream had no defined outcome**
- **Found during:** Task 1
- **Issue:** The plan's loop handles a timeout and an `AdapterError`, but not `StopAsyncIteration` — a provider that succeeds and yields nothing. Unhandled, it would escape `turn()` as a bare `StopAsyncIteration`, which inside an async frame is a confusing runtime error rather than an answer.
- **Fix:** Treated as a served turn with an empty reply (documented inline with its rationale).
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `4716280`

**4. [Rule 2 - Missing Critical] `test_no_mid_stream_fallback` — a control the plan did not ask for**
- **Found during:** Task 3
- **Issue:** The plan's controls prove fallback *fires* and that a healthy provider does not hop. Neither can catch the most likely wrong implementation of the deadline: wrapping the whole stream instead of the first `__anext__`. The shipped fake models only a slow FIRST token, so no programmable fake test can distinguish the two.
- **Fix:** Added a purpose-built local adapter (`_SlowLaterTokensAdapter`) that yields immediately and then pauses for five budgets, plus a source assertion pinning the deadline's scope. No socket is involved — the pause is an `asyncio.sleep`.
- **Files modified:** `packages/paaf-llm/tests/test_fallback.py`, `packages/paaf-llm/tests/test_agent_turn.py`
- **Commits:** `5a0e2b7`, `431de21`

---

**Total deviations:** 4 auto-fixed (1 sequencing, 3 missing-critical). No plan artifact was skipped or substituted.

## Issues Encountered

- **`profile.name` does not exist** — anticipated by plan 03-05's hand-off note and confirmed by reading `profiles.py` first. The loop carries names from the chain it is iterating; nothing was changed in the schema or the port, so parallel siblings are unaffected.
- **Reading trace rows back requires stopping the writer.** `TraceStore.stop()` flushes the queue and is idempotent, so a test can call it and the `trace_store` fixture's own teardown still succeeds. The helper asserts `store.dropped == 0` first — a read that silently proves nothing is worse than no read.

## Threat Mitigations Applied

| Threat | Applied |
|--------|---------|
| T-03-14 (DoS — a degraded provider stalling the turn indefinitely) | `asyncio.timeout(profile.first_token_budget_s)` bounds the first-token wait; on expiry the hop is recorded as `slow_first_token`, the abandoned generator is closed, and the chain advances. Proven by the `slow_first_token` parametrization of `test_fallback_degraded` / `test_fallback_traced`, and scoped correctly by `test_no_mid_stream_fallback`. |
| T-03-15 (Repudiation — a silent wrong-reroute) | Every turn emits one `RunEvent` with `served_by` and the full `{from,to,reason}` trail, read back from the real DB in `test_fallback_traced`. `test_healthy_no_fallback` + `test_trace_records_the_served_profile_and_the_prompt` prove the record is non-vacuous: a healthy turn writes `served_by = local` and `[]`, not a missing row. |
| T-03-16 (Info disclosure — secrets through trace/usage) | Accepted per plan. `turn()` drains the composed prompt (which by construction holds no secret — keys live in the SecretStore) and token counts. No `api_key` value is read anywhere in `agent.py`; `secret_store` is stored and never dereferenced this phase. |

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest --disable-socket` (packages) | 156 passed (baseline 130 + 26 new) |
| `uv run pytest tests/test_governance.py tests/negcontrol/test_import_boundary.py --disable-socket` | 44 passed (baseline 43; +1 SPDX-header case for `agent.py`) |
| `uv run lint-imports` | 3 contracts kept, 0 broken |
| `uv run ruff check` (this plan's 3 files) | All checks passed |
| `uv run ruff format --check` (this plan's 3 files) | All formatted |
| `python -c "import paaf_llm.agent"` framework probe | no `langchain*`/`langgraph*` in `sys.modules` |
| Suite runtime | `test_fallback.py` + `test_agent_turn.py` in 0.20s, no network |

## TDD Gate Compliance

| Task | RED (`test`) | GREEN (`feat`) | REFACTOR |
|------|--------------|----------------|----------|
| 1 | `5a0e2b7` — confirmed failing (`ImportError: cannot import name 'agent' from 'paaf_llm'`) | `4716280` | not needed |
| 2 | n/a (`type="auto"`) — its tests were written first anyway and confirmed failing (`IndexError: list index out of range`, no run row) | `9ebe24b` | — |
| 3 | n/a (`type="auto"`, test-only task) | `431de21` | — |

No test passed unexpectedly during a RED phase.

## Known Stubs

- **`warmup()` is a no-op against any adapter without a `preload` method** — including the shipped fake. This is the plan's stated two-clock design: the real preload path (an empty-prompt load / `keep_alive=-1` for Ollama) is wired by plan 03-08's adapter. `test_warmup_visits_every_profile_in_the_chain` pins the contract *now* using a subclassed fake, so 03-08 has an executable spec rather than a paragraph.
- **`secret_store` is held and never used** — key resolution belongs to the real adapter (plan 03-08, CORE-04). Declared with a typed Protocol so its meaning is explicit.
- **`TurnResult.handoff` is always `None`** — inherited from plan 03-05's Phase-4 seam; `turn()` sets it explicitly with a comment so a future MESH-02 change is deliberate.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 03-07 (CLI)** should call `Agent.system_prompt()` for `paaf prompt` / `--show-prompt` rather than re-deriving anything (D-02), and can render the `↳ fell back to <profile> (<reason>)` notice straight from `TurnResult.fallback_trail`. Import as `from paaf_llm.agent import Agent` — `Agent` is intentionally not on `paaf_llm.__all__`.
- **Plan 03-08 (real adapter)** must (a) translate its framework's exceptions into the four `AdapterError` subclasses — the loop reads `.reason` and has no other classification path — and (b) add an `async def preload(self, profile)` so `warmup()` stops being a no-op and the first-token budget measures a warm model.
- **Plan 03-09 (trace wiring)** — one `RunEvent` per turn is already emitted from `Agent._drain`, with `served_by`, the JSON trail, and post-aggregation token counts. If 03-09 adds its own emission it must not double-write; extend `_drain` instead.
- **Phase 4 (mesh)** — `TurnResult.handoff` is set explicitly to `None` at one site in `turn()`, and the loop already resolves an "awake profile" per turn as a local variable. That is the seam MESH-02 populates.
- **For the orchestrator:** `STATE.md`, `ROADMAP.md`, and `REQUIREMENTS.md` were left untouched per worktree protocol. This plan completes **MODEL-03** and **MODEL-04** (recorded in `requirements-completed`); MODEL-08 is further reinforced but was already completed by plan 03-05.

## Self-Check: PASSED

| Claim | Result |
|-------|--------|
| `packages/paaf-llm/src/paaf_llm/agent.py` | FOUND |
| `packages/paaf-llm/tests/test_agent_turn.py` | FOUND |
| `packages/paaf-llm/tests/test_fallback.py` | FOUND |
| Commits `5a0e2b7`, `4716280`, `9ebe24b`, `431de21` | ALL FOUND |

---
*Phase: 03-paaf-llm-core*
*Completed: 2026-08-05*
