# Phase 3: paaf-llm Core (single agent) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-04
**Phase:** 3-paaf-llm Core (single agent)
**Areas discussed:** Chat & prompt-inspector CLI, Fallback triggers, Routing (→ triggered a roadmap revision), Prompt composition & provenance

> **Note:** This discussion triggered a milestone-level roadmap revision. The founder's
> "skills + agents" architecture (LLM-driven model-to-model handoff) was pulled from v2 into
> v1 as a new **Phase 4 (Agent Mesh)**; Phase 3 was rescoped to "single agent"; old Phases
> 4–12 renumbered to 5–13. See ROADMAP.md / REQUIREMENTS.md and the Deferred Ideas below.

---

## Chat & prompt-inspector CLI

| Option | Description | Selected |
|--------|-------------|----------|
| REPL, with one-shot too | Interactive loop + `paaf chat "..."` | |
| REPL only / One-shot only | Single mode | |
| **Reframed:** Library-first, thin CLI | Real deliverable = API; multi-turn/fallback proven in fake suite; `paaf chat` a thin wrapper | ✓ |
| Real product CLI / API+tests only | Alternatives to the reframe | |

**User's choice:** Pushed back on the "REPL" premise; after reframing, chose **library-first,
`paaf chat` as a thin CLI**. Prompt inspection = **both** `paaf prompt` (dry-run) and `--show-prompt`.
**Notes:** Correctly identified that the deliverable is the library, not a CLI; multi-turn is a
library+test concern, `paaf chat` just exercises it.

## Fallback triggers ("degraded")

| Option | Description | Selected |
|--------|-------------|----------|
| Timeout + HTTP 5xx/429 | Conn fail + timeout + server error/overload codes | |
| **Above + slow-first-token** | Also fall back if first token misses a latency budget | ✓ |
| Timeout only | Simplest | |
| Visibility: **brief inline notice + full trace** | One-line CLI note + authoritative trace | ✓ |

**User's choice:** Degraded = conn-fail + timeout + 5xx/429 + slow-first-token; mid-conversation
fallback shows a brief inline notice plus the full trace record.
**Notes:** Flagged that the slow-first-token budget needs a per-profile default that won't
false-trigger on a legitimately slow local model (research/tuning task).

## Routing (intent → profile) — became a roadmap revision

| Option | Description | Selected |
|--------|-------------|----------|
| Keyword/pattern match | Deterministic rules on message text | |
| Explicit per-request tag | Caller/skill tags intent | |
| Small condition DSL | Tiny rule language | |
| **None of these — LLM-driven handoff** | The awake model decides handoffs itself; no rules | ✓ |

**User's choice:** Rejected deterministic routing rules entirely ("no hardcore rules for routing —
forget it"). Routing is the **currently-awake model automatically handing off** to a declared peer.
Chose to **revise the roadmap now** and (after sketching the dependency graph) to **split** single-
agent core (Phase 3) from the mesh (new Phase 4), handoff as a **first-class loop primitive**, public
release **including** the mesh, control surface = **manifest + optional hard constraints**, adherence =
**observability only in v1**, and to **renumber to an integer Phase 4** (4–12 → 5–13).
**Notes:** This is the founder's central architecture ("skills + agents"). Reconciled: an agent = a
model; handoff ≠ tool-registry entry; routing is probabilistic-but-catchable, not guaranteed.

## Prompt composition & provenance

| Option | Description | Selected |
|--------|-------------|----------|
| **Raw exact string + optional annotated view** | Byte-exact default; opt-in `--provenance` labels | ✓ |
| Raw only / Always annotated | Alternatives | |
| Runtime context: Time only (pluggable) | Compose time via a provider seam | |
| Runtime context: Time + static facts | Also user-pinned YAML facts | |
| **Runtime context: none yet (defer PERS-03)** | Base + skill fragments only in Phase 3 | ✓ |

**User's choice:** Inspector prints the raw byte-exact prompt by default with an opt-in annotated
(`--provenance`) view; **no runtime context in Phase 3** — PERS-03 deferred (moved to Phase 10).
**Notes:** Keeps PERS-04 literally true; PERS-03 waits until real sources (device/room) exist.

## Claude's Discretion

- Port abstraction shape, LangChain/LangGraph mapping inside `_engine`, YAML field names, history
  representation (ephemeral in-memory expected). One constraint the founder cares about: shape the
  port so Phase 4 handoff can be added without redesigning it (design-level only; don't build it).
- Slow-first-token budget default and whether it's fixed or adaptive (research task).

## Deferred Ideas

- **Agent mesh** (LLM-driven handoff, awake-state, context carry, enumerated-target guard, handoff-
  chain tracing, hard-constraint enforcement, explainer-in-prompt) → **Phase 4 (Agent Mesh)**, newly
  inserted.
- **Runtime context composition (PERS-03)** → **Phase 10 (The Appliance)**.
- **Routing-quality / mis-route eval (ROUTE-01)** → **v2** (v1 ships observability).
- **PyPI release including the mesh** → **Phase 6**.
