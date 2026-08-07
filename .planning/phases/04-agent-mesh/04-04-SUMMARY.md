---
phase: 04-agent-mesh
plan: 04
subsystem: llm-engine
status: complete
tags: [mesh, adapter, langchain, bind-tools, tool-calling, assumption-a1, mesh-01, model-08]

requires:
  - "paaf_llm.ports.ToolCallingChatAdapter / ToolSpec / ToolCall (04-01) — implemented, not edited"
  - "paaf_llm._engine.LangChainAdapter.stream / _usage_of / _translate / _scrub / bind (Phase 3)"
  - "paaf_llm.agent._run_chain's isinstance feature detection (04-01, widened by 04-03)"
provides:
  - "paaf_llm._engine._to_framework_tools(tools) — THE single ToolSpec-to-function-dict translation"
  - "paaf_llm._engine.LangChainAdapter.stream_with_tools(profile, messages, tools)"
  - "paaf_llm._engine.LangChainAdapter.last_tool_calls() / ._last_tool_calls"
  - "paaf_llm._engine.LangChainAdapter._tool_calls_of(aggregate) (static, the twin of _usage_of)"
  - "paaf_llm._engine.LangChainAdapter._bind_with_tools(profile, tools) (the EngineError boundary)"
  - "scripts/check_tool_streaming.py — the NON-BLOCKING live A1 check, outside pytest and outside CI"
  - "Assumption A1: measured and CONFIRMED on langchain-ollama==1.1.0 / Ollama 0.32.1"
affects:
  - "04-05 (renders the same name/description bytes _to_framework_tools shapes, in --provenance)"
  - "04-06 (per-agent fallback_chain runs over this call shape; one runs row per leg)"
  - "04-07 (the observer's grant tools reach a live provider through this method)"
  - "04-09 (the live-provider mesh verification this plan makes possible at all)"
  - "Phase 9 (the TTFA gate — see deferred item 4, the reasoning-model latency finding)"

tech-stack:
  added: []
  patterns:
    - "Framework tool vocabulary confined to ONE function returning a plain dict — no framework tool object is ever constructed"
    - "Aggregation-then-read extended from usage to tool calls: the same seam, the same reason, the same publish site"
    - "A binding failure raises like bind() (unconditional EngineError), NOT like a stream failure (_translate)"
    - "A live-provider assumption closed by a scratch script that gates nothing, deliberately outside pytest"

key-files:
  created:
    - scripts/check_tool_streaming.py
  modified:
    - packages/paaf-llm/src/paaf_llm/_engine/__init__.py
    - packages/paaf-llm/tests/test_engine_adapter.py
    - .planning/phases/04-agent-mesh/deferred-items.md

key-decisions:
  - "A bind_tools failure is raised as an unconditional EngineError rather than routed through _translate — the plan asked for both and they conflict; the behavior contract (never an AdapterError) wins, and a negative control now pins it"
  - "The tool binding is NOT cached with the model: the offered surface changes per leg (the hop budget withdraws it entirely at the wall), so a cached binding would serve one leg's moves to the next"
  - "_to_framework_tools builds the empty-parameters schema fresh per tool rather than sharing a module constant — a mutable dict handed out twice is one caller's edit away from rewriting another tool's declaration"
  - "The A1 check drives the PAAF port (stream_with_tools / last_tool_calls), not the framework directly, so a green result is evidence about the thing that ships"
  - "The no-tools short-circuit is asserted as a CALL (bound_tools == []), not as equal output — bind_tools([]) is a different call and historically a different mode"

patterns-established:
  - "Falsification-by-substitution: each of the four design-critical guards was inverted out of band and shown to produce exactly one named red test"
  - "A live check that records a disposition (confirmed / refuted / not run, and why) instead of returning an exit code"

requirements-completed: []

coverage:
  - id: D1
    description: "LangChainAdapter satisfies ToolCallingChatAdapter, so a handoff is reachable against a live provider rather than only against the fake"
    requirement: MESH-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_the_real_adapter_is_a_tool_calling_chat_adapter"
        status: pass
      - kind: other
        ref: "uv run python -c \"from paaf_llm._engine import LangChainAdapter; from paaf_llm.ports import ToolCallingChatAdapter; assert isinstance(LangChainAdapter(), ToolCallingChatAdapter)\""
        status: pass
    human_judgment: false
  - id: D2
    description: "PAAF ToolSpecs translate to bind_tools' function dicts in exactly one place, with empty parameters becoming an empty JSON Schema object"
    requirement: MESH-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_tool_spec_translates_to_one_openai_style_function_dict"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_tool_with_no_parameters_still_declares_an_empty_schema_object"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_offering_no_tools_never_calls_bind_tools"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tool calls are read off the aggregated stream and returned as PAAF ToolCalls, never off a chunk (T-04-16)"
    requirement: MESH-01
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_tool_calls_are_read_off_the_aggregate_never_off_a_chunk"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_stream_with_tools_publishes_the_call_after_the_stream_drains"
        status: pass
    human_judgment: false
  - id: D4
    description: "A bind_tools failure surfaces as EngineError, never as a degraded provider, with resolved secrets scrubbed (T-04-15)"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_bind_tools_failure_is_a_config_error_not_a_degraded_provider"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_bind_tools_failure_is_never_reclassified_as_a_transport_error"
        status: pass
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_a_resolved_key_never_appears_in_a_bind_tools_failure"
        status: pass
    human_judgment: false
  - id: D5
    description: "No framework type crosses the port on the new path — every yielded value is exactly str (T-04-18, MODEL-08)"
    verification:
      - kind: unit
        ref: "packages/paaf-llm/tests/test_engine_adapter.py#test_stream_with_tools_publishes_the_call_after_the_stream_drains"
        status: pass
      - kind: other
        ref: "uv run lint-imports (3 contracts kept, 0 broken; .importlinter unchanged)"
        status: pass
      - kind: integration
        ref: "bash scripts/check_framework_uninstalled.sh (184 tests green in a clean venv)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Assumption A1 measured against local Ollama and recorded with an explicit disposition"
    verification:
      - kind: manual_procedural
        ref: "uv run --all-packages --extra engine python scripts/check_tool_streaming.py qwen3.5:2b qwen3.5:9b"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-07
---

# Phase 4 Plan 04: The Real Adapter Grows Tools Summary

**`LangChainAdapter` is now a `ToolCallingChatAdapter`, so the mesh runs against a live Ollama model and not only against the fake — and the live check proves binding a handoff tool does not cost a single streamed token.**

## Performance

- **Duration:** ~25 min of active execution
- **Tasks:** 2 (Task 1 executed TDD: RED → GREEN)
- **Files modified:** 4 (1 created)
- **Tests added:** 16 (35 → 51 in the engine-adapter lane)

## Accomplishments

- The real adapter satisfies the second port protocol. Every mesh test written so far proved something about `FakeAdapter`; from this commit a handoff is reachable against the model a self-hoster actually runs.
- The framework's tool vocabulary is confined to one function that returns a plain dict. No `StructuredTool`, no `@tool` callable, no Pydantic args schema — `bind_tools` accepts the OpenAI-style function dict directly, so swapping the framework means rewriting one dict literal.
- Assumption A1 is closed by measurement rather than by inference from an issue closure, and it gates nothing.
- Four design-critical guards were falsified out of band and each produced exactly one named red test.

## Task Commits

1. **Task 1 (RED): failing tests for the tool-calling half** — `d483b36` (test)
2. **Task 1 (GREEN): LangChainAdapter satisfies ToolCallingChatAdapter** — `6213d80` (feat)
3. **Task 2: close assumption A1 with a live check that gates nothing** — `4b46e3d` (chore)

No REFACTOR commit: the GREEN implementation is the shape the plan specified and the falsification run found nothing to clean up.

## Files Created/Modified

- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` — `_to_framework_tools`, `LangChainAdapter._bind_with_tools`, `._tool_calls_of`, `.stream_with_tools`, `.last_tool_calls`, `._last_tool_calls`; module and class docstrings corrected to state the tool-vocabulary confinement and the second protocol.
- `packages/paaf-llm/tests/test_engine_adapter.py` — 16 offline tests under the existing `importorskip` guard; `_StubModel` gained `bind_tools` recording and a `bind_tools_error` injection point.
- `scripts/check_tool_streaming.py` — the live A1 check. Outside `testpaths`, referenced by no workflow, exits 0 unconditionally.
- `.planning/phases/04-agent-mesh/deferred-items.md` — two new out-of-scope findings, one widened.

## What Was Built

**The other half of the port, and it is small on purpose.** `stream_with_tools` is `stream` plus a binding plus one more post-drain assignment. Every non-negotiable of `stream` is carried over *verbatim* rather than referenced — the `str()` port-leak guard, the empty-chunk drop, the bare `except Exception` boundary that lets `GeneratorExit` and `CancelledError` through so the engine's timeout can `aclose()` cleanly, and the publish-after-drain rule. Two bodies that must agree are two bodies that eventually do not, so each carried-over line kept the comment explaining why it is there.

**`_tool_calls_of` is `_usage_of` with sharper teeth.** The test that matters asserts *both* halves of the aggregation rule against real `AIMessageChunk`s split mid-JSON: the summed message carries `arguments == {"reason": "maths"}`, and the first chunk alone carries `{}`. That asymmetry is the whole threat (T-04-16). A per-chunk read does not fail loudly — the framework declines to parse `'{"rea'` and reports empty args — so it would hand the mesh a plausible-looking `ToolCall` whose arguments had silently vanished, and a truncated *name* would then be rejected by 04-01's peer guard for entirely the wrong reason.

**A binding failure raises like `bind()`, not like a stream failure.** This is the one place the plan contradicted itself and the resolution is load-bearing — see Deviations. `bind_tools` contacts nobody, exactly as `bind()` does not, so a tool surface the provider refuses is a configuration problem that the next profile in the chain shares. `_scrub` stays on the path so a credential a provider echoed back cannot reach the error text (T-04-15).

**A1, measured.** RESEARCH inferred the fix from `langchain-ai/langchain#26971` being closed 2025-06-26 and from Ollama's 2025-05-28 incremental tool-call parser. Both inferences hold up under execution.

## Assumption A1 — CONFIRMED

Recorded in DECISIONS.md's measurement style.

**Pins:** `langchain==1.3.14`, `langchain-core==1.5.3`, `langchain-ollama==1.1.0` (exact, unchanged by this phase). **Server:** Ollama 0.32.1 on `127.0.0.1:11434`. **Date:** 2026-08-07.

| Model | prompt | tools bound | text chunks | ttft |
|-------|--------|-------------|-------------|------|
| `qwen3.5:2b` | plain prose | 1 handoff tool | **47** (57 on a second run) | 1.89 s (2.05 s) |
| `qwen3.5:9b` | plain prose | 1 handoff tool | **45** | 6.23 s |
| `qwen3.5:2b` | asks for a transfer | 1 handoff tool | 0 prose | — |
| `qwen3.5:9b` | asks for a transfer | 1 handoff tool | 0 prose | — |

**Disposition: CONFIRMED.** Token-level streaming survives `bind_tools` on the pinned versions. Both models also aggregated the handoff into exactly **one PAAF `ToolCall`, `name='transfer_to_ada'`, arguments parsed to a `dict`** — read through `last_tool_calls()`, i.e. through the port, not off the framework.

**Two secondary findings, recorded because they are load-bearing later:**

1. **RESEARCH's second surviving caveat reproduced.** On the handoff prompt both models returned the tool call and **zero accompanying prose**. This bears directly on **D-11 (pre-handoff prose)**: on these two models a handoff is silent unless the mesh puts something there itself. It is not a defect in this plan's change — the adapter yields what the model emits — but 04-05 should not assume the model narrates its own handoff.
2. **The comparison baseline was invalid, and the reason is worth more than the comparison.** The no-tools run measured 53.7 s / 78.1 s to first token, and once produced zero text in 88 s. This is not a streaming regression: `qwen3.5` is a reasoning model, and measured directly against `POST /api/chat`, **152 of 154 Ollama chunks carry `thinking` and exactly 1 carries `content`**. `langchain-ollama==1.1.0` does not surface thinking as text, so those arrive as empty chunks and `stream`'s empty-chunk drop correctly yields nothing for the whole thinking period. Logged as deferred item 4 — it affects the Phase-3 plain path and the first-token budget, not A1, and notably the **tools-bound path was 25× faster to first token** on the same prompt.

## Key Decisions

| Decision | Why |
|----------|-----|
| `bind_tools` failure → unconditional `EngineError`, not `_translate` | `_translate` classifies by reading exception TYPE NAMES. A binding error named like a transport failure would be reported as a degraded provider and swallowed by the fallback loop — walking the whole chain, printing `↳ fell back` three times, and ending on a generic failure that names nothing the user can fix. Pinned by `test_a_bind_tools_failure_is_never_reclassified_as_a_transport_error`. |
| The tool binding is not cached | The offered surface changes per leg — 04-03's wall withdraws it entirely — so a cached binding would serve one leg's moves to the next. `bind_tools` wraps the cached model rather than building a client, so re-binding per call costs no connection. |
| Empty `tools` short-circuits before `bind_tools` | The port says offering nothing must behave exactly like `stream`. Not "the same output" — the same *call*. `bind_tools([])` is precisely what Pitfall 3 describes historically breaking, and every no-peer user would be behind it. |
| The empty-parameters schema is built fresh per tool | A shared mutable module constant handed to two tools is one caller's edit away from rewriting another tool's declaration. |
| `_to_framework_tools` is the single place a tool's name and description are shaped | Both are steering text the model reads. PERS-05 requires the user to read the same bytes, and 04-05 renders exactly these specs. A second shaping site would make the inspector show something the model was never offered. |
| The A1 script drives the PAAF port, not the framework | A green result against `model.astream` directly would be evidence about langchain. Driving `stream_with_tools` / `last_tool_calls` makes it evidence about the thing that ships. |
| MESH-01 left `Pending` | 04-09 still carries it, and no live-provider mesh turn has been driven end to end yet — only the adapter half. Same reasoning 04-02 and 04-03 applied. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] The plan's own sync command fails on this workspace**

- **Found during:** Task 1, first command.
- **Issue:** every acceptance criterion opens with `uv sync --extra engine`, which exits 2: `Extra 'engine' is not defined in the optional-dependencies table for 'paaf-workspace'`. The extra lives on the `paaf-llm` member, not on the virtual workspace root. `.github/workflows/engine-adapter.yml:80` already documents this exact trap and uses the correct form.
- **Fix:** used `uv sync --all-packages --extra engine` throughout, matching CI. Nothing in the repo changed.
- **Verification:** `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` → 51 passed.

**2. [Rule 1 - Bug] The plan's two instructions for the `bind_tools` failure path contradict each other**

- **Found during:** Task 1, GREEN.
- **Issue:** the `<action>` says "route a `bind_tools` failure through `_translate` so it lands as `EngineError`", but `_translate` returns an `AdapterError` subclass whenever `classify()` recognises the exception. The `<behavior>` block states the contract unconditionally: "*A `bind_tools` failure surfaces as `EngineError`, not as any `AdapterError` subclass*". The two cannot both hold.
- **Fix:** implemented the behavior contract. `_bind_with_tools` raises `EngineError` directly, in `bind()`'s established shape and with `_scrub` on the path, and its docstring records why `_translate` was declined. Added `test_a_bind_tools_failure_is_never_reclassified_as_a_transport_error` as the negative control that distinguishes the two implementations — it injects an exception named `ConnectError` and asserts the raise is still not an `AdapterError`, while separately asserting that the same exception *would* classify as `ConnectionFailed`.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`, `packages/paaf-llm/tests/test_engine_adapter.py`
- **Verification:** falsification F2 below — substituting `raise self._translate(exc)` turns exactly that test red.
- **Committed in:** `6213d80`

**3. [Rule 2 - Missing critical functionality] Two docstrings understated what the class now is**

- **Found during:** Task 1, GREEN.
- **Issue:** the module docstring named only failure translation and the lazy import as the reasons the file exists, and the class docstring opened "A `ChatAdapter` backed by the real agent framework". Both became false the moment the adapter grew a tool surface — the same class of doc-drift 04-03 fixed in three places, and this file is the one place a reader goes to learn what may name a framework type.
- **Fix:** added a module-docstring paragraph stating that the tool vocabulary is confined here too and that nothing framework-shaped crosses in either direction, and rewrote the class docstring to state that it satisfies both protocols and why the tool binding is deliberately not cached.
- **Files modified:** `packages/paaf-llm/src/paaf_llm/_engine/__init__.py`
- **Committed in:** `6213d80`

---

**Total deviations:** 3 auto-fixed (1 blocking, 1 bug, 1 missing critical).
**Impact on plan:** none on scope. Deviation 2 is the only one that changed code the plan specified, and it resolves a genuine internal contradiction in favour of the stated contract, with a test that pins the choice.

### Out of Scope — Logged, Not Fixed

Three items in `.planning/phases/04-agent-mesh/deferred-items.md`:

- **Item 1 (widened).** Running `ruff` over `packages scripts` rather than over `paaf-llm` alone surfaces **25** files that would be reformatted at baseline (not 6), plus **one real pre-existing lint error** — `RUF022 __all__ is not sorted` in `paaf-core/secrets/__init__.py`, last touched by `960edbb` in Phase 2 and auto-fixable. `ci.yml` runs only `lint-imports`, so no `ruff` gate exists at all.
- **Item 3 (new).** `mypy` reports `agent.py:566: "ChatAdapter" has no attribute "stream_with_tools"` — the `isinstance` narrowing is lost through the `with_tools` local. Pre-existing (04-01 + 04-03), in a file outside this plan, and `_run_chain` is edited again by 04-06 and 04-07.
- **Item 4 (new).** The reasoning-model latency finding described under A1 above.

## Known Stubs

None introduced by this plan. Resolved from 04-01's and 04-03's stub lists: *"`LangChainAdapter` is still not a `ToolCallingChatAdapter`, so all of the above runs on the fake only"* — closed here.

Still open elsewhere, unchanged by this plan: the per-leg `runs` rows and `handoffs` writes (04-06), the per-agent prompt assembly (04-05), the per-agent `fallback_chain` (04-06), and the three unemitted `MeshSignalKind` members (04-07/04-08).

## Threat Mitigations Applied

| Threat | Disposition | Where |
|--------|-------------|-------|
| T-04-15 Information Disclosure (`bind_tools` error leaking a resolved key) | mitigated | `_bind_with_tools` puts `_scrub` on the new raise site; `test_a_resolved_key_never_appears_in_a_bind_tools_failure` asserts the secret is absent **and** that `***` is present, so a scrubber that dropped the message entirely would not pass. |
| T-04-16 Tampering (partial-JSON tool call from a mid-stream read) | mitigated | `_tool_calls_of` reads the summed aggregate only. Asserted against real chunks split mid-JSON, with the chunk-level read asserted to yield `{}` — so the test proves the failure is *silent*, which is what makes the guard necessary. Falsified (F4). |
| T-04-17 Spoofing (provider returns an unbound tool name) | mitigated by design | The adapter resolves nothing: it hands the raw `ToolCall` to `mesh.resolve_handoff`, which validates against `awake.peers` (04-01). No name check was added here, deliberately — a second authority would be a second thing to keep in step. |
| T-04-18 Tampering (framework `TextAccessor` crossing the port) | mitigated | The `str()` guard copied verbatim; asserted with `type(token) == str`, not `isinstance`, because `TextAccessor` is a `str` subclass and `isinstance` would pass. |
| T-04-19 Information Disclosure (live A1 check) | accepted | localhost only, no key, no cloud profile, not in CI, reads no secret. |
| T-04-SC Dependency surface | accepted | Zero packages installed. `pyproject.toml` unchanged (0 lines); the `[engine]` extra's exact pins are untouched. |

**Threat flags:** none. No new network endpoint, auth path, file access, or schema change. The one new outbound surface — tool names and descriptions leaving the box on a cloud profile — is the boundary the plan's threat model already declared, and `_to_framework_tools` is the single auditable place those bytes are shaped.

## Verification

| Gate | Result |
|------|--------|
| `uv sync --all-packages --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py -q` | **51 passed** (35 before this plan) |
| `uv run pytest -q` (workspace, extra installed) | **319 passed**, 0 skipped |
| `bash scripts/check_framework_uninstalled.sh` | **PASS** — 184 tests green in the clean venv; non-vacuity guard reports all 12 shipped test files, with `test_engine_adapter.py` still the one deliberate exclusion |
| `uv run lint-imports` | **3 contracts kept, 0 broken**; `.importlinter` unchanged (0 lines) |
| `git diff --stat -- .importlinter packages/paaf-llm/pyproject.toml` | **0** — no carve-out, no new force-include (no new test file was created) |
| `uv run ruff check packages/paaf-llm packages/paaf-trace scripts` | All checks passed |
| `uv run ruff format --check scripts/check_tool_streaming.py` | already formatted |
| `uv run python -c "...ast.parse('scripts/check_tool_streaming.py')..."` | exit 0 |
| SPDX + `NON-BLOCKING` header assertion | exit 0 |
| `uv run pytest -q --collect-only \| grep -c check_tool_streaming` | **0** — not collected |
| `grep -rn 'check_tool_streaming' .github/workflows/ \| wc -l` | **0** — wired into no CI job |
| `isinstance(LangChainAdapter(), ToolCallingChatAdapter)` one-liner | exit 0 |

### Non-Vacuity Checks (per the wave-1 finding)

Every `-k` filter was confirmed to select a nonzero number of tests before being reported.

| Command | Selected | Result |
|---------|----------|--------|
| `test_engine_adapter.py -k refuses_to_import_without_the_extra` | **1** of 51 | passed — the optional-extra negative control is intact |
| `test_engine_adapter.py -k tool_calling_chat_adapter` | **1** of 51 | passed |
| `test_engine_adapter.py -k bind_tools` | **5** of 51 | passed |
| `test_engine_adapter.py -k aggregate` | **2** of 51 | passed |

The plan prescribed no `-k` command that selects zero tests; its only `-k` criterion (`refuses_to_import_without_the_extra`) selects exactly one.

### Falsification — each guard was proved to bite

Four inversions applied out of band, each run against the full engine-adapter lane, each reverted immediately. Every one produced **exactly one** named red test, which is the shape that shows the assertion is specific rather than incidental.

| # | Inversion | Result |
|---|-----------|--------|
| F1 | Delete the `if not tools: return model` short-circuit | 1 failed — `test_offering_no_tools_never_calls_bind_tools` |
| F2 | Route `bind_tools` through `_translate` (the "consistent" choice) | 1 failed — `test_a_bind_tools_failure_is_never_reclassified_as_a_transport_error` |
| F3 | Emit `{}` for empty parameters instead of a schema object | 1 failed — `test_a_tool_with_no_parameters_still_declares_an_empty_schema_object` |
| F4 | Publish `_tool_calls_of(chunk)` instead of `_tool_calls_of(aggregate)` | 1 failed — `test_stream_with_tools_publishes_the_call_after_the_stream_drains` |

Tree restored and re-verified: **51 passed**, `git status --short -- packages scripts` empty.

### Phase invariants re-checked at commit time

1. **No `ALTER TABLE`, no new `runs` column** — `grep -rn "ALTER TABLE" packages/*/src` returns nothing; `packages/paaf-trace` untouched (0 lines).
2. **`force-include`** — no new test file created, so nothing to add; `packages/paaf-llm/pyproject.toml` unchanged (0 lines). `check_framework_uninstalled.sh`'s non-vacuity guard passes.
3. **`compose()` byte-exact** — `compose.py` unchanged (0 lines).
4. **`paaf prompt` default output** — verified with `xxd`: `You are Ada.`, 12 bytes, no trailing newline.
5. **No handoff tool call in `Agent.history`; `Role` not widened** — `agent.py` and `ports.py` untouched by this plan; `Role = Literal["system", "user", "assistant"]`, three members.
6. **`langchain*` confined to `paaf_llm._engine`** — `lint-imports` green with **no new carve-out**; `.importlinter` unchanged. This plan touched the one file permitted to name framework types and added no other importer.
7. **A1 gated nothing** — the script is outside `testpaths`, in no workflow, and exits 0 unconditionally. It was run, it confirmed, and no gate consulted it.

## Issues Encountered

The no-tools baseline in the A1 script measured 53.7 s to first token and once produced no text at all, which initially read as a streaming failure. Rather than record a guess, the cause was isolated by probing Ollama's HTTP API directly: 152 of 154 chunks carry `thinking`, one carries `content`. That turned an alarming number into a precise, actionable finding about reasoning models and the first-token budget, and confirmed it has nothing to do with A1.

## User Setup Required

None — no external service configuration. The A1 check needs a local Ollama with `qwen3.5:2b`; both were already present, and the script records "not run, and why" rather than failing if they are not.

## Next Phase Readiness

- **04-05** can render the same tool name and description bytes in `--provenance`, because `_to_framework_tools` is the only place they are shaped. It should also weigh finding 1 above: on both gate models a handoff arrives with no prose, so D-11's pre-handoff narration cannot be left to the model.
- **04-06 / 04-07** get a real adapter under the per-leg trace rows and the observer's grant tools.
- **04-09** can now drive a live-provider mesh turn end to end — the thing this plan existed to make possible.
- **Phase 9** should take deferred item 4 into the TTFA gate: calibrating a first-token budget on non-reasoning models alone would trip the fallback chain on a model that is working correctly.

## Self-Check: PASSED

- `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` — FOUND (`_to_framework_tools`, `stream_with_tools`, `_tool_calls_of`, `last_tool_calls`)
- `packages/paaf-llm/tests/test_engine_adapter.py` — FOUND (51 tests collected)
- `scripts/check_tool_streaming.py` — FOUND
- `.planning/phases/04-agent-mesh/deferred-items.md` — FOUND (items 3 and 4 added, item 1 widened)
- Commit `d483b36` — FOUND in `git log`
- Commit `6213d80` — FOUND in `git log`
- Commit `4b46e3d` — FOUND in `git log`

---
*Phase: 04-agent-mesh*
*Completed: 2026-08-07*
