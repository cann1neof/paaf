# Phase 4: Agent Mesh - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 makes the **inert mesh seam from Phase 3 live**. The currently-awake model decides, itself,
to hand control to a declared peer; the receiving agent gets the conversation, becomes awake, and may
hand off again — including back. In scope: the **handoff primitive** (a reserved mesh tool call, not a
registry entry); the **peer-graph guard** (MESH-02 — an undeclared target is a catchable error); the
**observer** (a reserved, on-by-default supervising profile that judges each handoff attempt and may
bounce it back or re-route it); **free-text constraint enforcement at handoff time** (MESH-06); the
**generated-but-overridable handoff explainer** visible in the prompt inspector (MESH-04/PERS-05); a
**deterministic hop budget** with a user-declared **home agent** as the terminator; **per-agent prompt
assembly**; and the **full handoff chain in the trace** (MESH-05). All of it headless — text only, no
audio, no wall-clock — and proven in CI against the `FakeAdapter` with the agent framework
uninstalled (SC#5).

**Out of scope (belongs elsewhere):**
- **The tool registry, MCP, permission tiers** → Phase 5. Handoff is the **only** tool the mesh
  exposes, plus the observer's own small grant. It is a primitive of the conversation loop, not a
  registry entry.
- **Long-history lookup tool** → needs the registry (Phase 5) and long-term memory (v2). Phase 4
  leaves the room for it in the design and builds the current-conversation layer only.
- **Observer duties beyond handoff** (reply/content-level checking, other supervision) → v2.
- **Mechanical enforcement that an agent emits no prose before a handoff call** → v2 (flagged
  important by the founder).
- **Routing-quality / mis-route eval (ROUTE-01)** → v2. This phase buys observability, not a
  guarantee.
- **Audio, barge-in, turn timing** → Phase 9 wraps this loop; it does not reinvent it.

</domain>

<decisions>
## Implementation Decisions

### The handoff signal (MESH-01/02)

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

### The observer

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

### Loop safety and turn shape (MESH-03)

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

### Constraints (MESH-06)

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

### Context carry-across and the explainer (MESH-03/MESH-04)

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope (this phase)
- `.planning/REQUIREMENTS.md` — **MESH-01 … MESH-06** (lines 76–81) are this phase's contract. Also
  read **ROUTE-01** in the Deferred section (line 199): v1 ships observability, not a routing-quality
  eval.
- `.planning/ROADMAP.md` §"Phase 4: Agent Mesh" — goal + 5 Success Criteria, `mode: mvp`.
- `.planning/ROADMAP.md` §"Notes on Structure" → "The agent mesh is the framework's spine, and it is
  text-first" — why routing is LLM-driven, why the loop lives in `paaf-llm` and not `paaf-session`,
  and why the mesh ships *before* tools (Phase 5) and voice.
- `.planning/ROADMAP.md` §"Phase 5" and §"Phase 6" — what must NOT be pulled forward (tool registry,
  MCP, permission tiers, skills, PyPI release). Phase 6 publishes `paaf-llm` **with the mesh in it**.

### Prior phase decisions this phase inherits
- `.planning/phases/03-paaf-llm-core/03-CONTEXT.md` — especially **D-07/D-08** (manifest + peer graph
  are free text; **no deterministic routing-rule DSL anywhere**), **D-10** (PERS-05 is mechanical and
  the inspector is its enforcement point across both phases — the Phase-4 explainer MUST appear
  there), **D-02/D-03** (the two inspector entry points, and the raw-view-authoritative /
  annotation-opt-in philosophy that D-19 above extends), and **D-06** (fallback provenance in the
  trace).
- `DECISIONS.md` (repo root) — §"Decision: LangChain 1.x + LangGraph STANDS", the port-hides-framework
  result, SPIKE-05/06 notes (Ollama token counts surface only after aggregation; MCP falsifier came
  back negative), and the **30/30 well-formed tool calls** measurement that D-01 rests on.
- `.claude/CLAUDE.md` §"The constraint that makes this decision cheap" — all `langchain*` imports
  confined to `paaf_llm._engine`, CI-enforced by import-linter.

### Phase-3 code this phase makes live (read before designing)
- `packages/paaf-llm/src/paaf_llm/ports.py` — the port. `TurnResult.handoff` is the declared Phase-4
  seam and is documented as such in the module docstring. `AdapterError` / `FallbackReason` /
  `AllProvidersFailed` / `EngineError` define what "try the next profile" vs "stop" already mean;
  the handoff guard's error type must slot into that taxonomy deliberately, not accidentally.
- `packages/paaf-llm/src/paaf_llm/profiles.py` — `ModelProfile.capabilities` / `.peers` /
  `.constraints` (the inert seam, with reload tiers) and `LlmConfig._check_refs`, which **already
  validates the peer graph at load** (no self-peer, no dangling edge). The `LlmConfig` docstring
  states explicitly why `fallback_chain` and `peers` are separate fields — D-09's home agent is the
  third such concept and must be kept distinct too.
- `packages/paaf-llm/src/paaf_llm/agent.py` — `Agent.turn`, `_run_chain`, `_drain`, the `TraceSink`
  and `SecretResolver` protocols. This is the loop handoff wraps.
- `packages/paaf-llm/src/paaf_llm/compose.py` — `PromptComposer.segments` / `.compose` and the
  `Segment.source` labelling that `--provenance` renders. D-17/D-18's per-agent explainer segment
  lands here.
- `packages/paaf-llm/src/paaf_llm/fake/__init__.py` — `FakeAdapter` + its injected `program()` script.
  **Handoff must be scriptable here**, deterministically, or SC#5 is unreachable.
- `packages/paaf-llm/src/paaf_llm/cli.py` — `paaf chat` / `paaf prompt` / `paaf profiles`, the
  `--show-prompt` / `--provenance` flags, and `_print_fallback_trail` (the `↳ fell back to …` notice
  whose shape D-10 declined to copy for handoffs).
- `packages/paaf-trace/src/paaf_trace/schema.sql` + `store.py` — the `runs` table with `served_by`
  and the JSON `fallback_trail`, plus the single-writer queue. MESH-05 extends this.

### Governance
- `DECISIONS.md` — the anti-feature list and the no-hidden-instructions commitment. The explainer and
  the observer's system prompt are both prompt text that steers behavior; D-18/D-19 are how they stay
  inspectable.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`TurnResult.handoff`** — the always-`None` seam is already declared and documented in `ports.py`
  precisely so adding handoff changes no signature. Use it; do not reshape the port around it.
- **`LlmConfig._check_refs`** — peer-graph integrity (no self-peer, no dangling target) is **already
  validated at config load**. MESH-02's runtime guard only needs to handle a model naming something
  outside the graph, not a graph that is internally broken.
- **`Endpoint` / `ReloadTier` plumbing on `ModelProfile`** — the observer is just another profile, so
  it inherits endpoint declaration (and therefore Phase-10's offline refusal) and reload tiers for
  free. New mesh fields must carry `reload_tier` metadata like every existing field does.
- **`Segment.source` + `--provenance`** — the labelled-segment mechanism the explainer needs already
  exists; the explainer becomes a new source label.
- **`FakeAdapter.program()`** — the deterministic scripting seam. Handoff scenarios (successful
  handoff, undeclared target, observer veto, observer re-route, budget exhaustion) all become scripts.
- **`paaf-trace` single-writer queue** — MESH-05 drains through the existing sink, off the hot path.

### Established Patterns
- **Capability removal over instruction** — D-04 and D-08 both work by withdrawing a tool rather than
  telling a model not to do something. This is now the mesh's house style for anything that must hold
  regardless of what the model decides; prefer it over prompt text.
- **Negative-control discipline** (Phases 1–3) — a check that cannot fail is not a check. The suite
  must prove the peer guard *fires* on an undeclared target AND that a declared target is *not*
  blocked; that the hop budget *stops* a loop AND that a legitimate A→B→A hand-back still works;
  that the observer *vetoes* a bad handoff AND does *not* veto a good one; that an unobserved mesh
  still says it is unobserved.
- **Adapter-package confinement, CI-enforced** — the mesh-private tool surface must be expressed in
  PAAF types in `ports.py`; the framework's tool-calling representation stays inside
  `paaf_llm._engine`.
- **Framework-uninstalled CI job** (Phase 3, plan 03-09) — SC#5 says the whole mesh runs there.
  Every mesh test must pass against `FakeAdapter` with the framework absent.
- **Validate-on-read, never repair** (`profiles.py`) — a malformed mesh declaration is *reported*
  with its offending value, never normalized into something plausible.
- **`extra="forbid"`** on config models — a hand-edited config is untrusted input; no smuggled field
  and therefore no hidden routing rule can ride along.

### Integration Points
- `Agent.turn` / `_run_chain` in `agent.py` is where the handoff loop wraps the existing per-agent
  fallback chain. **Each agent applies its own fallback chain** (SC#4) — so fallback is per-agent,
  nested inside the handoff loop, not global to the turn.
- `compose.py` gains the per-agent explainer segment; `cli.py` gains `--agent` on `paaf prompt`.
- `paaf-trace` schema gains the handoff chain; the correction signal (D-05) additionally needs a
  library-level observable surface, which Phase 10's WebSocket live-state channel will later consume.

</code_context>

<specifics>
## Specific Ideas

- Founder's framing of the observer, verbatim: *"the smallest model (that user can configure in a
  certain way or disable it completely) that checks if the agent is invoked correctly and kills new
  agent if invocation is incorrect."*
- On the observer's verdicts, verbatim: *"it can either emit 'generic retry' fallback to agent that
  called other agent or if it's confident enough it can re-route the agent by itself emitting some
  signal and letting everyone know that it happened (so we can use it as endpoint and light a
  flashlight or something)."* — the correction signal is meant to be **hookable**, not merely logged.
- On bounding the observer, verbatim: *"the behavior of the handoff … should be adjustable on the
  level of available tools (we will enable some tools and disable other for this model so it will
  surely do only one thing for this scenario) with generic retry option as default."*
- On the woken agent's context, verbatim: *"a salad of things: first is history — tool for long
  history lookup. second is all messages in current history. third is persona sewed from different
  parts: system-prompt, persona (how to talk to user) and agents running along with it (tailored for
  this exact agent)."*
- On pre-handoff prose, verbatim: *"We let user decide if he'd like to keep it. We must try to avoid
  any real reply in this style. For now — don't enforce it and add it for v2 upgrades, it's really
  important."*
- The founder explicitly asked to think about the loop case *"if we're in the loop and observer just
  turns everyone around"* — the `N last handoffs` observer window (D-15) exists for exactly this, and
  the deterministic budget (D-08) is the wall behind it.

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 4-agent-mesh*
*Context gathered: 2026-08-06*
