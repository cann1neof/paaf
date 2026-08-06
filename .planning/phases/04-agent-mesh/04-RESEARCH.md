# Phase 4: Agent Mesh - Research

**Researched:** 2026-08-06
**Domain:** LLM-driven multi-agent handoff inside a hand-rolled, port-isolated turn loop (Python 3.12, pytest, no new dependencies)
**Confidence:** HIGH on the codebase seams and the required work; MEDIUM on the external multi-agent conventions; LOW on live provider behaviour under bound tools (one verification task recommended)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**The handoff signal (MESH-01/02)**

- **D-01:** Handoff is expressed as a **reserved tool call** the engine registers — `handoff(target)`
  or equivalent. Chosen over an in-stream sentinel because Phase 1 measured 30/30 well-formed tool
  calls on `qwen3.5`, and parsing prose for a magic line is fragile. This means Phase 4 grows a
  **minimal, mesh-private tool-call surface** on the port, one phase before the Phase-5 registry.
  That surface is **not** the tool registry and must not become it: the mesh exposes the handoff tool
  and the observer's grant, nothing else. Phase 5 builds the user-facing registry separately and may
  reuse the plumbing, but "handoff is not a registry entry" stays true.
- **D-02:** `TurnResult.handoff` (the always-`None` Phase-3 seam in `ports.py`) is what gets set. The
  port's shape must not otherwise change — no new method, no moved signature — because Phase 3
  deliberately declared this field so Phase 4 would not have to.

**The observer**

- **D-03:** A **small supervising model** judges every handoff attempt: was this agent invoked
  correctly. It is **ON by default** and occupies a **reserved name in the profile namespace** (e.g.
  a profile named `observer`), so it is configured exactly like any other profile — **deeply
  configurable, down to its system prompt**.
- **D-04:** The observer's **behavior is bounded by which mesh tools it is granted, not by a mode
  flag or a prompt instruction.** Grant it the retry tool and it can only bounce back; grant it the
  re-route tool and it can also redirect; grant both for hybrid. **Default grant = generic-retry
  only.** This is the same mechanism as the hop budget (D-08): capability removed, never instruction
  added. A model cannot talk its way past a tool it does not have.
- **D-05:** Two possible verdicts. **Generic retry** — the attempt is killed and bounced to the
  calling agent, which may try again or answer. **Self re-route** — if confident, the observer picks
  a different peer itself and **emits a signal that a correction occurred**, so the event is
  externally observable (the founder wants it usable as an endpoint — "light a flashlight"). It is
  therefore not only a trace row: the library needs an observable event surface for it, headless.
- **D-06:** The observer may **only re-route within the calling agent's declared peer graph**. One
  graph, one guard, no second privilege tier — an undeclared target from the observer is the same
  catchable MESH-02 error as one from an agent. Enabling the observer must never silently make every
  agent reachable from every agent.
- **D-07:** **No `observer` profile declared → the mesh runs unobserved and says so plainly**
  (startup line + trace). "On by default" means the slot is reserved and wired, not that PAAF invents
  a model to fill it. PAAF never picks a model on the user's behalf.

**Loop safety and turn shape (MESH-03)**

- **D-08:** **Both** guards, and they are different kinds. A **deterministic per-turn hop budget** is
  enforced by the engine — not by any model, not by the observer — and when it is exhausted the
  handoff tool is **withdrawn** so the turn cannot continue hopping. On top of that, the observer is
  shown the recent handoff history so it can recognize a loop and break it gracefully *before* the
  wall. The budget guarantees termination; the observer makes termination graceful.
- **D-09:** When the budget is exhausted, control goes to a **user-declared home agent** — a new
  mesh-level field (`default_agent` or similar) naming who speaks when the mesh cannot decide. It is
  a **third distinct concept**, deliberately not collapsed into the other two: `fallback_chain` is
  resilience, `peers` is handoff-on-the-merits, the home agent is the terminator. The user names it;
  PAAF does not guess.
- **D-10:** A handoff resolves **inside the same user turn** — one question in, one answer out, from
  whoever ended up awake — and it is **silent** in the reply stream. "Nothing hidden" is satisfied by
  the trace, the observable correction signal, and the inspector, not by narrating routing at the
  user. Making the user re-ask would also be unusable in Phase 9 voice.
- **D-11:** Prose an agent emits *before* calling handoff ("Let me get the cook for that…") is
  **user-configurable to keep or drop**. The design should **discourage** replies in that style via
  the explainer, but **Phase 4 does not mechanically enforce it**. Mechanical enforcement is a **v2
  item the founder marked as really important** — do not silently drop it.

**Constraints (MESH-06)**

- **D-12:** `constraints` stays **free text** — no closed vocabulary, no typed constraint fields.
  A structured constraint set would be a routing DSL by the back door, which D-08 (Phase 3) bans.
- **D-13:** The **observer enforces** constraints, and the founder's ruling is that **the observer
  counts as "the system"** for MESH-06 / SC#5's "enforced regardless of what the model attempts."
  This is coherent because the observer is on by default; the honest caveat is already carried by
  D-07's running-unobserved notice. **Do not re-open this** — the tradeoff was raised and decided.
  The one thing that is deterministic in all configurations, observed or not, is the **peer-graph
  guard** (MESH-02).
- **D-14:** Constraint checking is **handoff-time only** — one observer call per handoff *attempt*,
  never per turn. Reply/content-level constraint checking is v2 observer scope.
- **D-15:** The observer's **input window is user-configurable**. **Default: the last user message +
  the handoff decision + the agent's stated reasoning (if any).** Configurable to N last messages /
  N last logs / **N last handoffs** — the last option exists specifically so the observer can see it
  is inside a handoff loop. Note for the planner: a cloud `observer` profile with a wide window ships
  a lot of conversation off-box on every handoff; the endpoint declaration makes this visible, and
  the docs should say it.

**Context carry-across and the explainer (MESH-03/MESH-04)**

- **D-16:** A woken agent's context is a **three-layer salad**:
  1. **Long history** — reached via a *lookup tool*, **not built in Phase 4** (see Deferred). Design
     for its later arrival; do not implement it.
  2. **All messages in the current conversation** — in the prompt (this is the MESH-03 guarantee).
  3. **An assembled persona, tailored per agent**: system prompt + persona (how to talk to the user)
     + the peer/agent explainer for *this specific agent*.
- **D-17:** Layer 3 means prompt composition becomes **per-agent**. `compose.py` currently produces
  `base` + skill fragments against a single global `LlmConfig.base_prompt`; Phase 4 must let each
  agent contribute its own system-prompt/persona layer while the explainer is generated per agent
  from *its* manifest and *its* peer list. Whether that is a new `ModelProfile` field or a reshape of
  the global `base_prompt` is the planner's call — the requirement is that two agents can have
  genuinely different prompts.
- **D-18:** The explainer is a **default template, user-overridable** (globally and/or per agent).
  MESH-04's "generated from the manifest and peer graph" holds by default; the user can still rewrite
  it, consistent with the observer being configurable down to its system prompt. Either way it
  appears **verbatim** in the prompt inspector as its own labelled segment under `--provenance` —
  PERS-05 is unconditional.
- **D-19:** The inspector's **default output is unchanged** — the active agent's prompt, as in Phase
  3. A new **`paaf prompt --agent <name>`** aims it at any declared profile, **including the reserved
  observer**. Same philosophy as D-03 in Phase 3: the plain view stays authoritative and clean, the
  deeper view is one opt-in flag away. This flag is what makes SC#3 reachable for a peer that is not
  currently awake, and it is the only way to read the observer's prompt (the observer is never
  "awake").

### Claude's Discretion

- The exact shape of the mesh-private tool-call surface on the port, and how `HandoffRequest` is
  typed — subject to D-02 (the port's existing shape does not change).
- Trace schema for the handoff chain (MESH-05): whether handoffs are new columns on `runs`, a new
  `handoffs` table, or events — as long as "who was awake each turn, every handoff and its outcome,
  every observer verdict/correction, and whether a turn was served by a fallback" is all
  reconstructible, per-agent fallback chains included.
- The default hop-budget value, the default observer window sizes, and where the observable
  correction signal surfaces in the headless library API (callback / event stream / both).
- How awake-state is held across user turns and whether it survives a process restart (not
  discussed; MESH-03 implies sticky within a session, and Phase-3 history is ephemeral in-memory).
- Whether the per-agent system prompt is a new `ModelProfile` field or a reshape of `base_prompt`
  (D-17).

### Deferred Ideas (OUT OF SCOPE)

- **Observer beyond handoffs** — reply/content-level checking and other run-time supervision. The
  founder: *"it also may observe other stuff too, we can figure that one later, add it to v2."* →
  **v2**. Phase 4 is handoff-time only (D-14).
- **Mechanical enforcement that an agent produces no prose before calling handoff** → **v2**,
  explicitly flagged *"it's really important"* (D-11). Phase 4 discourages it in the explainer and
  makes keeping/dropping it a user setting.
- **Long-history lookup tool** (layer 1 of D-16) → needs the Phase-5 tool registry and v2 long-term
  memory. Phase 4 designs room for it and builds the current-conversation layer only.
- **Routing-quality / mis-route eval (ROUTE-01)** → **v2**, already deferred in Phase 3. Phase 4
  ships the trace-based observability that makes such an eval possible later.
- **Awake-state persistence across a process restart** — not discussed; noted as Claude's discretion
  above. Long-term conversational memory remains v2.

**Also out of scope (from `## Phase Boundary`):** the tool registry, MCP and permission tiers (Phase 5);
long-history lookup; observer duties beyond handoff; mechanical no-prose-before-handoff enforcement;
routing-quality eval; audio, barge-in and turn timing (Phase 9).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **MESH-01** | Routing between models is decided by the currently-awake model itself (LLM-driven handoff); there are no deterministic, user-written routing rules anywhere | § Pattern 1 (handoff-as-tool) + § Pattern 3 (generated explainer). The only deterministic logic is the *guard* and the *budget*, neither of which selects a target. `extra="forbid"` (already shipped) keeps a routing DSL out of the schema — § Anti-Pattern 1 |
| **MESH-02** | A model may hand off only to peers declared in its peer graph; a handoff to an undeclared peer is rejected and recorded, never silently followed | § Pattern 2 (belt-and-braces: per-peer tool surface *and* a runtime guard) + § Pitfall 4 (models hallucinate unbound tool names, so the guard is not theoretical) + § Finding 3 (error taxonomy slot) |
| **MESH-03** | A handoff transfers control and the full conversation context to the receiving agent, which becomes the awake agent until it hands off again — including handing back | § Finding 2 (PAAF's user/assistant-only history satisfies "full conversation" *and* dodges the dangling-tool-call trap) + § Pattern 4 (awake-state) + § Pitfall 1 |
| **MESH-04** | Each agent's handoff explainer is generated from its capability manifest and peer graph and is present verbatim in the composed-prompt inspector — no hidden instructions steer routing | § Finding 1 (**tool names and descriptions are steering text too and must be inspectable**) + § Pattern 3 + § Code Example 3 (extending `PromptComposer` without breaking its byte-exact invariant) |
| **MESH-05** | The trace records every handoff, which agent was awake each turn, and whether each turn was served by a fallback, so a wrong reroute is observable after the fact | § Finding 5 (one `runs` row per agent leg, correlated by an engine-generated `turn_id`; no FK, because the writer never surfaces `lastrowid`) + § Pitfall 5 (**the trace store has no migration mechanism**) |
| **MESH-06** | A user may declare optional hard constraints on an agent that the system enforces regardless of the model's choice | § Pattern 5 (observer-enforced per D-13, bounded by capability grant per D-04) + § Security Domain (the observer is itself an injection target) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These are directives, not preferences. Plans must comply and verification must check them.

| Directive | Source | Consequence for Phase 4 |
|-----------|--------|------------------------|
| **All `langchain*` imports confined to `paaf_llm._engine`, CI-enforced by import-linter** | §"The constraint that makes this decision cheap" | The mesh's tool-call surface must be expressed in **PAAF types**. The framework's tool-call representation (`bind_tools`, `AIMessageChunk.tool_call_chunks`, `ToolMessage`) never appears outside `_engine`. `.importlinter` already forbids 7 modules workspace-wide with `paaf_llm._engine` + `paaf_llm._engine.**` as the only carve-out — **no new carve-out may be added** [VERIFIED: `.importlinter` read this session] |
| **The public API must never leak the underlying agent framework's types** | §Constraints | `tests/test_no_leak.py` walks every public signature. New public types (`ToolSpec`, `ToolCall`, `HandoffRequest`, observer verdicts) must be PAAF dataclasses/Pydantic models and be added to `paaf_llm.__all__` deliberately [VERIFIED: `paaf_llm/__init__.py` read this session] |
| **Raw SQL + `aiosqlite` for the trace store; no ORM** | §"What NOT to Use" | MESH-05's schema change is hand-written SQL in `schema.sql` plus a dataclass with `as_sql()`. No SQLAlchemy, no migration library |
| **No accounts, no telemetry, no mandatory cloud; offline mode verifiable** | §Constraints, §Privacy | The observer is just another `ModelProfile`, so it inherits `Endpoint` declaration and Phase-10's offline refusal for free. A cloud observer with a wide window is an egress the user must be able to see — § Security Domain |
| **`ruff` for lint/format; `mypy` (or `ty`) for type checking; `uv` for packaging** | §Development Tools | Available and verified in this environment — § Environment Availability |
| **`pytest` 9.1.1 + `pytest-asyncio`; golden tests against a fake model, no hardware, CI-safe** | §Development Tools | Every mesh scenario is a `FakeAdapter` program. § Validation Architecture |
| **Pin the agent framework exactly, never a range** | `paaf-llm/pyproject.toml` (T-03-SC) | Phase 4 adds **no** new dependency, so no new pin is needed — § Package Legitimacy Audit |

**Project skills:** `.agents/skills/` contains `find-skills`, `frontend-design`, `startup-ideation`. None applies to a headless Python mesh phase; no skill-specific pattern constrains this work. No `rules/*.md` directory exists.

**GSD workflow enforcement** (from CLAUDE.md): file edits must go through a GSD command. This phase runs under `/gsd-execute-phase`, which satisfies it.

---

## Summary

Phase 4 is **almost entirely a PAAF-internal engineering problem, not a research problem.** Every
library it needs is already installed and pinned; the phase adds **zero new dependencies**. The
external ecosystem contributes exactly three things: a validation that handoff-as-a-tool is the
industry-standard shape (OpenAI Agents SDK, `langgraph-swarm`, LangChain's own multi-agent guide all
converge on `transfer_to_<agent>` tools), a well-documented failure mode PAAF must consciously
*avoid re-introducing* (the dangling tool-call message that returns HTTP 400 forever after), and a
loop-safety convention (a hard hop ceiling, typically 5–10) that D-08 already anticipated. The real
work is in the six seams Phase 3 deliberately left, and the honest reading is that **three of them
are larger than the CONTEXT implies.**

The three under-described items the planner must size correctly. **First, the port genuinely has no
tool-call surface at all** — `ChatAdapter` is two methods, `stream(profile, messages) ->
AsyncIterator[str]` and `last_usage() -> Usage`, and neither can carry a tool declaration in or a
tool call out. D-01 ("grow a minimal tool-call surface on the port") and D-02 ("no new method, no
moved signature") are in real tension; the resolution that satisfies both literally is a **second,
optional capability protocol** that extends `ChatAdapter` rather than editing it, which leaves the
Phase-3 port byte-identical. **Second, SC#4's "each agent applies its own fallback chain" is not
implementable today** — `fallback_chain` is a single global field on `LlmConfig`, not a per-profile
one; a new `ModelProfile.fallback_chain` (with `_check_refs` validation and a `reload_tier`) is
required work that CONTEXT mentions only in passing. **Third, `paaf-trace` has no migration
mechanism whatsoever** — the writer runs `executescript(read_schema())` with `CREATE TABLE IF NOT
EXISTS`, which silently will *not* add a column to an existing `runs` table, so any MESH-05 design
that adds columns breaks every user who already has a `trace.db`.

The sharpest finding is about PERS-05. **A tool's name and description are prompt text that steers
the model, and they are not in the system prompt.** If the handoff tools are named per peer and
carry each peer's capability manifest in their descriptions — which is the industry convention and
the ergonomically obvious choice — then a large amount of routing-steering text exists that
`paaf prompt` does not currently show. MESH-04 says the explainer must be "present verbatim in the
composed-prompt inspector" and PERS-05 says PAAF "never injects instructions the user did not write
and cannot see." Both are violated unless the inspector is extended to render the **bound mesh tool
surface** alongside the composed prompt segments. This is not an optional nicety; it is the phase's
PERS-05 enforcement point, exactly as `compose.py` was Phase 3's.

**Primary recommendation:** add an optional `ToolCallingChatAdapter` capability protocol beside the
untouched `ChatAdapter`; emit one `transfer_to_<peer>` tool per declared peer (capability removal,
the mesh house style) **and** keep a deterministic runtime guard because models hallucinate tool
names that were never bound; never let a handoff tool call enter `Agent.history`; record one `runs`
row per agent leg correlated by an engine-generated `turn_id` with a separate FK-free `handoffs`
table; and extend `paaf prompt --agent <name>` to print the tool surface as labelled provenance
segments so no routing-steering byte is invisible.

## Key Findings

Five findings drive the plan. Each is cross-referenced from the requirements table above.

### Finding 1 — Tool names and descriptions are steering text, and `paaf prompt` does not show them *(PERS-05 / MESH-04)*

A tool's `name` and `description` are sent to the model and shape its behaviour, but they are **not
part of the system prompt**. Today `paaf prompt` renders only `PromptComposer` segments
[VERIFIED: `cli.py`, read this session]. The moment the mesh binds `transfer_to_chef("handles
cooking, recipes, and the kitchen timers")`, PAAF is injecting behaviour-steering text the user
cannot see — which MESH-04 ("present verbatim in the composed-prompt inspector") and PERS-05 ("never
injects instructions the user did not write and cannot see") both forbid.

**Consequence:** the inspector must render the **bound mesh tool surface**, not just prompt segments.
This is Phase 4's PERS-05 enforcement point exactly as `compose.py` was Phase 3's, and it should be
made mechanical by a test asserting every offered tool name and description appears in
`--provenance` output. See § Pattern 3 and § Open Question 3 for the default-output question.

### Finding 2 — PAAF's message model makes the classic handoff bug unrepresentable, and that must be preserved deliberately *(MESH-03)*

`Role` is `Literal["system","user","assistant"]` and `Message` is `(role, content)` — no `tool` role,
no `tool_call_id` [VERIFIED: `ports.py`]. The industry-standard handoff bug (§ Pitfall 1) cannot
occur in `Agent.history` by construction. Simultaneously, LangChain's own caution against carrying a
sub-agent's internal reasoning across a handoff is satisfied for free, because PAAF's history holds
only the clean user-facing transcript. **Both properties are accidental gifts of the Phase-3 design
and are easy to destroy** — by widening `Role`, by persisting the handoff tool call, or by reusing a
framework message list across legs. State the rule and test it.

### Finding 3 — The port has no tool-call surface at all, and D-01 vs D-02 needs an explicit resolution

`ChatAdapter` is exactly two methods: `stream(profile, messages) -> AsyncIterator[str]` and
`last_usage() -> Usage` [VERIFIED: `ports.py`]. Neither can carry a tool declaration in or a tool call
out. D-01 requires growing a tool-call surface; D-02 forbids changing the port's shape.

**Resolution that satisfies both literally:** add a **second protocol** —
`ToolCallingChatAdapter(ChatAdapter, Protocol)` — leaving the Phase-3 `ChatAdapter` definition
byte-identical, and feature-detect with `isinstance`. The alternative (a keyword-only `tools=()`
parameter on `stream`) is backward-compatible for *callers* but does edit the port. Both require
touching `FakeAdapter` and `LangChainAdapter`. See § Code Example 1 and § Pattern 2 for the paired
error-taxonomy decision (`UndeclaredPeer` is neither an `AdapterError` nor an `EngineError`).

### Finding 4 — SC#4's per-agent fallback chain does not exist yet

`fallback_chain` is a single **global** field on `LlmConfig`, not a per-profile one
[VERIFIED: `profiles.py`]. SC#4 requires "each agent applies its own fallback chain", and CONTEXT's
integration notes say fallback is "per-agent, nested inside the handoff loop, not global to the
turn." This is required schema work — a new `ModelProfile.fallback_chain` with `reload_tier`
metadata and `_check_refs` validation — that CONTEXT mentions only in passing. `Agent._chain()`
currently builds `[active_profile, *config.fallback_chain]` and must become per-awake-agent.

### Finding 5 — Correlate trace rows with a generated `turn_id`, never `lastrowid`, and prefer new tables over new columns *(MESH-05)*

`schema.sql` documents that `fallback_trail` was denormalized onto `runs` specifically because "the
fire-and-forget writer never surfaces `lastrowid`, so an FK child would force a writer redesign"
[VERIFIED: `schema.sql`]. That constraint still binds. An engine-generated `uuid4` `turn_id` sidesteps
it entirely.

**Recommended shape:** one `runs` row **per agent leg** (so `served_by` + `fallback_trail` deliver
SC#4's per-agent fallback provenance with no new mechanism), plus an FK-free `handoffs` table for
attempts, verdicts and corrections — including *rejected* attempts, which produce no `runs` row and
would otherwise be invisible. **Prefer new tables to new columns**, because the store has no
migration mechanism at all (§ Pitfall 5).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deciding *whether* and *where* to hand off (MESH-01) | **Model (LLM)** | — | The founding constraint. No PAAF code may select a target; PAAF only offers the choice and validates the answer |
| Declaring the peer graph, manifests, constraints, home agent | **Config schema** (`profiles.py`) | — | User-owned YAML, validate-on-read, `extra="forbid"`. Already the home of `peers`/`capabilities`/`constraints` |
| Enforcing the peer-graph guard (MESH-02) | **Engine** (`agent.py`) | Adapter (shapes the tool surface) | Must be deterministic in *all* configurations — D-13 names this as the one guarantee that holds unobserved |
| Enforcing the hop budget + withdrawing the handoff tool (D-08) | **Engine** | — | "Not by any model, not by the observer." Capability removal, not instruction |
| Judging handoff quality + enforcing free-text constraints (MESH-06) | **Observer (LLM)** | Engine (bounds it by tool grant) | D-13: the observer counts as "the system"; D-04: its powers are its tool grant |
| Translating PAAF `ToolSpec` ⇄ framework tool format, and framework tool calls ⇄ PAAF `ToolCall` | **Adapter** (`_engine/`) | — | The one permitted `langchain*` site. This is the entire reason the adapter exists |
| Scripting handoff scenarios deterministically | **`FakeAdapter`** | — | SC#5: the whole mesh must run with the framework uninstalled |
| Per-agent prompt assembly + explainer generation (MESH-04) | **Composer** (`compose.py`) | CLI (renders provenance) | Phase 3 established `compose.py` as the single derivation; a second derivation would let the inspector lie |
| Showing every steering byte to the user (PERS-05) | **CLI inspector** (`cli.py`) | Composer | The enforcement point. Must now cover the tool surface, not just prompt segments |
| Recording the handoff chain (MESH-05) | **`paaf-trace`** | Engine (emits) | Existing single-writer queue, off the hot path |
| Surfacing the observer-correction signal (D-05) | **`paaf-llm` public API** (callback/event) | Trace | "Usable as an endpoint" — Phase 10's WebSocket channel consumes it later. Must be headless |

**Boundary that must not move:** the mesh loop lives in `paaf-llm`, not `paaf-session`
(ROADMAP §"Notes on Structure"), and `paaf_voice`/`paaf_llm` independence is import-linter-enforced.

## Standard Stack

### Core

**Phase 4 introduces no new library.** Every table row below is already installed, pinned, and in use.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.13 | Runtime | Pinned by every `pyproject.toml` (`requires-python = ">=3.12"`) [VERIFIED: `python3 --version`, this session] |
| `pydantic` | 2.13+ | New mesh config fields (`ModelProfile.fallback_chain`, `system_prompt`, `LlmConfig.default_agent`, hop budget, observer window) | Already the schema layer; `extra="forbid"` + `model_validator` are the established validate-on-read pattern [VERIFIED: `packages/paaf-llm/pyproject.toml`] |
| `aiosqlite` | 0.22+ | MESH-05 trace rows | Already the trace store's only dependency; raw SQL, no ORM (CLAUDE.md) [VERIFIED: `paaf_trace/store.py`] |
| `click` | 8.4+ | `paaf prompt --agent <name>` (D-19) | The CLI is already Click; adding an option is one decorator [VERIFIED: `paaf_llm/cli.py`] |
| `rich` | 15+ | Rendering the mesh tool surface / handoff notices | Already used by `render_profiles` and `_print_fallback_trail` [VERIFIED: `paaf_llm/cli.py`] |
| stdlib `uuid` | — | `turn_id` correlation key for the handoff chain | Avoids the `lastrowid` problem entirely — see § Finding 5 |
| stdlib `json` | — | Serializing the handoff chain into TEXT columns | Exactly how `fallback_trail` already works [VERIFIED: `agent.py:_drain`] |

### Supporting (already pinned, only exercised behind the `[engine]` extra)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langchain` | 1.3.14 (exact pin) | `bind_tools` on the real adapter | Only inside `paaf_llm._engine` [VERIFIED: `uv.lock` + `pyproject.toml`, this session] |
| `langchain-core` | 1.5.3 | `AIMessageChunk` aggregation → `.tool_calls` | Only inside `_engine`; the aggregation pattern already exists there for `usage_metadata` [VERIFIED: `uv.lock`] |
| `langchain-ollama` | 1.1.0 (exact pin) | Local tool-calling profiles | The version that matters for the streaming-with-tools risk — see § Pitfall 3 [VERIFIED: `uv.lock`] |
| `langgraph` | 1.2.10 | Pinned, **not used by the mesh loop** | PAAF hand-rolls the loop by design (`agent.py` docstring). Do not pull LangGraph in for handoff — see § Don't Hand-Roll's inverse note |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled handoff loop in `agent.py` | `langgraph-swarm` / LangGraph `Command(goto=...)` | **Rejected.** It would put routing behind the framework boundary, break SC#5 (the mesh must run framework-uninstalled), and forfeit per-hop provenance — the identical reasoning `agent.py`'s docstring already gives for hand-rolling the fallback chain. It is still worth reading as a *reference implementation* — § Pattern 1 |
| Per-peer `transfer_to_<peer>` tools | A single `handoff(target: str)` with an enum-constrained `target` | Single-tool keeps the trace and explainer simpler and makes the guard trivially testable, but forfeits capability removal: the model can emit any string. **Recommendation: per-peer tools + the runtime guard anyway** — § Pattern 2 |
| A capability protocol beside `ChatAdapter` | A keyword-only `tools=()` parameter added to `ChatAdapter.stream` | The keyword param is backward-compatible for callers but *does* edit the Phase-3 port, which D-02 forbids. Both require touching `FakeAdapter` and `LangChainAdapter` — § Finding 3 |
| Free-text `constraints` enforced by the observer | Typed/structured constraint fields checked deterministically | **Locked shut by D-12/D-13.** A structured constraint set is a routing DSL by the back door, which Phase-3 D-08 bans. Do not re-open |

**Installation:**

```bash
# Nothing to install. Phase 4 adds no dependency.
uv sync                      # framework-free workspace (the SC#5 substrate)
uv sync --extra engine       # only for the engine-adapter CI job
```

**Version verification:** performed against the repo's own lockfile rather than PyPI latest, because
`paaf-llm` pins the framework **exactly** (T-03-SC supply-chain rule) and the planned versions are
the pinned ones, not the newest ones: `langchain==1.3.14`, `langgraph==1.2.10`,
`langchain-ollama==1.1.0`, `langchain-anthropic==1.4.8`, `langchain-openai==1.4.1`
[VERIFIED: `uv.lock` + `packages/paaf-llm/pyproject.toml`, read this session]. **No version bump is
required or recommended for this phase** — a bump would be an unreviewed supply-chain change riding
along inside a feature phase.

## Package Legitimacy Audit

**This phase installs no external packages.** The mesh is implemented entirely in PAAF source using
already-pinned dependencies plus the standard library (`uuid`, `json`, `asyncio`).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none — no new dependency)* | — | — | — | — | — | — |

**Packages removed due to [SLOP] verdict:** none — none were proposed.
**Packages flagged as suspicious [SUS]:** none — none were proposed.

**Planner note:** if a plan proposes *any* new dependency (a tool-schema helper, a JSON-Schema
builder, a graph library), that is a signal the design has drifted. `pydantic` already produces JSON
Schema via `model_json_schema()`, and the tool surface is a handful of dicts. Treat a new dependency
in this phase as a design smell requiring justification, and if one is genuinely needed, run
`gsd-tools query package-legitimacy check --ecosystem pypi <pkg>` and pin it exactly, matching the
`[engine]` extra's documented pinning rationale.

## Architecture Patterns

### System Architecture Diagram

```
                          ┌──────────────────────────────────────┐
   user_text ────────────▶│  Agent.turn()   (one user turn)      │
                          │  MESH-03: one question in,           │
                          │  one answer out (D-10)               │
                          └───────────────┬──────────────────────┘
                                          │
                     ┌────────────────────▼─────────────────────┐
                     │  awake = awake_agent  (sticky, D-19)     │◀──────────┐
                     │  hops_left = hop_budget (D-08)           │           │
                     └────────────────────┬─────────────────────┘           │
                                          │                                 │
                     ┌────────────────────▼─────────────────────┐           │
                     │  PER-AGENT PROMPT ASSEMBLY (D-16/D-17)   │           │
                     │  base + persona + skills + EXPLAINER     │           │
                     │  generated from awake.capabilities and   │           │
                     │  awake.peers               (MESH-04)     │           │
                     └────────────────────┬─────────────────────┘           │
                                          │                                 │
                     ┌────────────────────▼─────────────────────┐           │
                     │  MESH TOOL SURFACE (D-01, capability     │           │
                     │  removal): one transfer_to_<peer> tool   │           │
                     │  per declared peer.                      │           │
                     │  hops_left == 0  ⟹  surface is EMPTY     │           │
                     └────────────────────┬─────────────────────┘           │
                                          │                                 │
    ┌─────────────────────────────────────▼─────────────────────────────┐   │
    │  PER-AGENT FALLBACK CHAIN (SC#4) — nested INSIDE the mesh loop    │   │
    │  [awake, *awake.fallback_chain] → first-token deadline → commit   │   │
    │        ChatAdapter.stream(...)  ─┬─▶ tokens (buffered)            │   │
    │        + ToolCallingChatAdapter  └─▶ last_tool_calls()            │   │
    └─────────────────────────────────────┬─────────────────────────────┘   │
                                          │                                 │
                        ┌─────────────────▼──────────────────┐              │
                        │  did the leg emit a handoff call?  │              │
                        └───┬────────────────────────────┬───┘              │
                         no │                            │ yes              │
                            ▼                            ▼                  │
              ┌──────────────────────┐   ┌────────────────────────────────┐ │
              │ REPLY — this agent   │   │ PEER-GRAPH GUARD (MESH-02)     │ │
              │ answers. Turn ends.  │   │ target ∈ awake.peers ?         │ │
              └──────────┬───────────┘   └────┬──────────────────────┬────┘ │
                         │                 no │                  yes │      │
                         │                    ▼                      ▼      │
                         │        ┌───────────────────┐  ┌────────────────┐ │
                         │        │ UndeclaredPeer    │  │ OBSERVER       │ │
                         │        │ — catchable error,│  │ (if declared)  │ │
                         │        │   recorded, never │  │ D-03/D-13      │ │
                         │        │   followed        │  │ window: D-15   │ │
                         │        └─────────┬─────────┘  └───┬────────┬───┘ │
                         │                  │        approve │        │ veto/
                         │                  │                │        │ re-route
                         │                  │                ▼        ▼      │
                         │                  │        ┌──────────────────────┐│
                         │                  │        │ hops_left -= 1       ││
                         │                  │        │ awake = target       ││
                         │                  │        │ (re-route target ALSO││
                         │                  │        │  passes the guard,   ││
                         │                  │        │  D-06)               ││
                         │                  │        └──────────┬───────────┘│
                         │                  │                   └────────────┘
                         │                  │                   (loop back up)
                         ▼                  ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │  TRACE DRAIN (MESH-05) — fire-and-forget, off the hot path         │
    │  one runs row PER LEG (served_by + fallback_trail, SC#4)           │
    │  + handoff rows: attempt, target, verdict, correction              │
    │  correlated by engine-generated turn_id (no FK — see Finding 5)    │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │
                    ┌────────────▼─────────────┐        ┌──────────────────┐
                    │ TurnResult(text,         │        │ CORRECTION SIGNAL│
                    │   served_by, usage,      │        │ (D-05) — headless│
                    │   fallback_trail,        │        │ observable event │
                    │   handoff=HandoffRequest)│        │ "light a         │
                    └──────────────────────────┘        │  flashlight"     │
                                                        └──────────────────┘

    SIDE CHANNEL (never on the turn path):
      paaf prompt --agent <name>  ──▶  composed segments  +  MESH TOOL SURFACE
                                       (PERS-05: every steering byte visible)
```

**Two flows deliberately absent from the diagram**, because they must not exist: there is no
rule-evaluation box (MESH-01 — nothing but the model picks a target), and there is no path by which
the observer reaches a target outside the calling agent's peer graph (D-06 — one graph, one guard).

### Recommended Project Structure

Additive, following Phase-3 placement precedent. No file is moved.

```
packages/paaf-llm/src/paaf_llm/
├── ports.py           # + ToolSpec, ToolCall, HandoffRequest, ToolCallingChatAdapter,
│                      #   UndeclaredPeer error.  ChatAdapter itself UNCHANGED (D-02)
├── profiles.py        # + ModelProfile.fallback_chain / .system_prompt / .persona
│                      # + LlmConfig.default_agent / .hop_budget / observer settings
│                      # + _check_refs: default_agent resolves, observer name reserved
├── mesh.py            # NEW — explainer generation, tool-surface construction,
│                      #   the peer-graph guard, hop-budget bookkeeping. Pure + stdlib.
├── observer.py        # NEW — the supervising-model call, its verdict types,
│                      #   its capability grant. May be folded into mesh.py.
├── compose.py         # + an ordered mesh-segment parameter; byte-exact join invariant kept
├── agent.py           # the handoff loop wraps _run_chain; awake-state; trace drain
├── fake/__init__.py   # + scripted tool calls, + recording the offered tool surface
├── cli.py             # + `paaf prompt --agent <name>`; renders the tool surface
└── _engine/__init__.py# + bind_tools translation; chunk aggregation -> PAAF ToolCall

packages/paaf-trace/src/paaf_trace/
├── schema.sql         # + handoffs table (+ turn_id).  See Pitfall 5 on migration.
└── store.py           # + HandoffEvent dataclass with as_sql()
```

### Pattern 1: Handoff as a tool call — the industry-converged shape

**What:** the receiving agent is selected by the model *calling a tool*, not by emitting a parseable
sentinel in prose. Three independent implementations converged on this, which is strong evidence
D-01 is right.

**When to use:** always, here. D-01 is locked, and Phase 1's 30/30 well-formed tool calls on
`qwen3.5` is the local measurement that makes it safe.

- **OpenAI Agents SDK**: a handoff to an agent named "Refund Agent" becomes a tool called
  `transfer_to_refund_agent`; the convention is `transfer_to_<agent_name>`, overridable via
  `tool_name_override`. By default the receiving agent sees the entire previous conversation history
  [CITED: openai.github.io/openai-agents-python/handoffs/]
- **`langgraph-swarm`**: `create_handoff_tool(agent_name=...)` produces `transfer_to_<agent_name>`
  by default [CITED: reference.langchain.com/python/langgraph-swarm/handoff/create_handoff_tool]
- **LangChain multi-agent guide**: handoff tools update an `active_agent` state variable that
  "persists across turns, and the system reads this variable to adjust behavior"
  [CITED: docs.langchain.com/oss/python/langchain/multi-agent/handoffs]

**The one thing PAAF must NOT copy:** all three carry the tool-call message into the receiving
agent's history and therefore must synthesize a `ToolMessage` to close the request/response cycle.
PAAF's `Message` type cannot represent a tool message at all, and that is a feature — see
§ Finding 2 and § Pitfall 1.

### Pattern 2: Belt-and-braces peer enforcement (capability removal **plus** a runtime guard)

**What:** shape the tool surface so that only declared peers are *offerable* (capability removal —
the mesh's established house style per D-04/D-08), **and** keep a deterministic guard that rejects a
handoff to any target not in `awake.peers`.

**Why both, when the first seems sufficient:** because a model can emit a tool call for a tool that
was never bound. That is a documented, routine LLM failure mode, not a hypothetical. If PAAF relied
on the tool surface alone, MESH-02's requirement that an undeclared handoff be "rejected as a
catchable error rather than silently followed" would depend on the provider never hallucinating —
and a check that cannot fail (or that fires only when a third party misbehaves) is exactly what the
project's negative-control discipline forbids.

**Why this makes the guard *testable*:** `FakeAdapter` can script a tool call naming a target the
engine never offered. That is the negative control for MESH-02, and it is unreachable if the guard
does not exist as a distinct code path.

**Error taxonomy placement (do this deliberately, not accidentally — CONTEXT names this explicitly):**
`ports.py` already partitions failure into three meanings, documented at length:

- `AdapterError` (4 subclasses) = *"try the next profile"* — consumed by the fallback loop
- `AllProvidersFailed` = *"there is no next profile"* — terminal, pointedly not an `AdapterError`
- `EngineError` = *"the user must fix something; more models will not help"*

An undeclared-peer handoff is **none of these**. It is not a degraded provider (so not
`AdapterError` — subclassing it there would let the fallback loop swallow a routing violation as one
more plausible hop, printing `↳ fell back to cloud (connection)` at a routing bug), and it is not
necessarily a config error (`_check_refs` already guarantees the *graph* is integral; this is the
model naming something outside it). **Recommendation: a new sibling exception, e.g.
`UndeclaredPeer(Exception)`, defined in `ports.py`** — placed there for the same load-bearing reason
`EngineError` is: the framework-free CLI must be able to name it in an `except` clause.

### Pattern 3: The explainer as a labelled prompt segment — and the tool surface as its twin

**What:** MESH-04's explainer is generated per agent from that agent's `capabilities` and `peers`,
appended as a `Segment` with its own `source` label, and rendered by `--provenance`.

`compose.py` is already shaped for this and needs no reshape of its philosophy — only an additional
ordered input. Its invariant, asserted by `tests/test_compose.py`, is that
`compose(...) == SEGMENT_SEPARATOR.join(s.text for s in segments(...))`. **That invariant must
survive Phase 4**, and the existing test that splits the output back apart and demands it equal
`[base, *fragments]` must be widened to `[base, *fragments, explainer]` rather than deleted.

**Per-agent base prompt (D-17).** `PromptComposer.compose(base_prompt, fragments)` is a pure function
that takes the base prompt as an *argument* — it never reads `LlmConfig`. So per-agent composition
requires **no change to `compose.py`'s signature philosophy at all**; only `Agent.system_prompt()`,
which currently hardcodes `self._config.base_prompt`, needs to resolve the prompt for the awake
agent. **Recommendation: additive `ModelProfile.system_prompt: str | None` and
`ModelProfile.persona: str | None` (both `ReloadTier.WARM`), falling back to the global
`LlmConfig.base_prompt` when `None`.** This satisfies D-17's "two agents can have genuinely
different prompts" with zero breakage, keeps `base_prompt` meaningful as the shared base, and follows
the established `Field(..., json_schema_extra={"reload_tier": ...})` pattern that every existing
field carries.

**The twin — and the phase's PERS-05 enforcement point.** See § Finding 1. Tool names and
descriptions steer the model and are not in the system prompt. `paaf prompt --agent <name>` must
render them.

### Pattern 4: Awake-state, and where "full conversation" actually lives

`Agent.history` is `list[Message]` of user/assistant turns only, appended after a successful turn,
and the system message is composed fresh every turn so a live config edit takes effect (WARM).
Handoff therefore needs **no history surgery**: the receiving agent's leg is a fresh
`[Message("system", <its own composed prompt>), *self.history, Message("user", user_text)]`.

That single line is simultaneously MESH-03's guarantee (the receiving agent gets the full prior
conversation), the hand-back guarantee (A→B→A works because history is shared, not per-agent), and
the reason PAAF sidesteps the dangling-tool-call trap (§ Pitfall 1).

**Awake-state (Claude's discretion).** `awake_agent` is instance state on `Agent`, initialized to
`config.active_profile`, updated on an accepted handoff, and **sticky across user turns** —
MESH-03's "becomes the awake agent until it hands off again" reads naturally as sticky, and the
LangChain guide's `active_agent` state variable "persists across turns"
[CITED: docs.langchain.com/oss/python/langchain/multi-agent/handoffs]. **Recommendation: sticky
within the process, not persisted across restart** — Phase-3 history is already ephemeral in-memory
(D-01), so persisting awake-state alone would produce the incoherent state of "agent B is awake but
remembers nothing", and long-term memory is explicitly v2.

### Pattern 5: The observer as a bounded, ordinary profile

The observer being "just another `ModelProfile`" buys four things for free, and the plan should
state that it is relying on them: `Endpoint` declaration (and therefore Phase-10's offline refusal),
`ReloadTier` metadata, `extra="forbid"`, and secret-by-reference (`api_key_ref`).

Its powers come only from its tool grant (D-04): default = generic-retry only. **The grant must be
config, and its default must be enforced by the tool surface, not by prompt text** — a model cannot
talk its way past a tool it does not have.

**New validation `_check_refs` must gain** (all are load-bearing, none exists today):

1. `default_agent`, if declared, resolves to a declared profile (D-09)
2. The reserved `observer` name does not appear in any profile's `peers` — the observer is never
   awake and must not be a handoff target
3. `observer` is not `active_profile` and not in any `fallback_chain`
4. `ModelProfile.fallback_chain` entries resolve, and (per the existing self-peer precedent) a
   profile does not list itself in its own fallback chain

### Anti-Patterns to Avoid

- **A deterministic routing rule anywhere.** Banned by MESH-01 and Phase-3 D-08. Concretely: no
  keyword matching on the user's text, no scoring of `capabilities` strings, no "if the manifest
  contains X". The existing negative control is `test_unknown_config_key_is_rejected` using a
  plausible `routing_rules` key — that test's spirit must extend to the new mesh fields.
- **Collapsing `fallback_chain`, `peers`, and `default_agent`.** `LlmConfig`'s docstring already
  explains why the first two are separate ("collapsing them would quietly make every fallback target
  a handoff target"). D-09's home agent is the third such concept. Three fields, three meanings.
- **Letting the mesh tool surface become the tool registry.** D-01 is explicit. Phase 5 builds the
  user-facing registry; the mesh exposes handoff tools and the observer's grant, nothing else. A
  `ToolSpec` type is fine and will be reused; a *registry*, a decorator, or permission tiers in
  Phase 4 is scope creep.
- **Repairing a malformed mesh declaration.** `profiles.py`'s validate-on-read-never-repair rule:
  report the offending value, never normalize it into something plausible.
- **Narrating the handoff at the user.** D-10 — handoff is silent in the reply stream. Do not copy
  `_print_fallback_trail`'s `↳ fell back to …` shape for handoffs; CONTEXT records that this was
  considered and declined.
- **Adding an import-linter carve-out.** If the mesh needs a `langchain` symbol outside `_engine`,
  the design is wrong. The whitelist stays at exactly `paaf_llm._engine` + `paaf_llm._engine.**`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detecting the model's handoff intent | A regex/sentinel parser over the reply stream | Native tool calling via `bind_tools`, aggregated to `.tool_calls` | D-01, decided on Phase 1's 30/30 measurement. Prose parsing breaks on paraphrase, translation, and the multilingual code-switching this project is built around |
| Streaming chunk → parsed tool call | A hand-written incremental JSON parser over `tool_call_chunks` | Aggregate `AIMessageChunk` objects (`agg = agg + chunk`) and read `.tool_calls` off the aggregate | The framework already does the partial-JSON reassembly. `_engine` **already uses this exact aggregation** for `usage_metadata` (`_usage_of(aggregate)`), so `last_tool_calls()` is a two-line addition on a proven path [CITED: docs.langchain.com/oss/python/langchain/streaming] |
| JSON Schema for a tool's parameters | Hand-written schema dicts scattered in strings | `pydantic`'s `model_json_schema()`, or a single small `ToolSpec.parameters` dict built in one place in `mesh.py` | `pydantic` is already a dependency; a schema built in one place is auditable, which matters because it is user-visible steering text |
| Correlating a run row with its child rows | Reading `lastrowid` after insert | An engine-generated `uuid4` `turn_id` | `paaf-trace`'s writer is fire-and-forget and **never surfaces `lastrowid`** — `schema.sql` documents this as the reason `fallback_trail` was denormalized onto `runs` rather than given an FK child table. A UUID sidesteps a writer redesign |
| Ordered per-agent resilience | A new fallback mechanism for the mesh | The existing `_run_chain`, called once per agent leg | SC#4 nests fallback *inside* handoff. `_run_chain` already does ordered chain + first-token deadline + reason classification + provenance |
| Loop termination | Trusting the observer, or a prompt instruction | A deterministic engine-side hop budget that **withdraws the tool** | D-08. Industry guidance is the same: hard budget caps, and "when any cap is hit, the agent must STOP or ESCALATE — never continue" [ASSUMED — synthesized from practitioner sources, not an authoritative spec] |

**Key insight:** the *inverse* also holds here, and it is unusual. The obvious "don't hand-roll"
candidate — the multi-agent loop itself — is precisely what PAAF **must** hand-roll. `langgraph-swarm`
and `create_swarm` implement this exact feature, and adopting them would fail SC#5 outright (the
mesh must run with the framework uninstalled), put routing behind the swappable boundary, and lose
per-hop provenance. `agent.py`'s docstring already argues this for the fallback chain; the same three
reasons apply verbatim to handoff. Read `langgraph-swarm` as a reference implementation, import
nothing from it.

## Runtime State Inventory

*Not applicable — Phase 4 is additive greenfield inside an existing package, not a rename, refactor,
or migration.* No string is being renamed and no identifier is changing meaning.

**One adjacent item that behaves like migration state and is easy to miss:** an existing developer
`trace.db` created by Phase 3 will **not** pick up new columns on `runs`, because the store applies
its schema with `CREATE TABLE IF NOT EXISTS` and there is no version table or `ALTER TABLE` path.
This is not repo state — it is on-disk state on every machine that has run `paaf chat` — and it is
treated as a first-class pitfall in § Pitfall 5.

## Common Pitfalls

### Pitfall 1: The dangling tool-call message (the classic handoff killer)

**What goes wrong:** an agent emits an assistant message containing `tool_calls`, control transfers,
and that message stays in the shared conversation history with no tool message answering its
`tool_call_id`. Every subsequent request to an OpenAI-compatible provider then fails with HTTP 400 —
*"An assistant message with 'tool_calls' must be followed by tool messages responding to each
'tool_call_id'"* — and it keeps failing, because the poison is in the history, not the request.

**Why it happens:** it is the natural implementation. Frameworks carry the tool-call message across
the handoff so the receiving agent can see *why* it was called, and then must remember to synthesize
a `ToolMessage`. LangChain's own guide is explicit that this is required: *"When an LLM calls a tool,
it expects a response. The `ToolMessage` with matching `tool_call_id` completes this request-response
cycle — without it, the conversation history becomes malformed."*
[CITED: docs.langchain.com/oss/python/langchain/multi-agent/handoffs]

**How PAAF avoids it — and the one way a plan could re-introduce it.** PAAF's `Role` is
`Literal["system", "user", "assistant"]` and `Message` is `(role, content)` with no `tool_call_id`
field, so a dangling tool call is **structurally unrepresentable in `Agent.history`**
[VERIFIED: `ports.py`, read this session]. The receiving agent's leg is a *fresh* message list built
from PAAF `Message` values, and `_engine._to_framework_messages` constructs framework messages anew
on every `stream()` call — so nothing survives between legs. The rule that must be written down and
tested: **the handoff tool call is never appended to `Agent.history`, and no leg reuses another
leg's framework message list.** A plan that "preserves the handoff message so the next agent
understands the transfer" walks straight into this.

**Warning signs:** any proposal to widen `Role` with `"tool"`; any proposal to carry framework
messages between legs; a 400 that appears on turn 2 rather than turn 1.

**Prevalence check:** reported across at least six independent agent frameworks
(`agno` #1784/#4345, `pydantic-ai` #562/#3197, `google/adk-python` #153, `langchain4j` #1632)
[CITED: search results, this session — LOW-to-MEDIUM confidence on any individual issue, HIGH on the
API constraint itself, which is documented provider behaviour].

### Pitfall 2: Carrying too *much* context into the receiving agent

**What goes wrong:** the receiving agent is confused by the previous agent's internal reasoning and
tool traffic, and token cost climbs on every hop.

**Why it matters here:** LangChain's guide cautions directly — *"While you could include the full
subagent conversation in the handoff, this often creates problems. The receiving agent may become
confused by irrelevant internal reasoning, and token costs increase unnecessarily."*
[CITED: docs.langchain.com/oss/python/langchain/multi-agent/handoffs] — which reads as a direct
conflict with MESH-03's "full conversation."

**Resolution (favourable, and worth stating in the plan):** the conflict is only apparent. PAAF's
history contains **only user and assistant turns** — no scratchpad, no tool traffic, no chain-of-
thought. So "the full conversation" in PAAF *is* the clean user-facing transcript, which is exactly
what the guidance recommends passing. **Do not build an input-filter/compaction layer for this in
Phase 4** — the architecture already delivers the recommended outcome, and adding filtering would
weaken MESH-03.

**Residual risk:** if D-11's "keep pre-handoff prose" setting is on, that prose lands in history as
an assistant turn and *is* carried. That is the user's explicit choice, it is visible, and the
explainer is supposed to discourage the style — acceptable for Phase 4 by D-11.

### Pitfall 3: Binding tools may degrade token streaming on the local provider

**What goes wrong:** `ChatOllama` returns the whole reply as a single chunk once tools are bound —
historically even with an *empty* tools list. Because the mesh binds a handoff tool to essentially
every agent, this would silently convert PAAF from a streaming system into a batch one for its
primary local provider.

**Status — the honest version.** `langchain-ai/langchain` issue #26971, *"Token-level streaming is
unavailable in `langchain_ollama.ChatOllama` when tools are bound"*, was opened **2024-09-29** and
**closed 2025-06-26** — i.e. fixed well before the `langchain-ollama==1.1.0` this repo pins
[VERIFIED: GitHub REST API `repos/langchain-ai/langchain/issues/26971`, queried this session:
`state=closed`, `closed_at=2025-06-26T20:22:23Z`]. Upstream, Ollama shipped an incremental tool-call
parser enabling streaming *with* tool calling on **2025-05-28**, covering Qwen 3 and Qwen 2.5
[CITED: ollama.com/blog/streaming-tool].

**Why it still deserves a verification task rather than a shrug.** The fix is inferred from an issue
closure and an upstream release note, not from an executed check against this repo's exact pins. Two
documented residual caveats survive the fix: tool-call arguments do **not** stream progressively the
way text content does, and some models return only the tool call with no accompanying prose
[CITED: ollama.com/blog/streaming-tool]. The second interacts directly with D-11 (pre-handoff prose)
and with the phase's latency profile.

**How to avoid:** one short live check in the `engine-adapter` lane (or a scratch script) against
`qwen3.5:9b` — both models are present on this machine (§ Environment Availability): bind one dummy
tool, `astream`, assert **more than one** chunk arrives for a plain reply, and assert a tool call
aggregates correctly. **Recommendation: schedule this early**, because a negative result changes the
adapter design (it would force a non-streaming decision call), not just a constant.

**Note on scope:** this affects only the *real* adapter. SC#5's framework-uninstalled mesh suite runs
on `FakeAdapter` and is unaffected either way — which is precisely the port earning its keep again.

### Pitfall 4: Assuming the bound tool surface is a sufficient guard

**What goes wrong:** the peer graph is enforced only by which tools were bound, so no runtime guard
exists; then a model emits `transfer_to_admin` — a tool that was never offered — and the engine
either crashes on a `KeyError` or, worse, resolves the name against `LlmConfig.profiles` and follows
it. MESH-02's "rejected, never silently followed" fails in the exact scenario it was written for.

**Why it happens:** capability removal is genuinely the right primary mechanism (D-04/D-08), and it
feels complete. It is not: models routinely emit tool names outside the bound set.

**How to avoid:** § Pattern 2 — keep both. And write the negative control as a `FakeAdapter` program
that emits a handoff to a target the engine never offered.

**Warning signs:** a plan in which the only MESH-02 test asserts that an undeclared peer produces no
tool; a guard implemented as `profiles[target]` lookup rather than `target in awake.peers`.

### Pitfall 5: `paaf-trace` has no migration mechanism — adding a column silently does nothing

**What goes wrong:** MESH-05 adds `awake_agent` / `turn_id` columns to `runs`; the change works
perfectly on a fresh database and fails on every machine with an existing `trace.db` with
`sqlite3.OperationalError: table runs has no column named awake_agent`. CI is green because CI always
starts fresh (`trace_store` fixture uses `tmp_path`).

**Why it happens:** the writer's entire schema step is `await db.executescript(read_schema())`, and
`schema.sql` is all `CREATE TABLE IF NOT EXISTS` [VERIFIED: `paaf_trace/store.py` + `schema.sql`,
read this session]. There is no version table, no `ALTER TABLE`, and no migration runner anywhere in
the repo. `IF NOT EXISTS` makes an *added column* a silent no-op on an existing table — the most
dangerous shape of this bug, because nothing warns at startup.

**How to avoid — two viable routes, and a recommendation.**

- **(A) New tables only, zero changes to `runs`.** `CREATE TABLE IF NOT EXISTS handoffs (...)` and
  `CREATE TABLE IF NOT EXISTS turn_legs (...)` just work on an existing DB. **Recommended for this
  phase**: it is the lower-risk path, it needs no new machinery, and it keeps MESH-05's
  reconstructability intact.
- **(B) Add columns plus a real migration step** — an idempotent `ALTER TABLE ... ADD COLUMN` guarded
  by `PRAGMA table_info(runs)`, or a `schema_version` table. Correct long-term, but it is a
  `paaf-trace` architectural addition that Phase 4 did not budget for and that deserves its own
  design.

**Warning signs:** any plan task that edits an existing `CREATE TABLE` block in `schema.sql`. Add a
verification step that runs the suite twice against the *same* DB file, since the tmp-path fixture
will never catch this.

### Pitfall 6: Every hop is a full model round-trip on the latency path

**What goes wrong:** the hop budget is set generously (industry guidance suggests 5–10 handoffs per
session [ASSUMED — practitioner synthesis]), and a turn that hops three times pays three full
time-to-first-token penalties before the user sees anything. Handoff is silent (D-10), so from the
user's side the assistant simply goes quiet. Phase 9 wraps this loop for voice, and the repo already
runs a `ttfa-gate` CI job, so this is a measured concern rather than a stylistic one.

**Why it happens:** the handoff decision arrives as a tool call, which is only knowable once the
leg's stream is aggregated. The engine therefore cannot pass a leg's tokens through to the user until
it knows that leg is a reply and not a handoff.

**Mitigating facts (check these before designing around the problem):** `Agent.turn()` already
returns a complete `TurnResult.text` and exposes no streaming API — `_run_chain` joins tokens
internally, and streaming exists only to serve the first-token deadline [VERIFIED: `agent.py`, read
this session]. So Phase 4 introduces **no new buffering regression**; the constraint simply becomes
explicit. It also means D-11's "drop pre-handoff prose" option is implementable, which it would not
be if tokens streamed straight through.

**How to avoid:** set a **small default hop budget**. Recommendation: **3 handoffs per user turn**,
user-configurable. Three is the smallest value that leaves headroom above the legitimate A→B→A
hand-back (2 hops) that the negative-control suite must prove still works. Document the latency cost
of raising it, and hand Phase 9 the explicit note that only the *final* agent's tokens may stream.

### Pitfall 7: The observer is a new, wide egress path

**What goes wrong:** a user points the reserved `observer` profile at a cloud endpoint and widens
`window` to "N last messages"; now a slice of conversation leaves the box on **every handoff
attempt**, including rejected ones — a frequency profile quite unlike a normal reply.

**Why it happens:** D-15 makes the window configurable by design, and the default (last user message
+ handoff decision + reasoning) is narrow. The failure is a user turning a knob without seeing the
consequence.

**How to avoid:** it is largely free — the observer is an ordinary `ModelProfile`, so its `Endpoint`
is declared and Phase-10's offline refusal covers it. CONTEXT explicitly asks that **the docs say
this**. Add a plan task for the doc line; do not let it be implied by the schema.

## Code Examples

### 1. The port extension that satisfies D-01 without editing the Phase-3 port (D-02)

```python
# packages/paaf-llm/src/paaf_llm/ports.py  — ADDITIVE ONLY.
# ChatAdapter's own definition is not touched: no method added to it, no
# signature moved. The mesh's needs live in a SECOND protocol that extends it.

@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One tool offered to a model, in PAAF terms. No framework type here."""
    name: str
    description: str
    parameters: dict[str, object]  # JSON Schema; empty dict = no arguments


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool call a model emitted, read AFTER the stream is aggregated."""
    name: str
    arguments: dict[str, object]
    call_id: str | None = None


@dataclass(frozen=True, slots=True)
class HandoffRequest:
    """The Phase-4 payload for TurnResult.handoff (was `type HandoffRequest = Any`)."""
    from_agent: str
    to_agent: str


@runtime_checkable
class ToolCallingChatAdapter(ChatAdapter, Protocol):
    """A ChatAdapter that can additionally be offered tools (D-01).

    Deliberately a SEPARATE protocol: `ChatAdapter` keeps exactly the two
    methods Phase 3 declared, so the port's shape does not change (D-02). The
    engine feature-detects with `isinstance(adapter, ToolCallingChatAdapter)`
    and, on an adapter that is not one, runs the Phase-3 single-agent path and
    says so — rather than silently behaving as if no peer were ever declared.
    """

    def stream_with_tools(
        self,
        profile: ModelProfile,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> AsyncIterator[str]: ...

    def last_tool_calls(self) -> tuple[ToolCall, ...]:
        """Tool calls from the most recently completed stream.

        Read AFTER aggregation, never per chunk — the same rule and the same
        reason as `last_usage()`: providers publish the assembled call only once
        the stream drains, so a mid-stream read yields partial JSON.
        """
        ...
```

*Source: composed for this repo from `ports.py`'s own conventions (frozen slotted dataclasses,
`runtime_checkable` Protocol, `last_*()` post-aggregation reads). The `last_tool_calls()` shape
mirrors the existing, proven `last_usage()` seam.*

### 2. The adapter side — the only place the framework's tool vocabulary may appear

```python
# packages/paaf-llm/src/paaf_llm/_engine/__init__.py

async def stream_with_tools(self, profile, messages, tools):
    model = self.bind(profile)
    if tools:
        # PAAF ToolSpec -> the OpenAI-style function dicts bind_tools accepts.
        # This dict is the ONLY translation; no framework tool type is built.
        model = model.bind_tools([
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ])

    aggregate = None
    try:
        async for chunk in model.astream(self._to_framework_messages(messages)):
            # Identical aggregation to the existing usage path: adding chunks is
            # what reassembles partial tool-call JSON into parsed .tool_calls.
            aggregate = chunk if aggregate is None else aggregate + chunk
            text = str(getattr(chunk, "text", "") or "")
            if text:
                yield text
    except Exception as exc:
        raise self._translate(exc) from exc

    self._last_usage = self._usage_of(aggregate)
    self._last_tool_calls = self._tool_calls_of(aggregate)   # NEW, same seam

@staticmethod
def _tool_calls_of(aggregate) -> tuple[ToolCall, ...]:
    """Read PARSED tool calls off the AGGREGATE, never off a chunk.

    Mid-stream, `tool_call_chunks` carries partial JSON fragments
    ('{"', 'city', ...). Only the summed message exposes `.tool_calls` with
    arguments parsed into a dict.
    """
    return tuple(
        ToolCall(name=tc["name"], arguments=tc.get("args") or {}, call_id=tc.get("id"))
        for tc in (getattr(aggregate, "tool_calls", None) or ())
    )
```

*Source: aggregation-then-read pattern per [CITED: docs.langchain.com/oss/python/langchain/streaming],
which shows `full_message = token if full_message is None else full_message + token` followed by
reading `full_message.tool_calls`. The surrounding structure copies this repo's existing
`LangChainAdapter.stream` verbatim, including the `_translate` boundary and the `str()` call that
stops the framework's `TextAccessor` (a `str` subclass) from crossing the port.*

### 3. Extending the composer without breaking its byte-exact invariant

```python
# packages/paaf-llm/src/paaf_llm/compose.py

def segments(
    self,
    base_prompt: str,
    fragments: list[tuple[str, str]],
    mesh_fragments: list[tuple[str, str]] = (),   # NEW: e.g. [("mesh:explainer", text)]
) -> list[Segment]:
    segs = [Segment("base", base_prompt)]
    segs += [Segment(f"skill:{name}", text) for name, text in fragments]
    segs += [Segment(source, text) for source, text in mesh_fragments]
    return segs

# compose() is UNCHANGED in spirit and must stay this exact shape, because
# tests/test_compose.py splits the output back apart and demands it equal the
# segment texts. Phase 4 widens that assertion to [base, *fragments, explainer]
# — it must not delete it. This is the PERS-05 enforcement point.
def compose(self, base_prompt, fragments, mesh_fragments=()) -> str:
    return SEGMENT_SEPARATOR.join(
        s.text for s in self.segments(base_prompt, fragments, mesh_fragments)
    )
```

*Source: this repo's `compose.py`, read this session. The invariant
`compose(...) == SEGMENT_SEPARATOR.join(s.text for s in segments(...))` is asserted today and must
keep being asserted.*

### 4. The guard, in the place the taxonomy wants it

```python
# packages/paaf-llm/src/paaf_llm/mesh.py  (pure, stdlib-only, framework-free)

def resolve_handoff(awake_name: str, awake: ModelProfile, call: ToolCall) -> str:
    """Return the validated handoff target, or raise (MESH-02).

    Deterministic and unconditional: this is the ONE mesh guarantee that holds
    in every configuration, observed or not (D-13). It is checked against the
    declared peer list — never against `LlmConfig.profiles` — because a target
    that merely EXISTS is not a target this agent may reach.
    """
    target = _target_of(call)          # tool name -> peer name
    if target not in awake.peers:
        raise UndeclaredPeer(
            f"{awake_name!r} attempted a handoff to {target!r}, which is not in "
            f"its declared peers {sorted(awake.peers)}"
        )
    return target
```

*Source: composed for this repo, following `profiles.py`'s error-message style (name the offending
value) and `ports.py`'s exception-placement rationale.*

### 5. Scripting a handoff on the fake — the SC#5 substrate

```python
# packages/paaf-llm/src/paaf_llm/fake/__init__.py  (additions)

def program(self, profile_name, *, tokens=None, fail=None,
            first_token_delay_s=0.0, usage=None,
            tool_calls: list[ToolCall] | None = None) -> None:
    ...

# and, in stream_with_tools, record what was OFFERED so a test can prove the
# peer graph shaped the surface:
self.tool_offers.append((key, tuple(t.name for t in tools)))

# The MESH-02 negative control this unlocks: script a call to a target that was
# never offered. Without a runtime guard, this test cannot be written.
fake.program("chef", tool_calls=[ToolCall("transfer_to_admin", {})])
```

*Source: this repo's `FakeAdapter`, read this session — `program()` and the existing
`self.calls: list[tuple[str, tuple[Message, ...]]]` recording seam.*

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sentinel string in the reply, parsed by regex | Native tool call (`transfer_to_<agent>`) | ~2024 (OpenAI Swarm → Agents SDK), now universal | Validates D-01. Also means every serious model is *trained* on this shape, which is part of why Phase 1 measured 30/30 |
| Central supervisor routes every turn | Peer-to-peer swarm handoff; each agent owns its own peer list | 2025 (`langgraph-swarm`; OpenAI Agents SDK handoffs) | PAAF's per-profile `peers` is the current shape, not a novel one |
| Ollama could not stream while tool calling | Incremental tool-call parser; streaming + tools together | **2025-05-28** [CITED: ollama.com/blog/streaming-tool] | Removes what would have been Phase 4's biggest architectural risk. Verify against the pinned client — § Pitfall 3 |
| `langchain_ollama` collapsed streaming when tools were bound | Fixed | issue closed **2025-06-26** [VERIFIED: GitHub API] | Predates `langchain-ollama==1.1.0`, the pinned version |
| Handoff instructions injected invisibly into the agent's prompt | *Still the norm elsewhere* — OpenAI Agents SDK ships `RECOMMENDED_PROMPT_PREFIX` / `prompt_with_handoff_instructions()` [CITED: openai.github.io/openai-agents-python/handoffs/] | — | **PAAF deliberately diverges.** This is precisely the hidden-instruction pattern PERS-05 and MESH-04 forbid. PAAF's explainer must be generated, overridable, and printed verbatim by the inspector. Worth stating in the docs as a differentiator |

**Deprecated/outdated for this phase:**

- **Reading `tool_call_chunks` directly to reconstruct arguments** — superseded by summing chunks and
  reading the parsed `.tool_calls` off the aggregate.
- **CLAUDE.md's concern that "LangChain callbacks fail to cleanly surface MCP tool args + results"** —
  refuted by SPIKE-06, recorded in `DECISIONS.md`. Do not design around it.
- **The `type HandoffRequest = Any` alias in `ports.py`** — a Phase-3 placeholder under
  `TYPE_CHECKING`, explicitly labelled "It does not exist yet, by design." Phase 4 replaces it with a
  real type; leaving the alias would silently keep `TurnResult.handoff` untyped.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Streaming still works on `langchain-ollama==1.1.0` with tools bound (inferred from an issue closure + an upstream release note, not executed here) | Pitfall 3, State of the Art | Medium-high. Would force a non-streaming decision call in the adapter and change the latency story. **Mitigation: one live check, scheduled early — both `qwen3.5` models are on this machine** |
| A2 | A hop budget of ~3 is right for a latency-sensitive single-user voice assistant (industry guidance says 5–10, for different systems) | Pitfall 6 | Low. A user-configurable default; wrong only in ergonomics. Must be ≥3 so the legitimate A→B→A hand-back is not blocked by the wall |
| A3 | Sticky-within-process, non-persisted awake-state is what MESH-03 intends | Pattern 4 | Low-medium. Explicitly Claude's discretion in CONTEXT; confirm with the founder if cheap. Persisting it while history stays ephemeral would be incoherent |
| A4 | `LlmConfig.base_prompt` should remain the shared base with additive per-profile overrides, rather than being reshaped | Pattern 3 | Low. Explicitly Claude's discretion (D-17). Additive is the lower-risk reading of "two agents can have genuinely different prompts" |
| A5 | Practitioner guidance on handoff loop caps (5–10, fingerprint repeated calls, STOP-never-continue) reflects real production practice | Don't Hand-Roll, Pitfall 6 | Low. Only informs a default value; D-08 already mandates the mechanism regardless |
| A6 | `default_agent` being undeclared should mean "the currently-awake agent answers with the handoff tool withdrawn" | Open Question 2 | Medium. If wrong, budget exhaustion has undefined behaviour. **Needs a decision before planning** — D-09 says PAAF does not guess, so the no-guess default must itself be specified |
| A7 | A rejected handoff must be communicated back to the calling agent somehow, and PAAF has no message role for it | Open Question 1 | **High** — this is the phase's sharpest unresolved design question. See Open Question 1 |

## Open Questions

### 1. How does an observer veto reach the calling agent without inventing a message the user never wrote? *(highest priority)*

- **What we know:** D-05's "generic retry" verdict kills the handoff attempt and bounces it to the
  calling agent, "which may try again or answer." For the agent to *usefully* try again, it must
  learn that its attempt was refused. PAAF's `Role` is `system | user | assistant` only, with no
  `tool` role and no `tool_call_id` [VERIFIED: `ports.py`].
- **What's unclear:** where that refusal lives. Three candidate shapes, each with a real cost:
  1. **Widen `Role` with `"tool"`.** Most conventional, but edits the Phase-3 port (D-02 tension) and
     re-opens Pitfall 1's dangling-tool-call surface by making it representable.
  2. **A transient system/assistant segment for the retry leg only** — appended to the leg's message
     list, never to `Agent.history`, and surfaced in the inspector as its own labelled provenance
     source. Preserves PERS-05 (it is visible), preserves history hygiene, and needs no port change.
  3. **Capability removal only** — re-invoke the agent with the handoff tools withdrawn, so it can
     only answer. Purest expression of the mesh house style, and completely silent, but it forfeits
     the "may try again" half of D-05.
- **Recommendation:** **(2), with the veto text generated from the same explainer machinery and
  rendered by `paaf prompt --agent`**, so it can never become a hidden instruction. Fall back to (3)
  if the retry leg proves unreliable in practice. Flag (1) as the option to avoid.

### 2. What happens at budget exhaustion when no `default_agent` is declared?

- **What we know:** D-09 makes the home agent user-declared and states plainly that PAAF does not
  guess. But `default_agent` will be optional (a user with two agents and no declared home is normal).
- **What's unclear:** the no-guess behaviour. Falling back to `active_profile` *is* a guess.
- **Recommendation:** the **currently-awake agent answers with the handoff tools withdrawn**. That is
  not a guess — it is the absence of a further move — and it composes exactly with D-08's "when the
  budget is exhausted the handoff tool is withdrawn." Record it in the trace and surface it in the
  D-05 correction-signal channel so exhaustion is observable, never silent.

### 3. Should the mesh tool surface be rendered by `paaf prompt` by default, or only under `--provenance`?

- **What we know:** D-19 keeps the default output byte-exact and authoritative — `paaf prompt` today
  emits the prompt with no trailing newline so `> sent.txt` captures exact bytes. Adding tool text to
  the default output would break that contract.
- **What's unclear:** whether PERS-05 is satisfied by an opt-in view.
- **Recommendation:** **render the tool surface under `--provenance` (and under `--agent`), never in
  the default output.** This mirrors Phase-3 D-03's raw-authoritative/annotation-opt-in philosophy
  exactly, keeps the byte-exact pipe contract, and still means no steering text is unreachable. Pair
  it with a test asserting that every tool name and description offered to a model appears in the
  `--provenance` output — that makes PERS-05 mechanical rather than aspirational.

### 4. Does the observer get its own fallback chain, and what if the observer itself is down?

- **What we know:** SC#4 says each agent applies its own fallback chain, and the observer is "just
  another profile" (D-03) — so it presumably inherits `ModelProfile.fallback_chain`.
- **What's unclear:** the fail-open/fail-closed decision if the observer's whole chain degrades.
  Fail-open silently approves handoffs that D-13 promised were checked; fail-closed makes an
  unreachable observer break all routing.
- **Recommendation:** **fail-open, but loudly** — approve the handoff and emit the D-07
  "running unobserved" notice plus a trace row, because D-07 already establishes that an unobserved
  mesh is an acceptable, *disclosed* state. Never fail-open silently. Confirm with the founder.

### 5. One `runs` row per leg, or one per turn?

- **What we know:** Claude's discretion, but the constraint is fixed: per-agent fallback chains must
  be reconstructible (SC#4), and `runs` already carries `served_by` + `fallback_trail` per row.
- **Recommendation:** **one `runs` row per agent leg**, correlated by an engine-generated `turn_id`.
  Per-agent fallback provenance then falls out of the existing columns with no new mechanism, and
  `_drain`'s current shape is reused nearly verbatim. Pair with an FK-free `handoffs` table for
  attempts, verdicts, and corrections — including *rejected* attempts, which produce no `runs` row at
  all and would otherwise be invisible. See Pitfall 5 before touching `runs`' columns.

## Open Questions — RESOLVED (orchestrator, 2026-08-07)

All five open questions above are **closed** for planning purposes. The researcher's recommendation
is adopted verbatim in every case. These are binding on the planner and the executor — treat them as
locked decisions with the same force as CONTEXT.md's `D-NN` entries.

| # | Question | **Resolution (BINDING)** |
|---|----------|--------------------------|
| **OQ-1** | How does an observer veto reach the calling agent? | **Option (2): a transient, labelled retry-leg segment.** On veto, re-invoke the calling agent with an extra prompt segment carrying the refusal, appended to *that leg's* message list only — **never** to `Agent.history`. Generate the text from the same explainer machinery, label it as its own provenance source, and render it under `paaf prompt --agent`. Do **not** widen `Role` with `"tool"` (option 1 is forbidden — it re-opens Pitfall 1 and edits the Phase-3 port against D-02). If the retry leg proves unreliable in execution, fall back to option (3) (capability removal only) and record the deviation. |
| **OQ-2** | Budget exhaustion with no `default_agent` declared? | **The currently-awake agent answers with the handoff tools withdrawn.** This is the absence of a further move, not a guess, so D-09 holds. Compose it with D-08's existing "at the wall, withdraw the handoff tool." Record exhaustion in the trace and surface it on the D-05 correction-signal channel — exhaustion must never be silent. Falling back to `active_profile` is explicitly **rejected** (it is a guess). |
| **OQ-3** | Does `paaf prompt` render the mesh tool surface by default? | **No — under `--provenance` and `--agent` only, never in default output.** The byte-exact / no-trailing-newline default contract (D-19, Phase-3 D-03) is preserved unchanged. PERS-05 is satisfied because the surface is *reachable*, not because it is *default*. Ship the paired mechanical test: every tool name and description offered to a model must appear in `--provenance` output. |
| **OQ-4** | Observer's own fallback chain / observer unreachable? | **The observer inherits `ModelProfile.fallback_chain` like any other profile (D-03), and fails OPEN — loudly.** If the observer's whole chain degrades, approve the handoff, emit the D-07 "running unobserved" notice, and write a trace row. Silent fail-open is forbidden; fail-closed is rejected because an unreachable observer must not break all routing. |
| **OQ-5** | One `runs` row per leg, or per turn? | **One `runs` row per agent leg**, correlated by an engine-generated `turn_id` (never `lastrowid` — see Finding 5). Per-agent `fallback_trail` provenance then falls out of existing columns with no new mechanism. Add an **FK-free `handoffs` table** for attempts, verdicts, and corrections — including *rejected* attempts, which produce no `runs` row and would otherwise be invisible. Read Pitfall 5 before touching `runs`' columns: `paaf-trace` has no migration mechanism, so prefer new tables over new columns. |

**Assumption A1 (streaming with tools bound on `langchain-ollama==1.1.0`) — disposition:** do **not**
block the phase on it. The entire mesh suite runs on `FakeAdapter`, so A1 cannot affect SC#5. Include
one **non-blocking** live check as a scratch script (not a pytest test — the suite is
`--disable-socket`), run it early, and record the result. If streaming does collapse with tools
bound, that is an engine-adapter latency finding to be logged, not a phase blocker.

**Assumption A3 (awake-state is sticky within-process and not persisted) — adopted.** Persisting
awake-state while conversation history stays ephemeral would be incoherent.

**Assumption A2 (hop budget default) — adopted at 3, user-configurable, with a hard floor of 3** so
the legitimate A→B→A hand-back is never blocked by the wall.

**Assumption A4 (`base_prompt` stays the shared base, per-profile overrides are additive) — adopted.**

## Environment Availability

All verified on this machine this session.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | everything | ✓ | 3.12.13 | — |
| `uv` | workspace + both CI lanes | ✓ | 0.11.31 | — |
| `pytest` + `pytest-asyncio` | the whole suite | ✓ | 9.1.1 / 1.4.0 (pinned in root `[dependency-groups]`) | — |
| `pytest-socket` | no-network default | ✓ | 0.7.0 (pinned) | — |
| `import-linter` | the `langchain*` confinement contract | ✓ | 2.13 | — |
| `ruff` | lint/format | ✓ | 0.16.0 | — |
| `mypy` | "public API leaks no framework type" | ✓ | 2.3.0 | — |
| `sqlite3` | inspecting the trace DB by hand | ✓ | 3.51.0 | `aiosqlite` from Python |
| Ollama | **only** the optional live tool-streaming check (Pitfall 3 / A1) | ✓ | 0.32.1 | Skip the check; the mesh suite runs on `FakeAdapter` regardless |
| `qwen3.5:9b` / `qwen3.5:2b` | same live check — the exact Phase-1 gate models | ✓ | 6.6 GB / 2.7 GB, pulled 2 weeks ago | — |
| `langchain` + bindings | the `engine-adapter` CI lane only | ✓ (via `uv sync --extra engine`) | 1.3.14 / core 1.5.3 / ollama 1.1.0 | Not needed for SC#5 |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

**Notable:** the machine is provisioned to *close* assumption A1 cheaply — the live streaming check
needs no new install and no network beyond localhost. Note that the pytest default is
`--disable-socket --allow-unix-socket`, so any live-Ollama check must run **outside** the normal
suite (a scratch script or an explicitly socket-enabled marker), never as a plain test.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| Config file | `/pyproject.toml` `[tool.pytest.ini_options]` — `--disable-socket --allow-unix-socket --import-mode=importlib -p no:langsmith_plugin`, `testpaths = ["packages"]` |
| Quick run command | `uv run pytest packages/paaf-llm -q` |
| Full suite command | `uv run pytest -q` |
| Framework-uninstalled gate (SC#5) | `bash scripts/check_framework_uninstalled.sh` → `pytest --pyargs paaf_llm` in a clean venv |
| Engine-adapter gate | `uv sync --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py` |
| Shared fixtures | `packages/paaf-llm/tests/conftest.py` — `fake_adapter`, `make_profile`, `make_llm_config`, `trace_store` |

**A packaging step the planner must not miss.** Every new mesh test file that must run in the
framework-uninstalled lane has to be added to `[tool.hatch.build.targets.wheel.force-include]` in
`packages/paaf-llm/pyproject.toml` — the shipped suite is an explicit file list, not a glob
[VERIFIED: `pyproject.toml`, read this session]. A new `test_mesh.py` that is not listed will pass
locally and be invisible to the SC#5 gate, which is the one gate SC#5 is stated in terms of. Such a
file may import only `paaf_llm` + `paaf_core` + `paaf_trace` and their declared deps.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MESH-01 | No config key can express a routing rule (`extra="forbid"` negative control extended to mesh fields) | unit | `uv run pytest packages/paaf-llm/tests/test_profiles.py -k routing -x` | ❌ Wave 0 (extends existing file) |
| MESH-01 | A declared handoff tool is offered and the model's choice is followed | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k accepts_declared -x` | ❌ Wave 0 |
| MESH-02 | Undeclared target → `UndeclaredPeer`, recorded, **not** followed (fake scripts an un-offered tool) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k undeclared -x` | ❌ Wave 0 |
| MESH-02 | **Negative control:** a *declared* target is NOT blocked | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k declared_not_blocked -x` | ❌ Wave 0 |
| MESH-02 | Tool surface contains exactly the declared peers (capability removal) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k tool_surface -x` | ❌ Wave 0 |
| MESH-03 | Receiving agent's messages contain the full prior conversation | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k carries_history -x` | ❌ Wave 0 |
| MESH-03 | A→B→A hand-back works; conversation does not restart | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k hand_back -x` | ❌ Wave 0 |
| MESH-03 | No handoff tool call ever appears in `Agent.history` (Pitfall 1) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k history_clean -x` | ❌ Wave 0 |
| MESH-03 | Awake agent is sticky across user turns | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k sticky -x` | ❌ Wave 0 |
| MESH-04 | Explainer generated from *this* agent's manifest + peers appears verbatim in `--provenance` | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k explainer -x` | ❌ Wave 0 (extends existing file) |
| MESH-04 | Two agents get genuinely different prompts (D-17) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k per_agent -x` | ❌ Wave 0 |
| MESH-04 | `compose()` still equals the joined segment texts (byte-exact invariant preserved) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k byte_exact -x` | ✅ exists — **must be widened, not replaced** |
| MESH-04 | **Every** offered tool name + description appears in `--provenance` output (PERS-05 made mechanical) | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k tool_surface_visible -x` | ❌ Wave 0 |
| MESH-04 | `paaf prompt --agent <name>` targets a non-awake peer, and the reserved observer | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k agent_flag -x` | ❌ Wave 0 |
| MESH-05 | One `runs` row per agent leg, correlated by `turn_id`; per-agent `fallback_trail` intact | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k legs -x` | ❌ Wave 0 |
| MESH-05 | Every handoff attempt recorded incl. rejected ones and observer verdicts | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k attempts -x` | ❌ Wave 0 |
| MESH-05 | Schema applies cleanly to a **pre-existing** DB file (Pitfall 5) | integration | `uv run pytest packages/paaf-trace/tests/test_trace_schema.py -k reopen -x` | ❌ Wave 0 |
| MESH-06 | Observer vetoes a constraint-violating handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k vetoes -x` | ❌ Wave 0 |
| MESH-06 | **Negative control:** observer does NOT veto a good handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k allows -x` | ❌ Wave 0 |
| MESH-06 | Observer re-route to a target outside the caller's peers is rejected identically (D-06) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k reroute_guarded -x` | ❌ Wave 0 |
| MESH-06 | Observer without the re-route grant cannot re-route, whatever it emits (D-04) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k grant_bounds -x` | ❌ Wave 0 |
| MESH-06 | No `observer` profile → mesh runs unobserved and **says so** (D-07) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k unobserved_notice -x` | ❌ Wave 0 |
| D-08 | Hop budget stops a loop; handoff tool is withdrawn at the wall | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k budget -x` | ❌ Wave 0 |
| D-05 | Correction signal is observable headlessly (callback/event fires) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k correction_signal -x` | ❌ Wave 0 |
| SC#4 | Each agent applies its **own** `fallback_chain`, nested inside the handoff loop | unit | `uv run pytest packages/paaf-llm/tests/test_fallback.py -k per_agent -x` | ❌ Wave 0 (extends existing file) |
| SC#5 | The entire mesh suite passes with the framework uninstalled | integration | `bash scripts/check_framework_uninstalled.sh` | ✅ script exists — new files must be force-included |
| SC#5 | No framework type leaks through any new public signature | unit | `uv run pytest packages/paaf-llm/tests/test_no_leak.py -x` | ✅ exists — auto-covers new exports |
| — | `langchain*` stays confined to `_engine` | lint | `uv run lint-imports` | ✅ exists |

### Sampling Rate

- **Per task commit:** `uv run pytest packages/paaf-llm -q` (fake-adapter suite, sub-second, no network)
- **Per wave merge:** `uv run pytest -q` + `uv run lint-imports`
- **Phase gate:** full suite green **AND** `framework-uninstalled` green (SC#5 is not satisfied
  without it) **AND** `engine-adapter` green **AND** `ttfa-gate` unbreached, before `/gsd-verify-work`
- **Max feedback latency:** ~5s

### Wave 0 Gaps

- [ ] `packages/paaf-llm/tests/test_mesh.py` — MESH-01/02/03 + hop budget
- [ ] `packages/paaf-llm/tests/test_observer.py` — MESH-06 + D-04/D-05/D-06/D-07
- [ ] `packages/paaf-llm/tests/test_mesh_trace.py` — MESH-05
- [ ] Extend `tests/conftest.py`: a `make_mesh_config` fixture (peers, per-agent fallback chains,
      optional observer) — the existing `make_llm_config` cannot express a peer graph
- [ ] Extend `FakeAdapter`: scripted `tool_calls` + a `tool_offers` recording seam
- [ ] Add all new shipped test files to `[tool.hatch.build.targets.wheel.force-include]`
- [ ] Extend `tests/negcontrol/` if a new import boundary is introduced (none expected)
- [ ] Framework install: **not needed** — everything is present

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`. Phase 4 has no network surface of its own and
no authentication; the live categories are input validation, integrity of the routing guard, and
privacy of the new egress path.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth in this phase; `api_key_ref` resolution is unchanged Phase-3 behaviour |
| V3 Session Management | no | No sessions. Awake-state is in-process and not a security boundary |
| V4 Access Control | **yes** | The peer graph *is* the access-control matrix for routing. Enforced by `resolve_handoff` deterministically, and applied identically to observer re-routes (D-06) — no second privilege tier |
| V5 Input Validation | **yes** | `extra="forbid"` + `model_validator` on all new mesh fields; validate-on-read-never-repair; **the model's tool call is untrusted input** and its `target` must be validated against `awake.peers`, never used as a dict key |
| V6 Cryptography | no | No new crypto. Secrets stay by-reference through the existing `SecretStore` |
| V7 Error Handling & Logging | **yes** | `UndeclaredPeer` must be catchable and must not be swallowed by the fallback loop; the handoff chain drains to the local trace only (TRACE-05 no-egress control already enforced) |
| V8 Data Protection | **yes** | The observer's configurable window (D-15) is a new conversation egress path when pointed at a cloud endpoint |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection in conversation content induces an unauthorized handoff (e.g. to an agent with wider constraints) | Elevation of Privilege | The deterministic peer-graph guard — D-13 names it as the one guarantee holding in every configuration. Never widen the graph at runtime; never let the observer reach outside the *caller's* graph (D-06) |
| **Prompt injection against the observer** — content in the window argues the handoff is legitimate | Elevation of Privilege | Capability removal (D-04): the observer's powers are its tool grant, default retry-only. It cannot re-route without the tool no matter what it is persuaded of. The peer guard still applies to anything it does emit |
| Model emits a tool call for a tool that was never bound | Spoofing / Tampering | § Pattern 2's runtime guard; § Pitfall 4 |
| Smuggled config field encodes a hidden routing rule | Tampering | `extra="forbid"` on `ModelProfile` and `LlmConfig` (T-03-02, already shipped) — extend the existing `routing_rules` negative-control test to the new mesh fields |
| Hidden steering text via tool names/descriptions the inspector does not show | Repudiation / Tampering | § Finding 1 — render the tool surface under `--provenance`; add the test that every offered tool name and description appears there |
| Cloud observer with a wide window exfiltrates conversation on every handoff attempt | Information Disclosure | Observer is an ordinary `ModelProfile` → declared `Endpoint` → Phase-10 offline refusal. **Plus an explicit documentation line**, which CONTEXT asks for by name (§ Pitfall 7) |
| Unbounded handoff loop exhausts tokens/money/latency | Denial of Service | Deterministic engine-side hop budget with the tool withdrawn at the wall (D-08). Never model-enforced |
| Free-text `constraints` interpreted inconsistently, giving false assurance | Repudiation | Honest documentation: D-13 makes the observer "the system", and D-07's unobserved notice is the disclosed caveat. Do not claim deterministic constraint enforcement anywhere in docs or code comments |

**Carried-forward threat IDs to reference in plans:** T-03-02 (`extra="forbid"`, smuggled config
field), T-03-04 (secret scrubbing in adapter error text), T-03-36 (untrusted hand-edited config).

## Sources

### Primary (HIGH confidence)

- **This repository, read directly this session** — `packages/paaf-llm/src/paaf_llm/{ports,agent,profiles,compose,cli}.py`, `fake/__init__.py`, `_engine/__init__.py`; `packages/paaf-trace/src/paaf_trace/{store.py,schema.sql}`; `packages/paaf-llm/tests/conftest.py`; `.importlinter`; root and package `pyproject.toml`; `uv.lock`; `.github/workflows/*.yml`
- **GitHub REST API** — `repos/langchain-ai/langchain/issues/26971`: `state=closed`, `closed_at=2025-06-26T20:22:23Z` (queried this session)
- **Local environment probes** — `python3`, `uv`, `ruff`, `mypy`, `ollama`, `sqlite3`, `lint-imports`, `ollama list` (this session)
- `.planning/phases/04-agent-mesh/04-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/phases/03-paaf-llm-core/{03-CONTEXT,03-PATTERNS,03-VALIDATION}.md`, `DECISIONS.md`, `.claude/CLAUDE.md`

### Secondary (MEDIUM confidence)

- [docs.langchain.com/oss/python/langchain/streaming](https://docs.langchain.com/oss/python/langchain/streaming) — `tool_call_chunks`, chunk summation, reading `.tool_calls` off the aggregate
- [docs.langchain.com/oss/python/langchain/multi-agent/handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs) — handoff tools, `active_agent` state, the `ToolMessage`/`tool_call_id` requirement, the caution on carrying full sub-agent history
- [openai.github.io/openai-agents-python/handoffs/](https://openai.github.io/openai-agents-python/handoffs/) — `transfer_to_<agent>` naming, default full-history transfer, input filters, `RECOMMENDED_PROMPT_PREFIX`
- [reference.langchain.com/python/langgraph-swarm/handoff/create_handoff_tool](https://reference.langchain.com/python/langgraph-swarm/handoff/create_handoff_tool) — `create_handoff_tool` default naming
- [ollama.com/blog/streaming-tool](https://ollama.com/blog/streaming-tool) — incremental tool-call parser, 2025-05-28, Qwen 3 / Qwen 2.5 coverage, and the residual "arguments do not stream progressively" caveat

### Tertiary (LOW confidence — flagged, not relied upon)

- Practitioner posts on multi-agent loop prevention (max-handoff ceilings of 5–10, tool-call fingerprinting, STOP-never-continue) — informs assumption A2/A5 only; the mechanism itself is mandated by D-08 regardless
- Cross-framework reports of the dangling tool-call 400 (`agno` #1784/#4345, `pydantic-ai` #562/#3197, `google/adk-python` #153, `langchain4j` #1632) — individually LOW, but collectively corroborate an API constraint that is itself documented behaviour

## Metadata

**Confidence breakdown:**

- **Standard stack: HIGH** — no new dependency; every version read from this repo's own lockfile and pinned `pyproject.toml` rather than from training data
- **Existing-code seams: HIGH** — every claim about `ports.py`, `agent.py`, `profiles.py`, `compose.py`, `cli.py`, `fake/`, `_engine/`, `schema.sql`, `store.py`, `.importlinter` and the wheel force-include list was read from source this session
- **Architecture patterns: MEDIUM-HIGH** — the handoff-as-tool shape is corroborated by three independent official sources; PAAF's specific composition (capability protocol beside the port, per-leg trace rows, FK-free correlation) is reasoned from this codebase's own documented constraints rather than copied
- **Pitfalls: MEDIUM-HIGH** — Pitfalls 1, 4, 5 and 6 are grounded in source or official docs; Pitfall 3's *resolution* is inferred (assumption A1) and carries a recommended verification task
- **Trace/migration finding: HIGH** — `executescript` + `CREATE TABLE IF NOT EXISTS` with no version table was read directly; the silent-no-op consequence is standard SQLite behaviour
- **Open Question 1 (veto channel): LOW confidence in the recommendation, HIGH confidence that it is unresolved** — it should be settled before planning rather than during it

**Research date:** 2026-08-06
**Valid until:** 2026-09-05 (30 days). The repo-internal findings do not expire; only assumption A1
and the external convention citations are time-sensitive, and A1 should be closed by execution
regardless.
