---
phase: 04-agent-mesh
plan: 01
subsystem: llm-engine
status: complete
tags: [mesh, handoff, ports, protocol, peer-guard, fake-adapter]
requirements: [MESH-01, MESH-02, MESH-03]

requires:
  - "paaf_llm.ports.ChatAdapter (Phase 3) — extended, not edited"
  - "paaf_llm.profiles.ModelProfile.peers / .capabilities (Phase 3, inert until now)"
  - "paaf_llm.agent.Agent._run_chain fallback loop (Phase 3)"
provides:
  - "paaf_llm.ports.ToolSpec / ToolCall / HandoffRequest"
  - "paaf_llm.ports.ToolCallingChatAdapter (second Protocol, runtime_checkable)"
  - "paaf_llm.ports.UndeclaredPeer (exception taxonomy sibling)"
  - "paaf_llm.ports.MeshSignal / MeshSignalKind (6 members) / MeshSignalSink"
  - "paaf_llm.mesh.HANDOFF_TOOL_PREFIX / DEFAULT_HOP_BUDGET"
  - "paaf_llm.mesh.handoff_tools() / target_of() / resolve_handoff()"
  - "paaf_llm.agent.Agent.awake_agent / Agent._signal() / signals= keyword"
  - "paaf_llm.agent.Agent._run_chain(messages, tools=())"
  - "paaf_llm.fake.FakeAdapter.stream_with_tools() / last_tool_calls() / tool_offers"
  - "paaf_llm.fake.FakeAdapter.program(tool_calls=...)"
  - "tests/conftest.py::make_mesh_config fixture"
affects:
  - "04-02 (adapter stream_with_tools), 04-03 (hop budget config, hand-back)"
  - "04-04 (one runs row per leg, turn_id correlation)"
  - "04-05 (renders handoff_tools() specs in the prompt inspector)"
  - "04-06 (per-agent fallback_chain replaces the global chain in _chain())"
  - "04-07 (observer consumes MeshSignalKind.OBSERVER_* and the guard)"

tech-stack:
  added: []
  patterns:
    - "Capability extension by a SECOND Protocol rather than editing the port (D-02)"
    - "Belt-and-braces enforcement: capability removal AND a runtime guard (Pattern 2)"
    - "Publish-after-drain for tool calls, mirroring the proven last_usage() seam"
    - "Fresh per-leg message list; no framework/message state carried between legs"

key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/mesh.py
    - packages/paaf-llm/tests/test_mesh.py
    - .planning/phases/04-agent-mesh/deferred-items.md
  modified:
    - packages/paaf-llm/src/paaf_llm/ports.py
    - packages/paaf-llm/src/paaf_llm/__init__.py
    - packages/paaf-llm/src/paaf_llm/agent.py
    - packages/paaf-llm/src/paaf_llm/fake/__init__.py
    - packages/paaf-llm/tests/conftest.py
    - packages/paaf-llm/tests/test_ports.py
    - packages/paaf-llm/tests/test_fake_adapter.py
    - packages/paaf-llm/tests/test_no_leak.py
    - packages/paaf-llm/pyproject.toml

decisions:
  - "ToolCallingChatAdapter EXTENDS ChatAdapter as a second runtime_checkable Protocol — the Phase-3 port definition is byte-identical (D-02, Finding 3)"
  - "UndeclaredPeer is a sibling of AllProvidersFailed/EngineError and subclasses neither AdapterError nor EngineError"
  - "All six MeshSignalKind members declared in this plan even though four are triggered later — ports.py is edited by one plan, so a later edit would serialize a wave"
  - "FakeAdapter publishes scripted tool_calls ONLY on the stream_with_tools path; a provider offered no tools cannot have called one"
  - "program(tool_calls=...) deliberately does not validate names against the offered set — that is what gives the MESH-02 guard a negative control"
  - "Agent._chain() now starts at awake_agent rather than config.active_profile; resilience follows whoever is being asked to answer"
  - "MESH_UNAVAILABLE is announced once per Agent, not once per turn — it reports a static fact about the adapter"
  - "mesh.py constants landed in the Task-2 commit so the new suite collects cleanly; the functions landed in Task 3"

metrics:
  duration: ~50 min of active execution (spanned a session reset)
  tasks: 3
  commits: 3
  files_changed: 11
  lines: +1369 / -56
  tests_added: 26
  suite: 158 passed, 1 skipped (paaf-llm) / 239 passed, 1 skipped (workspace)
  completed: 2026-08-07
---

# Phase 4 Plan 01: The Mesh Seam Goes Live Summary

The awake model is now offered one `transfer_to_<peer>` tool per declared peer, picks a peer itself, and the receiving agent answers with the full prior conversation in hand — with a target outside the declared peers raising a catchable `UndeclaredPeer` instead of being followed, all provable with the agent framework uninstalled.

## What Was Built

**A second port protocol, not a wider one.** `ChatAdapter` needed a tool vocabulary it could not carry, and D-02 forbade reshaping it. `ToolCallingChatAdapter(ChatAdapter, Protocol)` resolves both literally: the Phase-3 definition is byte-identical (`test_chat_adapter_is_a_two_method_protocol` is the negative control that keeps it so), and the engine feature-detects with `isinstance`. An adapter that is not one runs the single-agent path and *says so* via `MeshSignalKind.MESH_UNAVAILABLE` rather than behaving as if no peer were declared.

**A guard that is enforced twice, on purpose.** `mesh.handoff_tools()` shapes the surface so only declared peers are offerable (capability removal), and `mesh.resolve_handoff()` checks the answer anyway against `awake.peers` — never `LlmConfig.profiles`. The redundancy is the requirement: models routinely emit tool names that were never bound, so a design resting on the surface alone would make MESH-02's "rejected, never silently followed" contingent on the provider behaving (Pitfall 4). `test_undeclared_target_raises` declares `admin` as a real profile precisely so the natural wrong implementation (`profiles[target]`) resolves it happily and fails.

**A handoff loop that cannot spring the classic trap.** `Agent.turn()` is now a bounded loop over agent legs wrapped around the unchanged fallback loop. Each leg builds a *fresh* `[system, *history, user]` list — one line that is simultaneously MESH-03's guarantee, the reason A→B→A hand-back will work in 04-03, and the reason a dangling tool call cannot survive between legs. The handoff tool call is never appended to `Agent.history`, and `Role` stays a closed three-member `Literal` (OQ-1 forbids widening it).

**A fake that can script all of it.** `FakeAdapter` is now a `ToolCallingChatAdapter`. `tool_offers` records what was *offered* so capability removal is provable rather than merely asserted, and `program(tool_calls=...)` deliberately does not validate names against the offered set — that omission is what makes the MESH-02 negative control writable at all.

## Key Decisions

| Decision | Why |
|----------|-----|
| Second Protocol over a `tools=()` keyword on `stream` | The keyword is backward-compatible for callers but still *edits* the port. D-02 says the shape must not change. |
| `UndeclaredPeer` subclasses neither `AdapterError` nor `EngineError` | An `AdapterError` means "try the next profile", so the fallback loop would swallow a routing violation and print `↳ fell back to cloud (connection)` at a routing bug. An `EngineError` would blame the user's YAML when `_check_refs` already proved the graph integral. |
| All six `MeshSignalKind` members declared now | `ports.py` is edited by exactly this plan in the phase; a later edit to add two members would serialize another wave behind it. |
| Scripted tool calls publish only on the tools-offered path | Otherwise an engine that never offered the handoff tools could still "receive" a handoff, and the test written to catch that would pass. Covered by `test_scripted_tool_calls_are_not_published_by_plain_stream`. |
| `_chain()` starts at `awake_agent` | Falling back from `active_profile` while a peer holds the conversation would answer as the wrong agent. Identical to Phase-3 behavior before any handoff, which is why no Phase-3 test moved. |
| Hop budget enforced from this plan, not deferred to 04-03 | Every hop is a full model round-trip on the latency path (Pitfall 6, T-04-04). "We will bound it next plan" would ship an unbounded loop for a wave. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `mesh.py`'s constants landed one task early**

- **Found during:** Task 2
- **Issue:** `tests/test_mesh.py` imports `paaf_llm.mesh`, but the plan creates `mesh.py` in Task 3. Task 2's own acceptance criterion requires `pytest packages/paaf-llm --collect-only` to report **no collection errors** — impossible with the module absent, and committing a collection error would have left the tree un-bisectable at `deed5db`.
- **Fix:** the Task-2 commit created `mesh.py` with its module docstring and the two constants (`HANDOFF_TOOL_PREFIX`, `DEFAULT_HOP_BUDGET`) only. The three functions landed in Task 3 as planned. RED stayed genuine — the mesh suite failed 9/10 at `deed5db` with `AttributeError`, which is proper TDD red rather than an import error.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/mesh.py`
- **Commit:** `deed5db`

**2. [Rule 1 - Bug] `test_no_leak.py` stubbed `HandoffRequest` as `object`, shadowing the now-real type**

- **Found during:** Task 1
- **Issue:** `_RESOLUTION_NS` stubbed `HandoffRequest` as `object` because Phase 3 had no payload. With the real dataclass defined, the stub *overrides* it in the annotation walker's namespace — so `test_public_signatures_are_paaf_typed` would keep inspecting `object` and would no longer be looking at `TurnResult.handoff` at all. A silent hole in a leak detector.
- **Fix:** removed the entry so the annotation resolves to the real type, with a comment explaining that a stub outliving the thing it stood in for is a hole, not a convenience.
- **Files modified:** `packages/paaf-llm/tests/test_no_leak.py`
- **Commit:** `403c32f`

**3. [Rule 1 - Bug] The plan's own acceptance command did not match the test name it prescribed**

- **Found during:** Task 3
- **Issue:** the plan names the test `test_declared_target_not_blocked` but verifies it with `pytest -k declared_not_blocked` (the same command 04-VALIDATION.md's Per-Task Verification Map binds). That `-k` filter deselects all ten tests — the row would have read green-by-vacuity in any automated check.
- **Fix:** renamed the test to `test_declared_not_blocked` so the documented command selects it. Verified all seven `-k` commands from the acceptance criteria select exactly one test each.
- **Files modified:** `packages/paaf-llm/tests/test_mesh.py`
- **Commit:** `632a538`

**4. [Rule 1 - Bug] `agent.py`'s module docstring misstated the chain after the `_chain()` change**

- **Found during:** Task 3
- **Issue:** the docstring advertised `[active_profile, *fallback_chain]`, which stopped being true the moment `_chain()` started from `awake_agent`.
- **Fix:** corrected it and added the Phase-4 paragraph explaining the two nested loops (delegation vs. resilience) and the three load-bearing properties of the handoff loop.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/agent.py`
- **Commit:** `632a538`

### Out of Scope — Logged, Not Fixed

**Pre-existing `ruff format` drift across six `paaf-llm` files.** `ruff format --check` reports six files that would be reformatted *at baseline*, before this phase touched anything; `ruff` is unpinned in the dev group and no CI job runs the check. Reformatting six unrelated files inside a mesh plan would have buried the plan's real diff. Files this plan touches are format-clean individually. Recorded in `.planning/phases/04-agent-mesh/deferred-items.md` with a suggested fix (pin `ruff`, reformat once, add the CI step).

## Known Stubs

Each is an intentional, plan-assigned deferral rather than an unfinished edge. None blocks this plan's goal.

| Stub | File | Resolved by |
|------|------|-------------|
| `DEFAULT_HOP_BUDGET` is a module constant, not user-configurable; reaching the wall silently withdraws the tools with no `BUDGET_EXHAUSTED` signal and no home-agent terminator | `mesh.py` | 04-03 (configurable with a floor of 3, withdrawal + exhaustion path, D-09) |
| Four `MeshSignalKind` members (`BUDGET_EXHAUSTED`, `OBSERVER_RETRY`, `OBSERVER_REROUTE`, `UNOBSERVED`) are declared but never emitted | `ports.py` | 04-03 and 04-07 (see decision above for why they are declared now) |
| One `runs` row per **turn**, describing the answering leg — a handed-off turn loses the first leg's `fallback_trail` from the trace | `agent.py::_drain` | 04-04 (one row per leg, correlated by the `turn_id` this plan already generates) |
| `system_prompt()` composes the same prompt for every leg; the handoff explainer and the tool surface are not in it | `agent.py`, `compose.py` | 04-05 (per-agent assembly, MESH-04/PERS-05) |
| `_chain()` uses the single global `fallback_chain` for every agent | `agent.py` | 04-06 (`ModelProfile.fallback_chain`, SC#4) |
| `LangChainAdapter` is not a `ToolCallingChatAdapter`, so the mesh runs on the fake only | `_engine/__init__.py` | 04-02 (`stream_with_tools` on the real adapter) |

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-01 Elevation of Privilege (injected handoff to a wider-privileged agent) | mitigated | `mesh.resolve_handoff` checks `target in awake.peers` unconditionally; `test_undeclared_target_raises` + `test_declared_not_blocked` |
| T-04-02 Spoofing (tool name never bound) | mitigated | Capability removal (`handoff_tools`) plus the runtime guard; a name without `HANDOFF_TOOL_PREFIX` is rejected by name, not silently resolved (`test_resolve_handoff_rejects_a_name_without_the_handoff_prefix`) |
| T-04-03 Tampering (`Agent.history` poisoning) | mitigated | The tool call is never appended; `test_history_clean_of_tool_calls` asserts both the history contents and that `Role` still has exactly three members |
| T-04-04 DoS (unbounded hop loop) | mitigated | `mesh.DEFAULT_HOP_BUDGET = 3` bounds `turn()` from this plan onward |
| T-04-05 Info disclosure in the error text | accepted | The message names only the user's own config, already printed by `paaf profiles` |
| T-04-SC Dependency surface | accepted | Zero packages installed; no change to `pyproject.toml` dependencies |

**Threat flags:** none. No new network endpoint, auth path, file access, or schema change was introduced.

## Verification

| Gate | Result |
|------|--------|
| `uv run pytest packages/paaf-llm -q` | 158 passed, 1 skipped |
| `uv run pytest -q` (workspace) | 239 passed, 1 skipped |
| `uv run lint-imports` | 3 contracts kept, 0 broken — **no new carve-out in `.importlinter`** (file unchanged) |
| `bash scripts/check_framework_uninstalled.sh` | PASS — 161 tests green in the clean venv; non-vacuity guard reports **all 12** test files shipped, including `tests/test_mesh.py` |
| `uv run ruff check packages/paaf-llm` | All checks passed |
| `uv run ruff format --check` (files this plan touches) | Clean (see deferred item for the pre-existing baseline drift) |

**Six MESH rows of 04-VALIDATION.md, each selected by its documented `-k` command and passing individually:** `accepts_declared`, `tool_surface`, `undeclared`, `declared_not_blocked`, `carries_history`, `history_clean`. Plus `source_imports_no_agent_framework`.

**Phase invariants re-checked at commit time:** no `ALTER TABLE` and no change under `packages/paaf-trace` (0 lines); `compose.py` and `cli.py` untouched (0 lines), so the byte-exact `compose()` invariant and `paaf prompt`'s default output are unaltered; `Role` unchanged; `.importlinter` unchanged.

## Self-Check: PASSED

All created files exist on disk (`mesh.py`, `test_mesh.py`, `deferred-items.md`) and all three commits resolve in `git log` (`403c32f`, `deed5db`, `632a538`).
