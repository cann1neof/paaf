---
phase: 04-agent-mesh
plan: 07
subsystem: llm-engine
status: complete
tags: [mesh, observer, mesh-06, d-03, d-04, d-06, oq-1, veto, reroute, grant]
requirements: [MESH-06, MESH-02]

requires:
  - "paaf_llm.mesh.resolve_handoff / handoff_tools / UndeclaredPeer (04-01) — reused, not duplicated"
  - "paaf_llm.mesh.tools_for_leg and the hop wall (04-03)"
  - "paaf_llm.compose.PromptComposer.segments(..., mesh_fragments) (04-05)"
  - "paaf_llm.agent.Agent._chain(agent_name) / _emit_handoff / the per-leg loop (04-06)"
  - "paaf_trace.store.HandoffEvent's observer_verdict / observer_profile / rerouted_to columns (04-02)"
provides:
  - "paaf_llm.observer — ObserverVerdict, HandoffAttempt, ObserverDecision, LegRunner, Observer.judge()"
  - "paaf_llm.mesh.OBSERVER_PROFILE_NAME / OBSERVER_GRANTS / OBSERVER_RETRY_TOOL / OBSERVER_REROUTE_PREFIX"
  - "paaf_llm.mesh.observer_tools() and retry_text() + MESH_RETRY_SOURCE / DEFAULT_RETRY_TEMPLATE"
  - "paaf_llm.profiles.LlmConfig.observer_grants / .observer_window_messages / .observer_window_handoffs"
  - "_check_refs rules 2 and 3 — the reserved name is never a participant"
  - "paaf_llm.agent.Agent.run_leg() (the LegRunner implementation) and system_prompt(..., extra_fragments)"
  - "paaf_llm.agent.HANDOFF_OBSERVER_RETRY / HANDOFF_OBSERVER_REROUTE"
  - "MeshSignalKind.OBSERVER_RETRY and .OBSERVER_REROUTE are now emitted (declared unemitted since 04-01)"
  - "packages/paaf-llm/tests/test_observer.py (22 tests, force-included)"
  - "tests/conftest.py::make_mesh_config(observer=, observer_grants=, observer_window_*, constraints=)"
affects:
  - "04-08 (the CLI / signals surface reads OBSERVER_RETRY / OBSERVER_REROUTE and renders the retry segment)"
  - "04-09 (the unobserved notice, the Pitfall-7 doc line, and marking MESH-05/MESH-06 complete)"

tech-stack:
  added: []
  patterns:
    - "Capability removal as the ONLY boundary — the grant is read off the surface that was just built"
    - "POWER and REACH are two questions; answering the second early would collapse a two-layer guard to one"
    - "A transient labelled prompt segment as the correction channel, never a widened Role"
    - "A recorded non-answer: PAAF does not decide on the model's behalf what it meant"
    - "Falsify every guard by deleting the mechanism it claims to measure, negative controls included"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/observer.py
    - packages/paaf-llm/tests/test_observer.py
  modified:
    - packages/paaf-llm/src/paaf_llm/mesh.py
    - packages/paaf-llm/src/paaf_llm/profiles.py
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/tests/conftest.py
    - packages/paaf-llm/pyproject.toml

decisions:
  - "The grant check answers 'may it re-route AT ALL', never 'may it reach THAT target' — the named target is handed on unvalidated so mesh.resolve_handoff is the one thing that decides reachability (deviation from the plan's literal name-membership check, which would have made D-06's second layer unreachable)"
  - "A veto SPENDS a hop: an observer that refuses everything and a model that keeps asking would otherwise loop with nothing counting, and the deterministic wall is the only termination guarantee"
  - "The observer's leg writes no runs / turn_legs row — the observer is never awake, so a turn_legs row would answer 'who was awake on this leg' with an agent that was not"
  - "The observer judges AFTER resolve_handoff, never before: the peer-graph guard is the one mesh guarantee that holds unobserved (D-13), so it is never asked to bless what the graph already refused"
  - "ObserverDecision.ungranted is a separate field rather than a fourth verdict — a verdict says what HAPPENED to the handoff, and an ungranted emission left it alone"
  - "LegRunner returns a 4-tuple (served_by, reply, trail, calls) rather than the plan's 3-tuple: a verdict is unreadable without the calls, and a second accessor would have made the protocol two methods"
  - "MESH-06 and MESH-02 both left Pending: 04-08 and 04-09 carry MESH-06 and are unexecuted (the 04-02 precedent)"

metrics:
  duration: ~70 min
  tasks: 3
  commits: 3
  files_changed: 7
  lines: +2117 / -17
  tests_added: 22
  suite: 290 passed (paaf-llm) / 377 passed (workspace) / 242 passed (clean venv, framework uninstalled)
  completed: 2026-08-07
---

# Phase 4 Plan 07: The Observer Summary

A small supervising model now judges every handoff attempt against the target agent's free-text hard constraints and can kill it — and its powers are exactly the tools it was granted, so a retry-only observer cannot re-route no matter what it emits, and a granted one cannot reach past the calling agent's own peer graph.

## What Was Built

**The observer is a reserved name, not a subsystem.** `mesh.OBSERVER_PROFILE_NAME` is written once; a profile sitting under that key is an ordinary `ModelProfile` and therefore inherits `Endpoint` declaration (and so Phase-9's offline refusal), `ReloadTier` metadata, `extra="forbid"` and secret-by-reference for free — the four things Pattern 5 says the design is relying on, now asserted rather than assumed. It is configurable down to its own system prompt, and `paaf prompt --agent observer` already prints it byte-exact, which is the only way to read the prompt of an agent that is never awake.

Reserving the name is what stops enabling the observer from adding an edge to the graph. `_check_refs` refuses it as a handoff target, as `active_profile`, and as a `fallback_chain` entry at either scope, each with the offending profile named. The peer case is the load-bearing one: without it, turning the observer on would quietly make a supervisor reachable from every agent that declared it, and MESH-02's graph would acquire a member the user never drew (T-04-36).

**The grant is the boundary, and the surface is where it is read.** `mesh.observer_tools(grants, caller_peers, profiles)` emits the retry spec when `generic_retry` is granted and one `reroute_to_<peer>` spec **per CALLER peer** when `reroute` is. `Observer._decide` then reads its recognized set straight back off that tuple, so there is exactly one place that decides what the observer may do and it is the same place that decided what the observer was offered. A grant check written against `LlmConfig.observer_grants` separately would be a second opinion about one question. The default is retry-only, so the shipped observer can bounce a handoff and can do nothing else — widening it is a readable edit to a config line, never something that arrives by upgrade.

**A veto reaches the caller as a transient labelled prompt segment, and nothing else.** `Agent.system_prompt` gained an `extra_fragments` keyword; on a veto the engine composes the calling agent's next leg with one extra `(mesh.MESH_RETRY_SOURCE, mesh.retry_text(...))` pair and clears it immediately, so the refusal exists for exactly one leg. It is a real `Segment`, held to `compose()`'s byte-exact invariant like every other one — a fragment that reached the model without being a segment would be the hidden prompt PERS-05 forbids — and it carries its own source label so `--provenance` can tell a one-off refusal from the standing explainer. `Role` still has exactly three members; OQ-1's option 1 stayed forbidden and is asserted directly.

**Termination survived the new loop.** A veto **spends a hop**. Without that, an observer that refuses every attempt and a model that keeps reaching for one would cycle with nothing counting, and D-08's guarantee — the budget terminates, the observer makes termination graceful — would be exactly backwards. The test adapter's leg cap turns a missing bound into a named assertion rather than a hung suite, and it never fires.

**`_emit_handoff` fills the three columns 04-06 left NULL, and the NULLs still mean something.** With an observer declared, `observer_verdict` is written on every attempt — `"approve"` included, because "the supervisor saw this and let it through" is the fact MESH-05 asks the trace to carry — alongside `observer_profile`, which names the profile that *actually* served the observer's leg and may be a fallback down its own chain. With no observer the three stay NULL: "nobody looked" and "the observer looked and said nothing" are different facts and D-07 turns on the difference. `MeshSignalKind.OBSERVER_RETRY` and `OBSERVER_REROUTE`, declared and unemitted since 04-01, now fire.

## Key Decisions

| Decision | Why |
|----------|-----|
| The grant answers "may it re-route at all", not "may it reach that target" | See deviation 1. Answering the second question in `_decide` would silently reduce a two-layer guard to one and make `reroute_guarded` untestable. |
| A veto spends a hop | The wall is the only termination guarantee (D-08). A killed attempt that costs nothing is an unbounded loop wearing a supervisor's hat. |
| The observer's leg writes no `runs` / `turn_legs` row | `turn_legs.agent` answers "who was awake on this leg". The observer is never awake, so a row for it would make that column lie. Its identity reaches the trace as `observer_profile` on the attempt row instead. |
| `judge` runs AFTER `resolve_handoff` | D-13: the peer-graph guard holds in every configuration, observed or not. Asking the observer to bless a target the graph already refused would invert that. |
| `ObserverDecision.ungranted` over a fourth verdict | A verdict says what happened to the handoff. An ungranted emission left it alone, so it is `APPROVE` with a record — not a new outcome. |
| `LegRunner` returns four values | A verdict cannot be read without the tool calls. The alternative was a second accessor, which would have widened the "one async method" protocol anyway. |
| MESH-06 and MESH-02 stay `Pending` | 04-08 and 04-09 both carry MESH-06 and are unexecuted; the unobserved notice (D-07) and the Pitfall-7 doc line are theirs. The 04-02 precedent. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The plan's grant check would have made D-06's second layer unreachable**

- **Found during:** Task 3
- **Issue:** Task 2's action says the recognized tool set is "derived from `mesh.observer_tools(...)` for this call" and that "a tool name outside the granted set is NOT translated into some other verdict". Read as exact-name membership — which is how Task 2 first implemented it — `reroute_to_admin` is simply not in the offered set, so it becomes an ungranted `APPROVE` and **never reaches `mesh.resolve_handoff` at all**. That directly contradicts Task 3's own `<behavior>` bullet ("an observer emitting `reroute_to_admin` where `admin` is NOT in the caller's peers raises exactly `UndeclaredPeer`"), and it is a real design defect, not only a test-writing one: it collapses the deliberate two-layer guard (surface + runtime check) down to the surface alone, which is precisely the shape Pitfall 4 says must never be relied on by itself.
- **Fix:** `_decide` now answers two separate questions. The **power** — may this observer re-route at all — is read off the surface (`any(name.startswith(OBSERVER_REROUTE_PREFIX) for name in offered)`), keeping the plan's "one place, the same place that built the surface" rule. The **reach** — may it reach *that* target — is deliberately not answered there: the named target is handed on unvalidated so the engine runs it through `mesh.resolve_handoff` with the CALLER's profile. This is the identical belt-and-braces shape `handoff_tools` + `resolve_handoff` has had since 04-01. Falsified both ways (see below).
- **Files modified:** `packages/paaf-llm/src/paaf_llm/observer.py`
- **Commit:** `43baecd`

**2. [Rule 3 - Blocking] `LegRunner`'s single async method could not carry a verdict**

- **Found during:** Task 2
- **Issue:** the plan specifies "one async method returning `(served_by, reply, trail)`". A verdict is read from the observer's **tool call**, which that tuple does not contain — so the protocol as written cannot be used for the thing it exists for. The alternatives were a second (sync) accessor mirroring `ChatAdapter.last_usage`, or a wider tuple.
- **Fix:** the tuple gained a fourth member, `(served_by, reply, trail, calls)`, keeping the protocol at exactly one method as the plan requires. The reply, the trail and the calls all describe the one leg that just ran, so they belong together; `_NullRunner` in the test file is four lines, which is the narrowness claim the docstring makes.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/observer.py`, `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `c7d48c9`

**3. [Rule 3 - Blocking] The plan's `detail` requirement collided with 04-06's use of the same column**

- **Found during:** Task 3
- **Issue:** Task 3 requires the ungranted emission to be "recorded in the attempt's `detail`". But 04-06 deliberately made `handoffs.detail` carry the pre-handoff prose verbatim, and `test_pre_handoff_prose_dropped_is_still_recoverable_from_the_trace` asserts that column equals exactly the dropped text. Overwriting it would break a T-04-31 mitigation; ignoring the plan would let an observer's overreach vanish (T-04-37).
- **Fix:** `ObserverDecision` gained an `ungranted` field carrying only the note, and `agent._with_note` prefixes it to the prose, dropping either half when empty — the same filter `PRE_HANDOFF_JOINER` applies to empty legs. With no observer, `ungranted` is `None` and the column is byte-identical to 04-06's; the D-11 test is untouched and green.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/observer.py`, `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `43baecd`

**4. [Rule 3 - Blocking] `test_observer.py` and its force-include entry landed in Task 1**

- **Found during:** Task 1
- **Issue:** Task 1's acceptance criteria demand passing tests for the reserved-name and grant rules, but its file list contains only `profiles.py` and `mesh.py`; the plan creates the test file and its `force-include` entry in Task 2. Worse, `check_framework_uninstalled.sh`'s non-vacuity guard compares the source `tests/` directory against the wheel and **fails** on any unshipped file — so a commit with the test file present and the entry absent would have left the SC#5 gate red at that commit.
- **Fix:** both landed in Task 1 (the 04-01 precedent, where `mesh.py`'s constants landed a task early for the same "the tree must be green at every commit" reason). Task 2 added the behavioural tests to the same file as planned. `test_observer_source_imports_no_agent_framework` stayed in Task 2, since `observer.py` does not exist until then.
- **Files modified:** `packages/paaf-llm/tests/test_observer.py`, `packages/paaf-llm/pyproject.toml`
- **Commit:** `b04217f`

**5. [Rule 3 - Blocking] `make_mesh_config` could express neither an observer nor a constraint**

- **Found during:** Tasks 1 and 2
- **Issue:** `conftest.py` is in no task's file list, but the shared fixture had no way to declare an `observer` profile, its grants, its window sizes, or — the thing MESH-06 is about — a profile's free-text `constraints`. Every observer test would have had to hand-build an `LlmConfig`.
- **Fix:** five pass-through parameters, omitted entirely when unset so the schema's own defaults stay the single source of truth (the `hop_budget` precedent). `observer` is **opt-in** rather than on by default, deliberately: every pre-existing mesh test must keep taking the unobserved path byte for byte, or "with no observer declared the mesh behaves exactly as before" would be a claim the fixture had quietly made untrue.
- **Files modified:** `packages/paaf-llm/tests/conftest.py`
- **Commits:** `b04217f`, `c7d48c9`

**6. [Rule 3 - Blocking] The `ObserverVerdict` exhaustiveness meta-test moved from Task 2 to Task 3**

- **Found during:** Task 2
- **Issue:** the plan puts the meta-test in Task 2, but `REROUTE`'s end-to-end test is a Task-3 artifact. A coverage map that spans the whole enum would have been red at the Task-2 commit; a map that did not would have been decoration.
- **Fix:** moved to Task 3 alongside the reroute tests, in `test_fallback.py`'s declared-data shape (`VERDICT_COVERAGE`), with a second assertion that each selector actually names a test function in this file's own source — so a renamed test breaks the map instead of silently leaving a verdict unmeasured.
- **Files modified:** `packages/paaf-llm/tests/test_observer.py`
- **Commit:** `43baecd`

**7. [Rule 3 - Blocking] The `REROUTE` branch of `turn()` landed in Task 2, not Task 3**

- **Found during:** Task 2
- **Issue:** Task 3 assigns the reroute call site to itself, but `turn()` dispatches on a three-member enum in one place. Handling two members in Task 2 and the third in Task 3 would have left an intermediate commit where a `REROUTE` decision fell silently through to the accepted path — a shipped bug for one commit, and un-bisectable.
- **Fix:** the whole dispatch (including `Agent._rerouted`) landed in `c7d48c9`; Task 3 then made `_decide` able to *produce* `REROUTE` and added the tests that exercise it. The falsification for Task 3 was run against the final tree, so nothing went unmeasured.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `c7d48c9`

### Falsification

Every guard this plan claims was broken on purpose before green was reported. The brief named three; six were run.

| Mechanism removed | Command | Result |
|---|---|---|
| `_check_refs`' reserved-name peer rule deleted | `pytest test_observer.py` | **1 failed** — `test_observer_may_not_be_a_handoff_target` |
| The `GENERIC_RETRY` branch made unreachable (veto silenced) | `pytest test_observer.py` | **2 failed** — `vetoes` and `history`, exactly the rows the brief demanded go red |
| The retry fragment never composed onto the leg | `pytest test_observer.py` | **1 failed** — `history`, on the segment's absence rather than on an absence check |
| **The observer never constructed at all** | `pytest test_observer.py` | **3 failed** — including **`allows`**, which is what proves the negative control is not vacuous: it could not pass with the observer disabled |
| `mesh.resolve_handoff` bypassed on the reroute path | `pytest test_observer.py` | **1 failed** — `reroute_guarded` |
| The grant check removed (any reroute emission honoured) | `pytest test_observer.py` | **1 failed** — `grant_bounds`, on the fake's `LookupError` for the deliberately-unprogrammed `cook` |
| The ungranted note dropped from `detail` | `pytest test_observer.py` | **1 failed** — `grant_bounds` |

The `allows` row is the one worth calling out. The wave brief warned that "a negative control that would pass even with the observer entirely disabled proves nothing", so it asserts the observer leg **ran** (it appears in `FakeAdapter.calls`) and that its verdict reached the row as `approve` — neither of which a disabled observer produces.

### Non-Vacuity Checks (per the wave-1 finding)

Every `-k` filter was confirmed to select a nonzero, intended set with `--collect-only -q` **before** being run.

| Command | Selected | Result |
|---|---|---|
| `test_observer.py -k vetoes` | 1 of 22 | passed |
| `test_observer.py -k allows` | 1 of 22 | passed |
| `test_observer.py -k history` | 1 of 22 | passed |
| `test_observer.py -k grant_bounds` | 1 of 22 | passed |
| `test_observer.py -k reroute_guarded` | 1 of 22 | passed |
| `test_observer.py -k source_imports_no_agent_framework` | 1 of 22 | passed |
| `test_mesh.py -k undeclared` | 1 of 31 | passed — the agent-side guard is unchanged |
| `test_mesh.py -k source_imports_no_agent_framework` | 1 of 31 | passed |

### Out of Scope — Logged, Not Fixed

**`uv run ruff check packages` is red at baseline on `paaf-core` (RUF022)** — an unsorted `__all__` in `packages/paaf-core/src/paaf_core/secrets/__init__.py`, a file no plan in this phase touches. Unchanged from 04-06's deferred item 3. `uv run ruff check packages/paaf-llm packages/paaf-trace` passes, and every file this plan touched is `ruff format`-clean individually.

## Known Stubs

Each is a plan-assigned deferral; none blocks this plan's goal.

| Stub | File | Resolved by |
|------|------|-------------|
| `MeshSignalKind.UNOBSERVED` is still declared and never emitted — D-07's "says so plainly (startup line + trace)" has no writer | `agent.py`, `ports.py` | 04-08 (which owns the CLI / signals surface) |
| `paaf prompt --agent observer --provenance` shows the observer's system prompt but **not** its tool surface — `observer_tools` is per-attempt (it depends on the caller's peers), so there is no single caller to render it against | `cli.py` | 04-08 |
| The Pitfall-7 documentation line CONTEXT asks for by name (a wide window on a cloud observer ships conversation off-box on every attempt) exists as a field comment and a docstring, not as user-facing docs | `profiles.py` | 04-09 |
| The observer's leg writes no `runs` / `turn_legs` row, so its model round-trip is not visible in the per-leg trace | `agent.py` | unassigned — a deliberate decision, recorded above, not an omission |
| A SQL error inside `TraceStore._writer` still kills the writer and deadlocks `stop()` | `paaf_trace/store.py` | unassigned — deferred item 2 from 04-02, unchanged |

**Resolved from earlier stub lists:** 04-06's three NULL observer columns are now written; 04-03's "the observer does not yet break a loop before the wall" is built; two of the three unemitted `MeshSignalKind` members now fire.

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-32 EoP (injection argues the observer into a re-route) | mitigated | The recognized power is read off `observer_tools`' output for that call; default retry-only. `grant_bounds` proves both halves. **Falsified** — deleting the grant check turns it red. |
| T-04-33 EoP (observer as a back door) | mitigated | Enforced twice: `reroute_to_<peer>` specs are emitted for CALLER peers only, and the named target passes `mesh.resolve_handoff` with the CALLER's profile. `reroute_guarded` asserts the same `UndeclaredPeer` type and a message naming the caller's peers; `test_enabling_the_observer_adds_no_reachable_target` asserts the subset over the whole graph. **Falsified.** |
| T-04-34 Tampering (veto delivery) | mitigated | The refusal is a transient labelled `Segment` on one leg's message list. `Role` is asserted to remain a three-member `Literal`; the retry text is asserted absent from `Agent.history` and from the first leg's prompt. **Falsified.** |
| T-04-35 Info disclosure (window + cloud endpoint) | mitigated | The observer is an ordinary `ModelProfile`, so its `Endpoint` is declared; both windows default to 0 and reject negatives; the field comments carry the warning. The user-facing doc line is 04-09's, and is listed as a stub rather than claimed. |
| T-04-36 Spoofing (reserved name) | mitigated | `_check_refs` rejects the name as a peer, as `active_profile`, and in a `fallback_chain` at either scope, each naming the offending profile. **Falsified** — deleting the peer rule turns it red. |
| T-04-37 Repudiation (ungranted emission) | mitigated | `ObserverDecision.ungranted` carries the offending tool name and the offered set onto the attempt row's `detail`; the handoff proceeds unchanged and is not reinterpreted. **Falsified** — dropping the note turns `grant_bounds` red. |
| T-04-38 DoS (one observer call per attempt) | accepted | `judge` is called once per ATTEMPT (D-14) and never per turn or per token; bounded by the hop budget, which a veto now spends. The cost is documented in `judge`'s docstring rather than hidden. |
| T-04-SC Dependency surface | accepted | Zero packages installed. `pyproject.toml` changed by exactly one line: a `force-include` test entry. |

**Threat flags:** one, and it is the one the threat model already names. The observer profile is a **new network egress path** exercised on every handoff attempt (T-04-35 / Pitfall 7). It introduces no new code path to the network — it goes through the same `ChatAdapter` port and the same declared `Endpoint` as any other profile — so there is no unmodelled surface, but the *frequency* is new and the user-facing documentation of it is 04-09's, tracked above.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest packages/paaf-llm -q` | 290 passed (268 before this plan) |
| `uv run pytest -q` (workspace) | 377 passed |
| `bash scripts/check_framework_uninstalled.sh` | **PASS** — 242 tests green in the clean venv; the non-vacuity guard reports **all 14** test files shipped, `tests/test_observer.py` included |
| `uv run lint-imports` | 3 contracts kept, 0 broken — **`.importlinter` unchanged**, no new carve-out |
| `uv run ruff check packages/paaf-llm packages/paaf-trace` | All checks passed |
| `uv run ruff format --check` (all 6 files this plan touched) | 6 files already formatted |
| `uv run pytest packages/paaf-llm/tests/test_mesh.py packages/paaf-llm/tests/test_mesh_trace.py -q` | 38 passed — a config with no observer behaves exactly as in 04-06 |
| `python -c "... c.observer_grants==['generic_retry'] and windows==0"` | exit 0 |
| `python -c "... len(mesh.observer_tools(('generic_retry',), ('chef','cook'), {}))==1"` | exit 0 |
| `python -c "... set(get_args(Role))=={'system','user','assistant'}"` | exit 0 — OQ-1 option 1 stayed forbidden |
| `python -c "... 'tests/test_observer.py' in force-include"` | exit 0 |
| `python -c "... inspect.getsource(agent).count('resolve_handoff') >= 2"` | exit 0 — 5 occurrences; the observer path calls the same guard |
| `paaf prompt --config … \| xxd` | ends `never been said.` — no trailing newline (D-19 unchanged) |
| `paaf prompt --config … --agent observer \| xxd` | `You supervise handoffs.` — 23 bytes, no trailing newline |

**Phase invariants re-checked at commit time:**

1. **OQ-1 honoured literally** — the veto is a transient labelled prompt segment on one leg's message list; `Role` unchanged; nothing in `Agent.history`; the text comes from `mesh.retry_text`, the same `str.replace` machinery `explainer_for` uses, under its own `mesh:observer-retry` source.
2. **D-06 through the SAME guard** — `Agent._rerouted` calls `mesh.resolve_handoff(awake, profile, …)`. `test_mesh.py -k undeclared` is unchanged and green; the observer's rejection is asserted to be the same exception class.
3. **D-04 enforced by the system** — the grant is read off the surface, not off the observer's output. `grant_bounds` covers both halves.
4. **No `ALTER TABLE`, no new column on `runs`** — `packages/paaf-trace` untouched (0 lines). The three columns filled were declared by 04-02.
5. **Force-include** — `tests/test_observer.py` added; the gate's guard reports 14/14 shipped.
6. **`compose()` byte-exact WIDENED, not weakened** — `compose.py` untouched (0 lines); `test_no_hidden_prompt` passes under its own name; the retry segment is an ordinary `Segment` subject to the same split-and-compare.
7. **`paaf prompt` default output byte-exact** — `cli.py` untouched (0 lines); verified with `xxd`.
8. **`langchain*` confined to `paaf_llm._engine`** — `lint-imports` green, `.importlinter` unchanged; `test_observer_source_imports_no_agent_framework` asserts it against `observer.py`'s source text.

**04-VALIDATION.md rows green,** each selected by its documented `-k` command and confirmed non-vacuous: `vetoes`, `allows`, `reroute_guarded`, `grant_bounds`.

**ROADMAP SC#5's first half** is satisfied for the observed case: an optional hard constraint declared in free text on an agent is enforced by the system regardless of what the routing model attempts (D-13's ruling that the observer counts as the system), and D-07's honest caveat — the mesh can run unobserved — is preserved rather than papered over.

## Requirements

**MESH-06 and MESH-02 both deliberately left `Pending`**, following the precedent every prior plan in this phase set.

- **MESH-06** — 04-08 and 04-09 both carry it and are unexecuted. Two of the six MESH-06 validation rows this phase declares belong to them, and D-07's "the mesh runs unobserved and says so plainly" has no writer yet (`MeshSignalKind.UNOBSERVED` remains declared and unemitted). Marking it Complete here would let an audit read "constraints are enforced by the system" as fully satisfied while a user running unobserved is told nothing.
- **MESH-02** — already carried by 04-01 and left Pending there; this plan extends its guarantee to the observer rather than completing it, and 04-09 is the last plan carrying it.

`roadmap update-plan-progress` was run; `requirements mark-complete` was deliberately not.

## Self-Check: PASSED

- `packages/paaf-llm/src/paaf_llm/observer.py` — FOUND
- `packages/paaf-llm/tests/test_observer.py` — FOUND
- `packages/paaf-llm/src/paaf_llm/mesh.py` — FOUND (`observer_tools`, `retry_text`, `OBSERVER_PROFILE_NAME`)
- `packages/paaf-llm/src/paaf_llm/profiles.py` — FOUND (`observer_grants`, the two windows, `_check_refs` rules 2/3)
- `packages/paaf-llm/src/paaf_llm/agent.py` — FOUND (`run_leg`, `_attempt`, `_rerouted`, `_with_note`)
- Commit `b04217f` — FOUND in `git log`
- Commit `c7d48c9` — FOUND in `git log`
- Commit `43baecd` — FOUND in `git log`
