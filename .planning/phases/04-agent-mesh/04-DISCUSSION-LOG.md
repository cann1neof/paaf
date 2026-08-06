# Phase 4: Agent Mesh - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 4-agent-mesh
**Areas discussed:** Handoff signal, Hard constraints (MESH-06), Turn semantics & loop safety, Context carry-across & explainer

---

## Handoff signal

### Q1 — How does the awake model express "hand this to `cook`"?

| Option | Description | Selected |
|--------|-------------|----------|
| In-stream sentinel | Reserved line parsed out of the token stream; works with any provider, trivially scriptable in the fake adapter; but it is text, so it can be emitted by accident and must be stripped before reaching the user | |
| Reserved tool call | One built-in `handoff(target)` via native tool-calling; 30/30 well-formed calls measured on qwen3.5 in Phase 1; but the port grows a tool-call surface one phase before the Phase-5 registry | ✓ (part) |
| Separate router call | A second cheap model call decides routing; cleanest parsing, no stream contamination; but it makes a router — not the awake model — the decider | ✓ (part) |

**User's choice:** Combine 2 and 3 — reserved tool call for handoff (the only tool), **plus an observer**: the smallest model, user-configurable or fully disable-able, that checks whether the agent was invoked correctly and kills an incorrect invocation.
**Notes:** Founder added that the observer "may observe other stuff too, we can figure that one later" — explicitly assigned to v2.

### Q2 — The observer rejects a handoff; what happens to the turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Original agent answers | Handoff killed, awake agent answers, rejection traced | |
| Tell the agent, let it retry | Agent is told why and gets a bounded retry | |
| Surface as an error | Turn fails loudly; a wrong observer call costs the user their answer | |

**User's choice:** The observer *decides*: either emit a "generic retry" back to the calling agent, or — if confident — re-route itself and **emit a signal that a correction happened**.
**Notes:** Verbatim: "so we can use it as endpoint and light a flashlight or something" — the signal must be hookable, not merely logged.

### Q3 — What targets may the observer re-route to?

| Option | Description | Selected |
|--------|-------------|----------|
| Same peer graph as the agent | One graph, one guard; an undeclared target from the observer is the same MESH-02 error | ✓ |
| Any declared profile | Observer sees the whole mesh; but enabling it silently makes every agent reachable from every agent | |
| Its own declared graph | Observer gets its own `peers`; most control, one more thing to keep in sync | |

**User's choice:** Same peer graph as the agent.

### Q4 — Observer on/off by default, and where does its model come from?

| Option | Description | Selected |
|--------|-------------|----------|
| Off by default, opt-in | Nothing runs the user didn't ask for; mesh works with zero extra config | |
| On by default, named profile | Better routing out of the box; costs a second call per handoff | ✓ (extended) |
| On by default, auto-picked | Zero-config; but PAAF choosing a model cuts against "the user owns the mind" | |

**User's choice:** ON by default, occupying a **reserved name in the profile namespace**, deeply configurable down to its system prompt. Its behavior (always-retry / always-reroute / hybrid) is set by **which mesh tools it is granted**, not a mode flag — default grant is generic-retry only.
**Notes:** Verbatim: "we will enable some tools and disable other for this model so it will surely do only one thing for this scenario."

### Q5 — What if no `observer` profile is declared?

| Option | Description | Selected |
|--------|-------------|----------|
| Mesh runs unobserved, says so | Slot is reserved and wired, but PAAF never invents a model to fill it; states the fact at startup and in the trace | ✓ |
| Refuse to start the mesh | Strongest guarantee; costs the simplest two-agent setup a mandatory extra profile | |
| Fall back to the awake profile | Zero config; but a model grading its own decision is the weakest guard | |

**User's choice:** Mesh runs unobserved, says so.

---

## Hard constraints (MESH-06)

### Q1 — What is a hard constraint, mechanically, and what enforces it?

| Option | Description | Selected |
|--------|-------------|----------|
| Two tiers, labelled | Small closed machine-checked set + free-text guidance, clearly distinguished | |
| Free text, observer enforces | No new vocabulary, no D-08 tension; but "enforced regardless" becomes "a second model usually catches it", and it evaporates when unobserved | ✓ |
| Machine-checked only | Every constraint a real guarantee; user loses anything outside the vocabulary | |

**User's choice:** Free text, observer enforces.

### Q2 — Routing-scoped or content-scoped checking in Phase 4?

| Option | Description | Selected |
|--------|-------------|----------|
| Handoff-time only | One call per handoff attempt; content checking is the v2 scope already flagged | ✓ |
| Handoff + every reply | Real content coverage; but a model call on every turn and v2 scope pulled forward | |

**User's choice:** Handoff-time only.

### Q3 — MESH-06/SC#5 say "enforced by the system regardless of what the model attempts." Square that.

| Option | Description | Selected |
|--------|-------------|----------|
| Amend the wording | Say what is true: the peer-graph guard is the one deterministic guarantee; constraints are observer-enforced and unenforced when unobserved | |
| Call the observer "the system" | No doc churn; the observer is a system component and is on by default | ✓ |

**User's choice:** Call the observer "the system."
**Notes:** The tradeoff (a reader may expect determinism) was raised in the option text and the founder decided. Coherent given on-by-default status, with the running-unobserved notice carrying the caveat. Recorded as locked — not to be re-litigated downstream.

### Q4 — What does the observer see when judging?

| Option | Description | Selected |
|--------|-------------|----------|
| Full conversation | Best judgement; but a cloud observer profile then receives the whole conversation on every handoff | |
| Last user turn + manifests | Small, cheap, fast; can't catch a mis-route that only makes sense against earlier context | ✓ (as default) |
| You decide | Leave to researcher/planner | |

**User's choice:** Make it the user's choice. **Default** = last user message + the handoff decision + the agent's reasoning (if any). Configurable to N last messages / N last logs / **N last handoffs**.
**Notes:** Founder raised the loop case unprompted here — "if we're in the loop and observer just turns everyone around" — which drove the next area.

---

## Turn semantics & loop safety

### Q1 — What hard-stops an A→B→A→B loop?

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic hop budget | Engine-enforced counter; at the wall the handoff tool is withdrawn so the agent cannot try | ✓ (part) |
| Cycle detection | Refuses a repeated edge; but a legitimate single hand-back becomes impossible, which MESH-03 wants | |
| Both | Budget as the outer wall + observer shown handoff history so it can break the loop gracefully first | ✓ |

**User's choice:** Both — plus the fallback default model must be determined by the user.

### Q2 — Who is the user-determined fallback default when the budget is exhausted?

| Option | Description | Selected |
|--------|-------------|----------|
| A declared home agent | New mesh-level field; a third concept distinct from `fallback_chain` and `peers` | ✓ |
| Reuse `active_profile` | No new field; but conflates "where a conversation begins" with "who answers when routing fails" | |
| The awake agent answers | Zero config; but the model that just proved confused holds the turn | |

**User's choice:** A declared home agent.

### Q3 — Does the receiving agent answer in the same turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Same turn, announced | Visible `↳ handed off to cook`, matching the existing fallback notice | |
| Same turn, silent | Cleanest output; handoff visible in trace and inspector rather than the reply stream | ✓ |
| Turn ends, user re-asks | Simplest loop; unbearable in Phase 9 voice | |

**User's choice:** Same turn, silent.

### Q4 — What happens to prose emitted before the handoff call?

| Option | Description | Selected |
|--------|-------------|----------|
| Dropped, not in history | Preserved in the trace; keeps history equal to what the user actually saw | |
| Kept in history, not shown | Richer context for the receiving agent; but history diverges from what the user saw | |
| You decide | Leave to the planner | |

**User's choice:** Let the **user** decide via config. Verbatim: "We must try to avoid any real reply in this style. For now — don't enforce it and add it for v2 upgrades, it's really important."

---

## Context carry-across & explainer

### Q1 — What does agent B see when it wakes mid-turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Full history, own persona, told why | B knows it is being handed a live conversation and what for | |
| Full history, own persona, no reason | Less steering; but wastes A's reasoning | |
| History + A's persona too | Full transparency; but A's instructions bleed into B | |

**User's choice:** A three-layer "salad" — (1) long history via a lookup tool, (2) all messages in the current history, (3) a persona sewn from parts: system prompt + persona (how to talk to the user) + the agents running alongside, tailored for that exact agent.

### Q2 — Does Phase 4 build the long-history lookup tool?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave room, build later | Needs the Phase-5 registry and v2 long-term memory; keeps handoff the one mesh tool | ✓ |
| Build it in Phase 4 | Fuller capability; pulls registry + memory into the handoff phase | |

**User's choice:** Leave room, build later.

### Q3 — Who writes the handoff explainer?

| Option | Description | Selected |
|--------|-------------|----------|
| Default template, user-overridable | MESH-04 holds by default, user can still rewrite; verbatim in the inspector either way | ✓ |
| Fixed PAAF template | Guarantees explainer and tool never drift; but one piece of prompt the user cannot rewrite | |
| User writes it per agent | Total ownership; MESH-04's "generated from" stops being true and edits can desync from `peers` | |

**User's choice:** Default template, user-overridable.

### Q4 — Does `paaf prompt` show the observer's prompt (PERS-05)?

| Option | Description | Selected |
|--------|-------------|----------|
| Show every agent, observer included | The complete steering surface one command away | |
| Agents only, observer on request | Cleaner default; the re-router is off-screen unless you ask | |
| Active agent only, as today | Smallest change; but one agent's prompt is no longer the whole story | ✓ |

**User's choice:** Active agent only, as today.

### Q5 — Then how is a non-awake agent's explainer inspectable (SC#3)?

| Option | Description | Selected |
|--------|-------------|----------|
| `paaf prompt --agent <name>` | Default unchanged; explicit flag aims at any profile including the observer | ✓ |
| Only what is awake | Minimal surface; SC#3 satisfiable only by editing config, observer unreachable | |

**User's choice:** `paaf prompt --agent <name>`.

---

## Claude's Discretion

- The exact mesh-private tool-call surface on the port and how `HandoffRequest` is typed.
- Trace schema for the handoff chain (columns vs. table vs. events), subject to full reconstructability.
- Default hop-budget value, default observer window sizes, and where the correction signal surfaces in the headless API.
- Awake-state persistence across user turns and process restarts (not discussed).
- Whether the per-agent system prompt is a new `ModelProfile` field or a reshape of `base_prompt`.

## Deferred Ideas

- Observer duties beyond handoff (reply/content checks, other supervision) → v2.
- Mechanical enforcement of "no prose before a handoff call" → v2, flagged "really important."
- Long-history lookup tool → Phase 5 registry + v2 long-term memory.
- Routing-quality / mis-route eval (ROUTE-01) → v2 (already deferred in Phase 3).
- Awake-state persistence across process restarts → open.
