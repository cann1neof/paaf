# Phase 3: paaf-llm Core (single agent) - Context

**Gathered:** 2026-08-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 builds the **single-agent core of `paaf-llm`**: a Python library that constructs an agent
from a YAML config and holds a real multi-turn conversation with it. In scope: the **port + `fake/`
adapter** (framework hidden behind PAAF types, fake written and merged before the real LangChain/
LangGraph adapter); **model profiles** across Ollama, OpenAI-compatible endpoints and Anthropic —
including two LAN servers as distinct profiles (MODEL-01/02/06); a **single-agent streaming turn**;
**user-defined ordered fallback chains** that survive provider loss and degraded providers
(MODEL-03/04); the **capability manifest + peer-agent graph schema** as inert, validated config
(MODEL-05); **prompt composition** (base prompt + skill fragments) and the **verbatim prompt
inspector** (PERS-01/02/04/05); and the no-framework-types-leak guarantee (MODEL-08). A thin
`paaf chat` CLI and a `paaf prompt` inspector command ship as the human-facing surface.

**Out of scope (moved to their own phases during this discussion):**
- **The agent mesh** — LLM-driven handoff between models, awake-state, context carry-across,
  enumerated-target guard, handoff-chain tracing, optional hard constraints. Now **Phase 4 (Agent
  Mesh)**. Phase 3 only lays the manifest + peer-graph *data*; the graph is inert here.
- **Runtime context composition (PERS-03)** — deferred to **Phase 10 (The Appliance)**, where real
  sources (device name, room) exist. Phase 3 composes base + skill fragments only.
- Tools/MCP/permissions (Phase 5), skills + PyPI release (Phase 6), `MODEL-07` desktop test button
  (Phase 11).
</domain>

<decisions>
## Implementation Decisions

### Chat & inspector CLI surface (SC#2, SC#5)
- **D-01:** **Library-first.** The real deliverable is the `paaf-llm` API (build agent from config,
  run a turn, keep conversation history). `paaf chat` is a **thin interactive CLI wrapper** over
  that API, holding no logic the library doesn't. Multi-turn and fallback behavior are **proven in
  the fake-adapter test suite** (send turn 1, kill/degrade provider, send turn 2, assert the
  conversation continued) — the CLI is not where correctness is established.
- **D-02:** **Prompt inspection ships two entry points, both thin, both calling the same composer:**
  a dry-run **`paaf prompt`** command that composes and prints the exact prompt for the current
  config without a model call, **and** a **`--show-prompt`** flag on `paaf chat` that echoes the
  prompt actually sent alongside the reply.
- **D-03:** The inspector's **default output is the byte-exact prompt as sent** — the literal PERS-04
  guarantee. A separate **opt-in `--provenance`** flag re-renders the *same content* with source
  labels (`base` / `skill:<name>`). The raw view is authoritative; annotation is an audit aid, never
  the default (keeps PERS-04's "exactly as sent, nothing the user didn't write" literally true).

### Fallback triggers & visibility (MODEL-03/04)
- **D-04:** A provider is "degraded enough to fall back" on **connection failure + request timeout +
  HTTP 5xx/429 + slow-first-token** (the first token not arriving within a budget). This covers the
  concrete MODEL-04 case ("local server up but overloaded") without judging response *quality*.
- **D-05:** The **slow-first-token budget is a per-profile setting** with a sane default that must
  **not** false-trigger on a legitimately slow local model. Getting that default right (and whether
  it's a fixed ms or adaptive) is a **research/tuning task** for the planner/researcher.
- **D-06:** Each fallback **trigger reason is recorded in the trace** (SC#4 authoritative record). In
  the thin chat CLI, a fallback shows a **brief inline notice** (e.g. `↳ fell back to <profile>
  (provider 503)`) — honoring "nothing hidden" without noise.

### Capability manifest + peer-graph seam (MODEL-05, reframed)
- **D-07:** Each model profile declares, in YAML, a **natural-language capability manifest** (what it
  handles) and a **peer-agent graph** (which profiles it may hand off to), plus **optional hard
  constraints** (the mesh's control surface, but declarable now). Phase 3 defines and **validates the
  schema** and surfaces it via the CLI, but builds **no handoff behavior** — the graph is **inert
  data** this phase. This is the seam Phase 4 makes live.
- **D-08:** Routing is **not** rule-based. There is deliberately **no deterministic routing-rule DSL
  anywhere** — the founder's architecture is LLM-driven handoff (Phase 4). Do not add routing rules.

### Prompt composition (PERS-01/02/04/05)
- **D-09:** Phase 3 composes **base system prompt (PERS-01) + skill persona fragments (PERS-02)**
  only. **No runtime context (PERS-03)** — see Deferred. Skill fragments in Phase 3 come from a
  fake/stub skill source (real skills are Phase 6); the composition machinery must accept fragments
  now so PERS-02 is exercised end-to-end.
- **D-10:** **PERS-05 is load-bearing and mechanical:** the composed prompt contains nothing the user
  did not write. When Phase 4 adds the generated handoff "explainer," that explainer must appear
  **verbatim in this same inspector** — so the inspector Phase 3 builds is the enforcement point for
  PERS-05 across both phases. Build it to show 100% of what is sent.

### Claude's Discretion (constrained by the decisions above)
- Port abstraction shape (how a turn, streaming, history, and fallback are expressed in PAAF types),
  the LangChain/LangGraph mapping inside `paaf_llm._engine`, the exact CLI framing, YAML schema
  field names, and how history is held (ephemeral in-memory is expected; long-term memory is v2).
  **One design constraint the founder cares about:** shape the port so **Phase 4 handoff can be
  added without redesigning it** (design-level, cheap to honor now; do not build handoff).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope (this phase)
- `.planning/REQUIREMENTS.md` — MODEL-01, 02, 03, 04, 05 (reframed to manifest + peer-graph), 06, 08;
  PERS-01, 02, 04, 05 (PERS-03 deferred to Phase 10). Read the reframed MODEL-05 text and the new
  **Agent Mesh (MESH-01..06)** section to understand what Phase 3 is *setting up* but not building.
- `.planning/ROADMAP.md` §"Phase 3: paaf-llm Core (single agent)" — goal + 5 Success Criteria (the
  contract; `mode: mvp`), and §"Phase 4: Agent Mesh" (what the seam feeds).
- `.planning/ROADMAP.md` §"Notes on Structure" — "The agent mesh is the framework's spine, and it is
  text-first" (why routing is LLM-driven, why the loop lives in `paaf-llm`, why v1 is observability
  not guarantee).

### Phase-1 evidence this phase inherits
- `DECISIONS.md` (repo root) §"Decision: LangChain 1.x + LangGraph STANDS" — the framework choice,
  the port-hides-framework result (61 translation lines either way; 0 framework types in public
  signatures, test-enforced), and the D-19 list of what was deferred to Phase 3 (fallback chains,
  `interrupt()`→confirm, streaming-tool output). SPIKE-05/06 notes: Ollama token counts surface only
  on ~1/334 stream chunks (read after aggregation, not per-chunk).
- `.claude/CLAUDE.md` §"The constraint that makes this decision cheap" (all `langchain*` imports
  confined to `paaf_llm._engine`, CI-enforced via import-linter — already wired in Phase 2),
  §"Decision 1" (fallback mechanisms: `ModelFallbackMiddleware` / `.with_fallbacks()`), and the
  provider table (`init_chat_model("ollama:...")` string→model factory maps 1:1 to a YAML profile).

### Phase-2 assets this phase builds on
- `packages/paaf-core/src/paaf_core/config/schema.py` — the Pydantic `AppConfig`/`ModelConfig` tree
  with per-field `reload_tier` metadata; model profiles + manifest + peer-graph extend this.
- `packages/paaf-core/src/paaf_core/config/store.py` — atomic write + monotonic-revision conflict.
- `packages/paaf-core/src/paaf_core/secrets/` — encrypted `SecretStore` (API keys referenced by key,
  never inline). `packages/paaf-core/src/paaf_core/net/endpoint.py` — endpoint declaration/LAN
  classification (fallback across LAN/WAN profiles must declare endpoints through this).
- `packages/paaf-trace/` — WAL SQLite trace store; SC#4's "which profile served / was it a fallback"
  records here. `packages/paaf-llm/src/paaf_llm/_engine/__init__.py` — the adapter-package marker
  where the LangChain/LangGraph adapter lands (the ONE place framework imports are allowed).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`paaf-core` config/secrets/endpoint/trace subsystems** (Phase 2) are the substrate: extend the
  config schema for profiles + manifest + peer-graph; reference API keys via `SecretStore`; declare
  each profile's endpoint via the endpoint interface; drain runs into the trace store.
- **`paaf_llm._engine` marker package** exists and is whitelisted by the import-linter `forbidden`
  contract — the real adapter goes here and nowhere else.

### Established Patterns (carry as principles)
- **Negative-control discipline** (Phase 1/2): a check that cannot fail is not a check. The
  fake-adapter suite must prove fallback *fires* on each degraded trigger AND that a healthy provider
  does *not* fall back; the "no framework types leak" test must run with the framework uninstalled.
- **Adapter-package confinement is cheap and CI-enforced** — keep all `langchain*` behind the port;
  public API returns only PAAF dataclasses/Pydantic models.

### Integration Points
- `packages/paaf-llm/` is currently a stub (`__init__.py` + empty `_engine`). Phase 3 is where its
  real port, adapters, config extensions, and CLI first appear. Keep it `pip`-installable with no
  voice/audio deps (FOUND-02, defended by the Phase-2 clean-venv wheel job).
</code_context>

<specifics>
## Specific Ideas

- Founder's framing verbatim: the whole framework is **"skills + agents,"** where an **agent is
  another model**; each model carries its own skills and a configurable graph of peer agents. Phase 3
  builds the single-agent half and the *data* for the agent half; Phase 4 makes agents hand off.
- Handoff is a **first-class primitive of the conversation loop**, NOT a tool-registry entry — this
  is why the mesh (Phase 4) precedes tools (Phase 5) and why the port shape matters now.
- Routing reliability is **observability, not a guarantee** (founder accepted): enumerated targets +
  full handoff chain in the trace; a formal mis-route eval is v2 (ROUTE-01).
</specifics>

<deferred>
## Deferred Ideas

- **Agent mesh — LLM-driven handoff, awake-state, context carry-across, enumerated-target guard,
  handoff-chain tracing, optional hard-constraint enforcement, explainer-in-prompt.** → **Phase 4
  (Agent Mesh)**, newly inserted this session. Phase 3 lays only the inert manifest + peer-graph.
- **Runtime context composition (PERS-03)** — time/device/room into the prompt. → **Phase 10 (The
  Appliance)**, where real sources exist. Phase 3 composes base + skill fragments only.
- **Routing-quality / mis-route eval (ROUTE-01)** — scoring whether the awake model routed correctly.
  → **v2**. v1 ships the trace-based observability that makes such an eval possible later.
- **Public PyPI release including the mesh** — the founder decided the first public `paaf-llm` ships
  *with* the mesh. → **Phase 6 (Skills & PyPI Release)**.
</deferred>

---

*Phase: 3-paaf-llm-core*
*Context gathered: 2026-08-04*
