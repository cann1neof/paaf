# Phase 3: paaf-llm Core (single agent) - Research

**Researched:** 2026-08-04
**Domain:** LLM-agent port design, ordered fallback over streaming, YAML model profiles, prompt composition/inspection, LangChain 1.x confined behind a PAAF port
**Confidence:** HIGH on architecture and the fallback finding; MEDIUM on exact LangChain 1.x API surface; the slow-first-token default is an explicit tuning recommendation (D-05).

## Summary

Phase 3 builds the single-agent core of `paaf-llm` as a **library-first** vertical slice: PAAF-typed ports, a `fake/` adapter written and merged **before** the real LangChain/LangGraph adapter, YAML model profiles across Ollama / OpenAI-compatible / Anthropic, user-ordered fallback chains that survive both hard loss and degraded-but-reachable providers, an inert capability-manifest + peer-graph schema, and a byte-exact prompt inspector. Two thin CLI entry points (`paaf chat`, `paaf prompt`) sit on top.

The single most consequential finding: **the fallback loop and the slow-first-token deadline must live in PAAF engine code, not in LangChain's `ModelFallbackMiddleware` or `.with_fallbacks()`.** Three independent reasons force this. (1) `RunnableWithFallbacks` streaming only falls back on failures during *initial stream creation* — a documented limitation — and neither built-in mechanism can express "the first token never arrived within budget," which is a latency trigger over a live stream, not an exception. (2) SC#1 requires the entire suite to pass with the agent framework **uninstalled**; any fallback logic living inside LangChain could not be exercised in that configuration. (3) D-06 requires each fallback trigger reason to drain into the trace, which is cleanest from PAAF code. So the port's real surface is deliberately tiny — a single streaming method that raises PAAF-typed exceptions — and the fallback/deadline/history/composition/trace orchestration is pure, framework-free PAAF code the fake adapter exercises end-to-end.

The second consequential finding: **LangChain/LangGraph are absent from the workspace lockfile entirely** and must be introduced as an **optional extra** (e.g. `paaf-llm[engine]`), never a hard dependency — this is what makes SC#1 (framework uninstalled), FOUND-02 (pip-installable without heavy deps) and MODEL-08 (no framework types leak) all simultaneously satisfiable. The import-linter contract already anticipates the one allowed edge but must be extended to cover `langchain_ollama`/`langchain_anthropic`/`langchain_openai`, which are not yet in its forbidden list.

**Primary recommendation:** Build a one-method `ChatAdapter` port (async streaming, raises PAAF exceptions) + a pure PAAF `Agent` engine that owns the ordered-fallback loop, the per-profile first-token deadline, in-memory history, prompt composition, and trace draining. Write the `fake/` adapter and the full engine test suite first with LangChain uninstalled; add the real adapter behind an optional extra last. Default the slow-first-token budget to a generous, per-profile fixed value (~10 s) paired with startup warmup, not an adaptive scheme.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Library-first. The real deliverable is the `paaf-llm` API (build agent from config, run a turn, keep conversation history). `paaf chat` is a **thin interactive CLI wrapper** holding no logic the library doesn't. Multi-turn and fallback correctness are **proven in the fake-adapter test suite** (send turn 1, kill/degrade provider, send turn 2, assert the conversation continued) — not in the CLI.
- **D-02:** Prompt inspection ships two entry points, both thin, both calling the **same composer**: a dry-run **`paaf prompt`** command that composes and prints the exact prompt without a model call, and a **`--show-prompt`** flag on `paaf chat` that echoes the prompt actually sent alongside the reply.
- **D-03:** The inspector's **default output is the byte-exact prompt as sent** (literal PERS-04). A separate **opt-in `--provenance`** flag re-renders the *same content* with source labels (`base` / `skill:<name>`). The raw view is authoritative; annotation is an audit aid, never the default.
- **D-04:** A provider is "degraded enough to fall back" on **connection failure + request timeout + HTTP 5xx/429 + slow-first-token** (first token not arriving within a budget). Covers the MODEL-04 "local server up but overloaded" case without judging response *quality*.
- **D-05:** The **slow-first-token budget is a per-profile setting** with a sane default that must **not** false-trigger on a legitimately slow local model. Whether it is fixed-ms or adaptive is an explicit **research/tuning task** (addressed below; see Pitfall 2 and Assumptions A1).
- **D-06:** Each fallback **trigger reason is recorded in the trace** (SC#4 authoritative record). The thin chat CLI shows a **brief inline notice** (e.g. `↳ fell back to <profile> (provider 503)`).
- **D-07:** Each model profile declares, in YAML, a **natural-language capability manifest** + a **peer-agent graph** (which profiles it may hand off to) + **optional hard constraints**. Phase 3 defines and **validates the schema** and surfaces it via the CLI, but builds **no handoff behavior** — the graph is **inert data**.
- **D-08:** Routing is **not** rule-based. There is deliberately **no deterministic routing-rule DSL anywhere**. Do not add routing rules.
- **D-09:** Phase 3 composes **base system prompt (PERS-01) + skill persona fragments (PERS-02)** only. **No runtime context (PERS-03)**. Skill fragments come from a **fake/stub skill source** (real skills are Phase 6); the composition machinery must accept fragments now so PERS-02 is exercised end-to-end.
- **D-10:** **PERS-05 is load-bearing and mechanical:** the composed prompt contains nothing the user did not write. The inspector Phase 3 builds is the **enforcement point for PERS-05 across Phase 3 AND Phase 4** (Phase 4's generated handoff explainer must appear verbatim in this same inspector). Build it to show 100% of what is sent.

### Claude's Discretion
- Port abstraction shape (how a turn, streaming, history, and fallback are expressed in PAAF types), the LangChain/LangGraph mapping inside `paaf_llm._engine`, the exact CLI framing, YAML schema field names, and how history is held (ephemeral in-memory expected; long-term memory is v2).
- **One design constraint the founder cares about:** shape the port so **Phase 4 handoff can be added without redesigning it** (design-level, cheap to honor now; do NOT build handoff).

### Deferred Ideas (OUT OF SCOPE)
- **Agent mesh** — LLM-driven handoff, awake-state, context carry-across, enumerated-target guard, handoff-chain tracing, optional hard-constraint *enforcement*, explainer-in-prompt → **Phase 4**. Phase 3 lays only the inert manifest + peer-graph.
- **Runtime context composition (PERS-03)** → **Phase 10**. Phase 3 composes base + skill fragments only.
- **Routing-quality / mis-route eval (ROUTE-01)** → v2. v1 ships trace-based observability only.
- **Public PyPI release including the mesh** → **Phase 6**.
- Tools/MCP/permissions → Phase 5. Skills + PyPI → Phase 6. MODEL-07 desktop test button → Phase 11.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MODEL-01 | User defines named model profiles (provider, model, endpoint, params) with no code | YAML profile schema extending `AppConfig` (§ Capability schema + Pattern 4); reuses Phase-2 config store/validation |
| MODEL-02 | Providers: Ollama, OpenAI-compatible, Anthropic (minimum) | `init_chat_model` provider-string mapping inside `_engine` (Pattern 3); one adapter, three provider strings |
| MODEL-03 | Ordered fallback chain surviving an unreachable provider mid-conversation | PAAF-owned fallback loop over the ordered chain (Pattern 2); connection-failure trigger |
| MODEL-04 | Fallback also on degraded-but-reachable provider | Timeout / 5xx / 429 / slow-first-token triggers, all classified in the adapter and handled by the engine (Pattern 2, Pitfall 1/2) |
| MODEL-05 | Capability manifest (NL) + peer-agent graph declared per profile in YAML, no code | Inert Pydantic schema + cross-field validation, no handoff (Pattern 4) |
| MODEL-06 | Multiple endpoints of the same provider as distinct profiles (two LAN servers) | Two `ollama` profiles with distinct `Endpoint`s via `net/endpoint.py` (Pattern 3, Code Example) |
| MODEL-08 | Public API exposes only PAAF types; suite passes vs fake adapter with framework uninstalled | One-method port + PAAF exception types; optional-extra dependency; framework-uninstalled CI job (Pattern 1, Validation Architecture) |
| PERS-01 | User writes a base system prompt | `PromptComposer` base input from config (Pattern 5) |
| PERS-02 | Active skills contribute persona fragments composing with base | Composer accepts ordered fragments from a fake/stub skill source (Pattern 5, D-09) |
| PERS-04 | Final composed prompt inspectable verbatim, exactly as sent | Single composer feeds both the live path and the inspector; byte-identity test (Pattern 5, Pattern 6) |
| PERS-05 | PAAF never injects instructions the user did not write and cannot see | Composed prompt = base + fragments and nothing else; `join(segments)==sent` invariant test (Pattern 6, Validation Architecture) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Build agent from YAML | `paaf-llm` engine (pure PAAF) | `paaf-core` config | Config validation is Phase-2's; agent construction is new PAAF code, framework-free |
| Provider binding (Ollama/OpenAI/Anthropic) | `paaf_llm._engine` (LangChain) | — | The ONLY place framework types exist; `init_chat_model` lives here |
| Ordered fallback + degraded-trigger detection | `paaf-llm` engine (pure PAAF) | adapter (exception translation only) | Must run with framework uninstalled (SC#1); slow-first-token is a latency policy, not a framework feature |
| First-token deadline over a stream | `paaf-llm` engine (pure PAAF) | — | `asyncio.timeout` around the first `__anext__`; framework cannot express it |
| Conversation history | `paaf-llm` engine (pure PAAF) | — | Ephemeral in-memory list of PAAF `Message` (D-01, Claude's discretion) |
| Prompt composition (base + skill fragments) | `paaf-llm` composer (pure PAAF) | Phase-6 skill source (stubbed now) | Byte-exact string is the enforcement point for PERS-04/05 |
| Prompt inspection (`paaf prompt`, `--show-prompt`, `--provenance`) | thin CLI → same composer | — | D-02/D-03: one composer, two entry points, raw view authoritative |
| Model/API-key resolution | `paaf-core` `SecretStore` | profile `api_key_ref` | CORE-04: keys by reference, never inline, never logged |
| Endpoint declaration / LAN-WAN classification | `paaf-core` `net/endpoint` | each profile | CORE-05: offline enforcement is architectural; each profile declares its endpoint |
| Trace draining (prompt sent, served-by, fallback reason, tokens) | `paaf-trace` `TraceStore` | engine emits events | SC#4 authoritative record; Ollama tokens read post-aggregation (SPIKE-05) |
| Capability manifest + peer graph | `paaf-core` schema (inert data) | Phase-4 mesh (later) | D-07: validated data this phase, live in Phase 4 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Runtime | Workspace pin (3.12.13 resolved); every dep requires ≥3.10 `[VERIFIED: pyproject requires-python >=3.12]` |
| pydantic | 2.13.4 | Profile/manifest/peer-graph schema | Already the Phase-2 config substrate; `extra=forbid` on `AppConfig` `[VERIFIED: uv pip list]` |
| pyyaml | 6.0.3 | YAML tree read/write | Already a workspace dev dep and used by the config store `[VERIFIED: uv pip list]` |
| click | 8.4.2 | Thin CLI (`paaf chat`, `paaf prompt`) | Already installed; standard Python CLI; keep the CLI a thin wrapper (D-01) `[VERIFIED: uv pip list]` |
| rich | 15.0.0 | CLI streaming/inline-notice rendering | Already installed; good for the `↳ fell back` notice + live token stream `[VERIFIED: uv pip list]` |
| paaf-core | 0.1.0 (workspace) | config schema, `SecretStore`, `net/endpoint` | Phase-2 substrate `paaf-llm` builds on |
| paaf-trace | 0.1.0 (workspace) | WAL SQLite trace | SC#4 authoritative record |

### Supporting — the OPTIONAL `[engine]` extra (real adapter only; NOT installed for the fake-adapter suite)
| Library | Version (verify at plan time) | Purpose | When to Use |
|---------|---------|---------|-------------|
| langchain | ~1.3.x | `init_chat_model`, chat-model interface | Real adapter only; confined to `paaf_llm._engine` |
| langgraph | ~1.2.x | Agent runtime (single-agent now; `interrupt()`/handoff land in Phase 4/5) | Real adapter only |
| langchain-ollama | ~1.1.x | Ollama provider binding | Real adapter, local + LAN profiles |
| langchain-anthropic | ~1.4.x | Anthropic provider binding | Real adapter, cloud profile |
| langchain-openai | verify | OpenAI-compatible endpoint binding | Real adapter, OpenAI-compatible profiles (arbitrary `base_url`) |

> **Version note:** CLAUDE.md pins were verified 2026-07-13; the live PyPI publish dates seen this session (langchain 2026-07-16, langgraph 2026-07-28, langchain-anthropic 2026-07-28) are *newer* — LangChain's release cadence is rapid (8 patches in 43 days per Phase-1 notes). The planner must re-pin exact versions at plan time via `pip index versions <pkg>` and record them. `[CITED: CLAUDE.md Recommended Stack; VERIFIED: gsd package-legitimacy publishedAt]`

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PAAF-owned fallback loop | LangChain `ModelFallbackMiddleware` / `.with_fallbacks()` | Rejected — cannot express slow-first-token, `RunnableWithFallbacks` streaming only falls back on initial-creation failure, and logic inside LangChain can't run framework-uninstalled (SC#1). See Don't Hand-Roll note. |
| click | typer | typer is fine but adds a dep; click is already installed and sufficient for a thin CLI |
| in-memory history list | LangGraph checkpointer/persistence | Overkill for Phase 3 ephemeral history (D-01); checkpointer is a Phase-4/`interrupt()` concern |

**Installation (planner wires this):**
```toml
# packages/paaf-llm/pyproject.toml
[project]
dependencies = ["paaf-core", "paaf-trace", "pydantic>=2.13", "pyyaml>=6.0.3", "click>=8.4", "rich>=15"]

[project.optional-dependencies]
engine = ["langchain~=1.3", "langgraph~=1.2", "langchain-ollama~=1.1", "langchain-anthropic~=1.4", "langchain-openai"]

[project.scripts]
paaf = "paaf_llm.cli:main"
```

> **Load-bearing:** the `engine` extra keeps FOUND-02, SC#1 and MODEL-08 simultaneously true. `pip install paaf-llm` (no extra) must import and run the fake adapter with zero LangChain present.

## Package Legitimacy Audit

Ran `gsd-tools query package-legitimacy check --ecosystem pypi ...` this session.

| Package | Registry | Latest publish | Downloads (API) | Source Repo | Verdict | Disposition |
|---------|----------|----------------|-----------------|-------------|---------|-------------|
| langchain | PyPI | 2026-07-16 | unknown (PyPI API limitation) | docs.langchain.com / langchain-ai | SUS (too-new, unknown-downloads) | Approved — pre-vetted in Phase 1 SPIKE-07; rapid release cadence explains "too-new" |
| langgraph | PyPI | 2026-07-28 | unknown | github.com/langchain-ai/langgraph | SUS (too-new, unknown-downloads) | Approved — same |
| langchain-ollama | PyPI | 2026-04-07 | unknown | docs.langchain.com/…/ollama | SUS (unknown-downloads) | Approved |
| langchain-anthropic | PyPI | 2026-07-28 | unknown | docs.langchain.com/…/anthropic | SUS (unknown-downloads) | Approved |
| langchain-openai | PyPI | (verify) | unknown | langchain-ai | verify at plan time | Approve after re-check |
| ollama (py client) | PyPI | — | — | github.com/ollama/ollama-python | OK (used in Phase 1) | Only if the adapter uses it directly; prefer `langchain-ollama` |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged [SUS]:** the LangChain family — but the SUS verdict is driven entirely by (a) "too-new" (an artifact of LangChain's frequent patch cadence — the *latest version* is always days old) and (b) "unknown-downloads" (PyPI's JSON API does not expose weekly downloads). These are **not** slopsquatting signals: real repos, the framework was selected via a Phase-1 spike (SPIKE-05/06/07, DECISIONS.md), and every import is confined behind `_engine` and CI-enforced. **The planner need not add a `checkpoint:human-verify` for these** — they are pre-approved by DECISIONS.md — but MUST pin exact versions at plan time and record them. The genuine residual risk (from DECISIONS.md/CLAUDE.md, unchanged) is that `langchain-mcp-adapters` (0.x) and `langchain-protocol` (0.0.x) are pre-1.0; neither is needed in Phase 3 (MCP is Phase 5).

## Architecture Patterns

### System Architecture Diagram

```
                 YAML config tree (paaf-core AppConfig, validated on read)
                 profiles{}, fallback_chain[], active_profile, base_prompt
                          │
                          ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  paaf_llm.Agent  (PURE PAAF — zero framework imports)             │
   │                                                                    │
   │  build(config, adapter, secret_store, trace) ──► holds history[]  │
   │                                                                    │
   │  turn(user_text):                                                  │
   │    1. PromptComposer.compose(base, [skill fragments]) ─┐          │
   │       (D-09; PERS-01/02) returns byte-exact system str │          │
   │    2. messages = [System(str)] + history + User(text)  │          │
   │    3. FOR profile IN [active] + fallback_chain:         │          │
   │         stream = adapter.stream(profile, messages)      │          │
   │         try: first = await asyncio.timeout(budget) __anext__       │
   │         except (ConnFail|Timeout|HTTP5xx|429|SlowFirstToken):      │
   │              trace.emit(FallbackEvent reason)  ── D-06             │
   │              CLI: "↳ fell back to <next> (<reason>)"              │
   │              continue        ── MODEL-03/04                        │
   │         else: yield first + remaining tokens ── committed profile  │
   │    4. history += assistant reply ; trace.emit(RunEvent)           │
   └───────────┬───────────────────────────────────────────┬──────────┘
               │ port: ChatAdapter.stream(profile, messages)│
               ▼ (raises PAAF exceptions only)              ▼
   ┌────────────────────────┐              ┌─────────────────────────────┐
   │ FakeAdapter (shipped)  │              │ _engine LangChainAdapter     │
   │ scripted tokens/delays │              │ init_chat_model(provider str)│
   │ scripted failures      │              │ endpoint→base_url; key←Secret│
   │ NO langchain import     │              │ translate fw exc → PAAF exc  │
   │ (SC#1 framework-uninst.)│              │ [engine] optional extra      │
   └────────────────────────┘              └──────────┬──────────────────┘
                                                       ▼
                                         Ollama LAN #1 / Ollama LAN #2 /
                                         OpenAI-compatible / Anthropic
```

Byte-exact prompt (step 1) is also what `paaf prompt` prints — same composer, no re-derivation (D-02/D-03).

### Recommended Project Structure
```
packages/paaf-llm/src/paaf_llm/
├── __init__.py          # public API re-exports: Agent, ModelProfile, TurnResult, exceptions — PAAF types only
├── ports.py             # ChatAdapter Protocol + PAAF message/result/exception types (ZERO framework import)
├── agent.py             # Agent engine: fallback loop, first-token deadline, history, trace draining (pure PAAF)
├── compose.py           # PromptComposer: base + ordered skill fragments → byte-exact string + provenance segments
├── profiles.py          # ModelProfile / manifest / peer-graph Pydantic (may live in paaf-core schema instead)
├── fake/                # SHIPPED fake adapter (like paaf-trace/_testing) — written & merged FIRST
│   └── __init__.py      # FakeAdapter: scripted tokens, delays, and every degraded failure
├── cli.py               # thin click CLI: chat / prompt / --show-prompt / --provenance (D-01/D-02)
└── _engine/             # THE ONLY place langchain* may be imported (import-linter whitelisted)
    └── __init__.py      # LangChainAdapter: init_chat_model + exception translation
```

### Pattern 1: One-method port, PAAF exceptions only (MODEL-08, item 1)
**What:** The port is a single async streaming method; all failure modes are PAAF exception types. No framework type appears in any public signature.
**When to use:** The entire adapter boundary.
```python
# ports.py — ZERO framework imports
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator, Literal, Protocol, Sequence

Role = Literal["system", "user", "assistant"]

@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str

class FallbackReason(str, Enum):
    CONNECTION = "connection"        # hard reach failure (MODEL-03)
    TIMEOUT = "timeout"              # request timeout (MODEL-04)
    HTTP_5XX = "http_5xx"            # server error (MODEL-04)
    HTTP_429 = "http_429"            # rate limited / overloaded (MODEL-04)
    SLOW_FIRST_TOKEN = "slow_first_token"  # first token missed the budget (D-04/D-05)

class AdapterError(Exception):
    """Base for all PAAF-typed adapter failures. Carries a FallbackReason."""
    reason: FallbackReason

class ConnectionFailed(AdapterError): reason = FallbackReason.CONNECTION
class RequestTimedOut(AdapterError): reason = FallbackReason.TIMEOUT
class ServerError(AdapterError): reason = FallbackReason.HTTP_5XX
class RateLimited(AdapterError): reason = FallbackReason.HTTP_429
# SlowFirstToken is raised by the ENGINE (deadline), not the adapter.

@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

class ChatAdapter(Protocol):
    def stream(self, profile: "ModelProfile", messages: Sequence[Message]) -> AsyncIterator[str]:
        """Yield reply tokens. Raise a PAAF AdapterError subclass on a degraded/failed provider.
        Final usage is read AFTER aggregation (SPIKE-05) via `last_usage()`."""
        ...
    def last_usage(self) -> Usage: ...
```
**Phase-4 seam (design-only):** `TurnResult` carries a `handoff: HandoffRequest | None` field, `None` in Phase 3. The engine loop already resolves an "awake profile" per turn as a local variable — Phase 4 sets it from a parsed handoff signal + the profile's `peers`. No port method changes.

### Pattern 2: PAAF-owned ordered fallback with a first-token deadline (MODEL-03/04, item 3)
**What:** The engine iterates the user-ordered chain, wraps the first-token wait in a deadline, classifies degraded triggers, records each to the trace, and commits to the first profile that yields a token.
**When to use:** Every `Agent.turn`.
```python
# agent.py — pure PAAF
import asyncio
from .ports import (AdapterError, FallbackReason, Message)

async def _run_chain(self, messages):
    chain = [self.active_profile, *self.fallback_chain]  # ordered (MODEL-03)
    for i, profile in enumerate(chain):
        gen = self.adapter.stream(profile, messages)
        try:
            # deadline covers ONLY time-to-first-token (D-04 slow-first-token; item 4)
            async with asyncio.timeout(profile.first_token_budget_s):
                first = await gen.__anext__()
        except asyncio.TimeoutError:
            self._record_fallback(profile, FallbackReason.SLOW_FIRST_TOKEN)
            await gen.aclose()
            continue
        except AdapterError as e:                 # conn/timeout/5xx/429 (MODEL-04)
            self._record_fallback(profile, e.reason)
            continue
        # committed: this profile served the turn
        yield first
        async for tok in gen:                     # no mid-stream fallback (D-04 scope = first token)
            yield tok
        self._served_by = profile.name
        return
    raise AllProvidersFailed(chain)               # every profile degraded
```
**Note (documented LangChain limitation this avoids):** `RunnableWithFallbacks` "will only be called on failures during the initial stream creation, and errors that occur after a stream starts will not fallback" — so even if used, it could not implement a first-token deadline. `[CITED: github.com/langchain-ai/langchainjs/issues/6026; reference.langchain.com RunnableWithFallbacks]`

### Pattern 3: init_chat_model provider-string mapping, confined to `_engine` (MODEL-01/02/06, item 5)
**What:** One adapter builds a chat model per profile from a provider string; two LAN Ollama servers are two profiles with distinct endpoints.
```python
# _engine/__init__.py — the ONLY langchain import site
from langchain.chat_models import init_chat_model  # 1.x factory
# profile.provider ∈ {"ollama","openai_compatible","anthropic"}  →  provider string
#   ollama:            init_chat_model(f"ollama:{profile.model}", base_url=endpoint_url(profile))
#   openai_compatible: init_chat_model(f"openai:{profile.model}", base_url=endpoint_url(profile),
#                                      api_key=secret_store.get(profile.api_key_ref))
#   anthropic:         init_chat_model(f"anthropic:{profile.model}",
#                                      api_key=secret_store.get(profile.api_key_ref))
```
- MODEL-06: two profiles `{provider: ollama, endpoint: 192.168.1.10:11434}` and `{...: 192.168.1.11:11434}` are distinct; each declares its `Endpoint` via `net/endpoint.py`, both classify LAN.
- API keys: `profile.api_key_ref` names a `SecretStore` key (CORE-04). The key VALUE never lives in YAML and never reaches a log line or the prompt.
- **The adapter must NOT `import httpx` directly** — let `langchain-ollama`/`-anthropic`/`-openai` own the network client, so the framework's `no-network-client` import contract stays green (the client lives in the optional dep, not framework source).

### Pattern 4: Inert capability manifest + peer-graph schema (MODEL-05/D-07, item 6)
**What:** Extend the Pydantic tree with named profiles carrying a natural-language manifest, a peer list, and optional constraints; validate cross-references; build no behavior.
```python
# profiles.py (or paaf-core schema.py) — pydantic v2
from pydantic import BaseModel, Field, model_validator

class ModelProfile(BaseModel):
    model_config = {"extra": "forbid"}
    provider: Literal["ollama", "openai_compatible", "anthropic"]
    model: str
    endpoint_host: str | None = None       # → net.endpoint.Endpoint; None for cloud defaults
    endpoint_port: int | None = None
    endpoint_scheme: str = "http"
    api_key_ref: str | None = None         # name into SecretStore (never the value)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    first_token_budget_s: float = Field(10.0, gt=0.0)   # D-05 default; per-profile (Pitfall 2)
    # --- inert mesh data (D-07/D-08: NL text, NOT a routing DSL) ---
    capabilities: str = ""                 # natural-language manifest
    peers: list[str] = Field(default_factory=list)      # profile names it MAY hand off to (inert)
    constraints: list[str] = Field(default_factory=list)  # optional hard constraints, declarable now

class LlmConfig(BaseModel):
    model_config = {"extra": "forbid"}
    base_prompt: str = ""                  # PERS-01
    active_profile: str
    profiles: dict[str, ModelProfile]
    fallback_chain: list[str] = Field(default_factory=list)   # ordered names (MODEL-03)

    @model_validator(mode="after")
    def _check_refs(self):
        names = set(self.profiles)
        if self.active_profile not in names:
            raise ValueError(f"active_profile '{self.active_profile}' is not a declared profile")
        for n in self.fallback_chain:
            if n not in names: raise ValueError(f"fallback_chain references undeclared profile '{n}'")
        for pname, p in self.profiles.items():
            for peer in p.peers:
                if peer not in names: raise ValueError(f"{pname}.peers references undeclared '{peer}'")
                if peer == pname:     raise ValueError(f"{pname} lists itself as a peer")
        return self
```
- **No handoff behavior.** `peers`/`constraints` are inert data surfaced by the CLI (SC#4). Phase 4 reads `peers` to constrain LLM handoff targets (MESH-02) and enforces `constraints` (MESH-06).
- `capabilities` is deliberately **free text**, not a structured schema — encoding it as fields would smuggle in a routing DSL (violates D-08).
- Reuse the Phase-2 `reload_tier` metadata pattern on new fields (adding a profile ≈ WARM/COLD; changing `provider` ≈ RESTART, matching the existing `ModelConfig.provider` precedent).

### Pattern 5: Single-composer prompt build (PERS-01/02/04, item 7)
**What:** One pure function composes the base prompt + ordered skill fragments into the exact string sent, and also returns labeled segments for `--provenance`.
```python
# compose.py — pure PAAF, deterministic
@dataclass(frozen=True, slots=True)
class Segment:
    source: str        # "base" | f"skill:{name}"
    text: str

class PromptComposer:
    def segments(self, base_prompt: str, fragments: list[tuple[str, str]]) -> list[Segment]:
        segs = [Segment("base", base_prompt)]
        segs += [Segment(f"skill:{name}", text) for name, text in fragments]  # PERS-02, D-09 stub source
        return segs
    def compose(self, base_prompt, fragments) -> str:
        # THE authoritative byte-exact string. The live path and `paaf prompt` both call THIS.
        return "\n\n".join(s.text for s in self.segments(base_prompt, fragments))
```
- The engine sends `compose(...)` verbatim as the system message; `paaf prompt` prints `compose(...)`; `--show-prompt` prints the same. D-02: **one composer, no re-derivation.**
- `--provenance` renders `segments(...)` with `source` labels — the **same** underlying text.
- **PERS-05 invariant (test, Pattern 6):** `"\n\n".join(seg.text for seg in segments) == compose(...)` and `compose(...)` contains base + fragments and **nothing else** — no hidden system text. This is the enforcement point Phase 4's explainer must also satisfy (D-10).
- **No runtime context** (PERS-03 deferred). Fragments come from a fake/stub skill source now (D-09).

### Pattern 6: Trace draining (item 8, D-06, SPIKE-05)
**What:** Drain prompt-sent, served-by profile, each fallback reason, and post-aggregation token counts into `paaf-trace`.
- `RunEvent(prompts=composed_prompt, model=served_by_profile_name, prompt_tokens=…, completion_tokens=…)` — token counts read **after** the stream aggregates (SPIKE-05: Ollama surfaces usage on ~1/334 chunks; a per-chunk read reports `None` 99.7% of the time). Read `adapter.last_usage()` post-turn.
- **Fallback reasons need a home the current schema lacks.** The `runs`/`tool_calls` tables have no fallback/served-by columns. Recommended (planner decides exact shape): add to `paaf-trace` either (a) `served_by TEXT` + `fallback_trail TEXT` (JSON list of `{from,to,reason}`) columns on `runs`, or (b) a dedicated `fallbacks(run_id FK, from_profile, to_profile, reason)` table. **Recommend (a)** — append-mostly, denormalized, no need to surface `lastrowid` from the fire-and-forget writer (the current `TraceStore._writer` does not return the inserted row id, so child-table FKs would require extending the writer; a denormalized column avoids that). This is a small, additive `schema.sql` change — flag as a planned task.

### Anti-Patterns to Avoid
- **Delegating fallback to LangChain middleware/`with_fallbacks`.** Breaks SC#1 (can't run framework-uninstalled), can't express slow-first-token, and `RunnableWithFallbacks` streaming only falls back on stream *creation* failure.
- **Reading token usage per stream chunk.** Reports `None` 99.7% of the time for Ollama (SPIKE-05). Aggregate first.
- **Re-deriving the prompt for the inspector.** Any second code path is a byte-drift risk that silently violates PERS-04. One composer only.
- **Putting `capabilities` into structured fields.** That is a routing DSL by the back door (D-08). Keep it free text.
- **Making LangChain a hard dependency.** Violates FOUND-02, SC#1, MODEL-08. Optional `[engine]` extra only.
- **Counting model cold-load time against the first-token deadline.** Guarantees false triggers on any cold Ollama model (Pitfall 2).
- **Charging a slow-first-token fallback mid-stream.** D-04's slow-first-token is strictly about *reaching* the first token; once tokens flow, do not re-fall-back.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Provider binding across Ollama/OpenAI/Anthropic | A custom multi-provider HTTP client | `init_chat_model` in `_engine` | The 80% PROJECT.md decided not to rebuild; provider breadth is LangChain's value |
| Config validation / atomic write / revision | New YAML parsing + validation | Phase-2 `paaf-core` config store + `AppConfig` | CORE-01/02/03 already done; extend the schema, don't reinvent |
| API-key storage | Keys in YAML or a new store | `paaf-core` `SecretStore` + `api_key_ref` | CORE-04; encrypted, write-only, never logged |
| LAN/WAN classification | ad-hoc `if offline` checks | `net/endpoint.Endpoint.is_lan()` | CORE-05; offline-safe, no DNS |
| Trace persistence | A new log file / DB | `paaf-trace` `TraceStore` | TRACE-01..05; single-writer WAL, off hot path |
| Ordered fallback ITSELF | (this is the exception) | **PAAF engine code** — see rationale | Must run framework-uninstalled + express slow-first-token + record reasons |

**Key insight:** hand-roll exactly one thing — the fallback/deadline orchestration — because the framework's built-ins cannot satisfy D-04's slow-first-token trigger, SC#1's framework-uninstalled requirement, or D-06's per-reason trace. Everything else is delegated to Phase-2 subsystems or LangChain.

## Runtime State Inventory

Not applicable — Phase 3 is greenfield feature work on the Phase-2 substrate, not a rename/refactor/migration. No stored data, live-service config, OS-registered state, or build artifacts carry an old identifier that this phase changes. (New: the optional `[engine]` extra and the `paaf-trace` schema addition are additive, not migrations of existing state.)

## Common Pitfalls

### Pitfall 1: `RunnableWithFallbacks` / middleware cannot see a degraded-but-reachable provider mid-stream
**What goes wrong:** A provider accepts the connection, returns 200, then stalls or 5xx's *after* the stream opens; the built-in fallback never fires.
**Why it happens:** Fallbacks trigger only on failures during initial stream creation `[CITED: langchainjs#6026]`; a slow first token is a latency condition, not an exception at creation.
**How to avoid:** Own the loop (Pattern 2); wrap the first `__anext__` in `asyncio.timeout`; classify `AdapterError` subclasses the adapter raises.
**Warning signs:** A test where a 429-after-200 provider does *not* fall back (this is precisely the negative-control that must pass).

### Pitfall 2: The slow-first-token budget false-triggers on a cold-loaded local model (D-05)
**What goes wrong:** A fixed small budget (e.g. 2 s) fires constantly because the model is cold-loading, not degraded.
**Why it happens:** Ollama unloads models after 5 min (`OLLAMA_KEEP_ALIVE` default); a cold load costs **3–10 s for a 7B model and 60–90 s for a 14B model** before the first token `[CITED: mljourney.com, markaicode.com, vibecodewithkai.substack.com]`. The Phase-1 stack pins `qwen3.5:9b` — squarely in the seconds-to-tens-of-seconds cold-load band.
**How to avoid (recommended two-clock design):**
  1. **Warm/preload each profile at agent build** (Ollama: an empty-prompt load or `keep_alive=-1`), so cold-load is paid once at startup, not charged per turn.
  2. The deadline measures **time-to-first-token on a warm model only**, defaulting to a **generous per-profile fixed `first_token_budget_s ≈ 10 s`** — comfortably above warm prefill even on a slow CPU-hosted local model, yet catching a genuinely stalled/overloaded provider. Cloud profiles may lower it (~5 s).
  3. **Fixed, not adaptive, for the default.** An adaptive EWMA has no history on the first (cold) turn and would trip exactly when a model is legitimately slow; fixed + generous + per-profile + warmup is predictable and honest. Offer adaptive as an opt-in future refinement.
**Warning signs:** Fallbacks firing on turn 1 after idle; a local profile that "works but always falls back." (See Assumptions A1 — this default is a tuning recommendation the founder should confirm.)

### Pitfall 3: import-linter blocks the provider sub-packages, or the httpx contract goes red
**What goes wrong:** The langchain contract whitelists only `langchain`/`langgraph`/`langchain_core`/`langchain_mcp_adapters`; `langchain_ollama`/`_anthropic`/`_openai` are **not in the forbidden list at all** (so they'd be importable anywhere — a leak) and are **not** in the `ignore_imports` whitelist. Separately, the `no-network-client` contract forbids `httpx`.
**Why it happens:** The Phase-2 `.importlinter` predates the real adapter.
**How to avoid:** (a) Add `langchain_ollama`, `langchain_anthropic`, `langchain_openai` to the `langchain` contract's `forbidden_modules`, then add the whitelist `ignore_imports = paaf_llm._engine.* -> langchain*` (and the same for each provider module). (b) Ensure the adapter never `import httpx` directly — the client stays inside the langchain deps, keeping the framework's `no-network-client` claim literally true. Add a negative-control test that a langchain import *outside* `_engine` fails CI (the Phase-2 negcontrol pattern).
**Warning signs:** CI green even though a `langchain_ollama` import sits in `cli.py`.

### Pitfall 4: The framework-uninstalled suite silently imports LangChain
**What goes wrong:** `ports.py`/`agent.py`/`compose.py`/`fake/` transitively import `_engine`, so `pip install paaf-llm` (no extra) fails at import, breaking SC#1.
**Why it happens:** A convenience re-export in `__init__.py` that pulls in `_engine`.
**How to avoid:** `_engine` is imported **lazily**, only when the real adapter is explicitly constructed. `paaf_llm.__init__` re-exports only PAAF types + `FakeAdapter`. A CI job installs the wheel **without** `[engine]` and runs the full suite (extends the Phase-2 clean-venv wheel job).
**Warning signs:** `ImportError: No module named 'langchain'` when running the fake-adapter suite.

### Pitfall 5: Trace child-rows need a run id the fire-and-forget writer doesn't return
**What goes wrong:** Attaching per-fallback rows to a run requires `runs.id`, but `TraceStore.emit`/`_writer` are fire-and-forget and never surface `lastrowid`.
**Why it happens:** The Phase-2 writer is intentionally non-blocking (hot-path safety).
**How to avoid:** Prefer denormalized `served_by` + `fallback_trail` (JSON) columns on `runs` (Pattern 6), avoiding a child table and the need for `lastrowid`. If a `fallbacks` table is chosen instead, the writer must be extended to return/assign ids — a larger change; call it out explicitly.

## Code Examples

### Two LAN Ollama servers as distinct profiles + a cloud fallback (YAML)
```yaml
# the one config tree (paaf-core), extended by Phase 3
llm:
  base_prompt: "You are the user's assistant."     # PERS-01
  active_profile: "kitchen-local"
  fallback_chain: ["study-local", "cloud"]          # ordered (MODEL-03)
  profiles:
    kitchen-local:                                   # MODEL-06: LAN server #1
      provider: ollama
      model: "qwen3.5:9b"
      endpoint_host: "192.168.1.10"
      endpoint_port: 11434
      first_token_budget_s: 10.0                     # D-05, generous local default
      capabilities: "General chat; runs on the kitchen mini-PC."   # NL manifest (D-07)
      peers: ["study-local"]                         # inert this phase
    study-local:                                     # MODEL-06: LAN server #2 (same provider!)
      provider: ollama
      model: "qwen3.5:9b"
      endpoint_host: "192.168.1.11"
      endpoint_port: 11434
    cloud:                                           # MODEL-02: Anthropic
      provider: anthropic
      model: "claude-...."                           # planner pins
      api_key_ref: "anthropic_api_key"               # CORE-04, value in SecretStore
      first_token_budget_s: 5.0
```

### The fake adapter's degraded-trigger surface (item 2)
```python
# fake/__init__.py — SHIPPED, zero framework imports (SC#1)
class FakeAdapter:                        # implements ChatAdapter
    def program(self, profile_name, *, tokens=None, fail=None, first_token_delay_s=0.0): ...
    #   fail ∈ {ConnectionFailed, RequestTimedOut, ServerError, RateLimited}  → raise on stream
    #   first_token_delay_s > budget      → engine's asyncio.timeout fires SLOW_FIRST_TOKEN
    #   tokens=[...]                       → deterministic streaming for multi-turn/history tests
```
This lets the suite prove, offline and deterministically: multi-turn history carries across a fallback (D-01), fallback FIRES on each of the four degraded triggers, and a HEALTHY profile does NOT fall back (negative control).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| "STT is a non-issue" note | Whisper locks to one language per clip (SPIKE-04) | Phase 1 | Not Phase 3, but bounds public claims |
| Pydantic AI as a contender | LangChain 1.x + LangGraph STANDS (falsifier fired negative, SPIKE-06) | Phase 1 (DECISIONS.md) | Phase 3 uses LangChain; recoverable for ~250 lines if wrong |
| `create_agent` scare (deleted in 1.1.0) | Stale-venv artifact; 1.0 no-breaking-change policy holds | 2025→2026 | Version stability is real; still pin exact |
| Middleware/`with_fallbacks` for resilience | PAAF-owned loop (this phase) | Phase 3 | Required by slow-first-token + SC#1 |

**Deprecated/outdated:**
- PyAudio, per-language voice switching, Kokoro/XTTS — not relevant to Phase 3 (voice phases).
- Reading LangChain token usage per-chunk for Ollama — superseded by post-aggregation read (SPIKE-05).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Slow-first-token default of **~10 s fixed, per-profile, with startup warmup** (not adaptive) | Pitfall 2, Pattern 4 | If too low, false fallbacks on slow local models (the exact D-05 failure); if too high, a genuinely dead provider is tolerated too long. **D-05 explicitly makes this a tuning task — founder should confirm the number.** `[ASSUMED]` |
| A2 | Exact LangChain 1.x symbol paths (`init_chat_model` import location, `asyncio.timeout` interplay with `astream`) | Pattern 3 | Minor: adapter wiring detail; verify against the pinned version's docs at plan time. `[ASSUMED]` |
| A3 | Trace fallback record via denormalized `served_by`+`fallback_trail` columns on `runs` | Pattern 6, Pitfall 5 | Schema-shape choice; a `fallbacks` child table is the alternative but needs writer changes. Planner decides. `[ASSUMED]` |
| A4 | YAML field names (`profiles`, `fallback_chain`, `first_token_budget_s`, `peers`, `capabilities`) | Pattern 4 | Cosmetic — Claude's discretion per CONTEXT; no downstream contract depends on exact names yet. `[ASSUMED]` |
| A5 | LangChain provider strings `ollama:`/`openai:`/`anthropic:` map 1:1 to profiles with `base_url`/`api_key` kwargs | Pattern 3 | If a provider needs different plumbing (e.g. OpenAI-compatible base_url quirks), the adapter absorbs it — no public API change. `[CITED: CLAUDE.md provider table]` / partially `[ASSUMED]` |
| A6 | Exact pinned versions of the `[engine]` packages | Standard Stack | Must be re-pinned via `pip index versions` at plan time; CLAUDE.md pins are 2026-07-13, live publishes are newer. `[ASSUMED]` |

## Open Questions

1. **Fallback vs. mesh peer-graph — are they the same list?**
   - What we know: `fallback_chain` (resilience, MODEL-03) and `peers` (handoff targets, MODEL-05/Phase-4) are conceptually distinct — fallback is "same request, different provider on failure"; handoff is "different agent, by the awake model's choice."
   - What's unclear: whether the founder wants them modeled as one field or two. CONTEXT treats them separately (D-04 vs D-07).
   - Recommendation: keep them **separate fields** (as in Pattern 4). They have different semantics and Phase 4 only touches `peers`.

2. **Does a warm-up/preload step belong in Phase 3 or is it a config-only default?**
   - What we know: warmup is the clean fix for Pitfall 2.
   - What's unclear: whether the founder wants an explicit `agent.warmup()` API now (useful later for VOICE-10's warmup contract) or just a documented `keep_alive` recommendation.
   - Recommendation: add a minimal `warmup()` on the engine now (cheap, reused by Phase 8/VOICE-10), defaulting to preloading `active_profile` + chain.

3. **Should the OpenAI-compatible provider be `langchain-openai` with `base_url`, or the generic `openai:` string?**
   - Recommendation: verify at plan time; `langchain-openai` with an arbitrary `base_url` is the documented path for OpenAI-compatible endpoints. Absorbed by the adapter regardless.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | everything | ✓ | 3.12.13 | — |
| pydantic / pyyaml / click / rich | schema + CLI | ✓ | 2.13.4 / 6.0.3 / 8.4.2 / 15.0.0 | — |
| paaf-core / paaf-trace (workspace) | substrate | ✓ | 0.1.0 | — |
| LangChain `[engine]` extra | real adapter only | ✗ (absent from lockfile) | — | **Fake adapter** — the entire test suite runs without it (SC#1) |
| Ollama running on LAN | live `paaf chat` against a real local model | ✗ (dev harness, no server assumed) | — | Fake adapter for tests; real run is user-provided at their own LAN |

**Missing dependencies with no fallback:** none for the phase's testable scope.
**Missing dependencies with fallback:** LangChain (fake adapter covers all CI); a live Ollama/cloud provider (only needed for a manual smoke of the real adapter, not for the graded suite).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode=auto`) `[VERIFIED: root pyproject]` |
| Config file | `/pyproject.toml` `[tool.pytest.ini_options]` — `--disable-socket --allow-unix-socket --import-mode=importlib`, `testpaths=["packages"]` |
| Quick run command | `uv run pytest packages/paaf-llm -q` |
| Full suite command | `uv run pytest -q` |
| Framework-uninstalled job | install `paaf-llm` wheel **without** `[engine]`, then `uv run pytest --pyargs paaf_llm` (extends the Phase-2 clean-venv wheel job, Plan 02-03) |

### Phase Requirements → Test Map (negative-control discipline)
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MODEL-08/SC#1 | Full suite passes with LangChain uninstalled | integration | `pytest --pyargs paaf_llm` in a venv without `[engine]` | ❌ Wave 0 |
| MODEL-08 | No framework type in any public signature | unit | `pytest packages/paaf-llm/tests/test_no_leak.py` (assert `__init__` exports + `inspect.signature` are PAAF-typed) | ❌ Wave 0 |
| MODEL-03 | Fallback FIRES on connection failure mid-conversation; history carries across | unit | `pytest -k test_fallback_connection` | ❌ Wave 0 |
| MODEL-04 | Fallback FIRES on timeout, on 5xx, on 429, on slow-first-token (4 positive tests) | unit | `pytest -k "test_fallback_degraded"` | ❌ Wave 0 |
| MODEL-04 | **Negative control:** a HEALTHY provider does NOT fall back | unit | `pytest -k test_healthy_no_fallback` | ❌ Wave 0 |
| MODEL-05 | Undeclared peer / fallback target rejected at config load | unit | `pytest -k test_peer_validation` (expects `ValidationError`) | ❌ Wave 0 |
| MODEL-06 | Two same-provider LAN profiles are distinct and each classifies LAN | unit | `pytest -k test_two_lan_profiles` | ❌ Wave 0 |
| PERS-04 | `paaf prompt` / `--show-prompt` output == the string the engine sent (byte-identity) | unit | `pytest -k test_prompt_byte_exact` | ❌ Wave 0 |
| PERS-05 | Composed prompt == base + fragments and nothing else; `join(segments)==compose()` | unit | `pytest -k test_no_hidden_prompt` | ❌ Wave 0 |
| D-06 | Each fallback trigger reason lands in the trace | integration | `pytest -k test_fallback_traced` | ❌ Wave 0 |
| SPIKE-05 tie-in | Token usage read post-aggregation is non-None (fake reports usage once) | unit | `pytest -k test_usage_aggregated` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest packages/paaf-llm -q` (fake-adapter unit suite; sub-second, no network).
- **Per wave merge:** `uv run pytest -q` (whole workspace).
- **Phase gate:** full suite green **AND** the framework-uninstalled job green (SC#1 is not satisfied until both pass).

### Wave 0 Gaps
- [ ] `packages/paaf-llm/tests/conftest.py` — shared `FakeAdapter` programming fixtures + a `TraceStore` fixture (async).
- [ ] `packages/paaf-llm/tests/test_no_leak.py` — public-signature PAAF-only assertion.
- [ ] `packages/paaf-llm/tests/test_fallback.py` — 4 positive triggers + 1 healthy negative control + history-carries-across.
- [ ] `packages/paaf-llm/tests/test_prompt.py` — byte-exact + no-hidden-prompt invariants.
- [ ] `packages/paaf-llm/tests/test_profiles.py` — peer/fallback/active cross-ref validation.
- [ ] CI: a framework-uninstalled job (extend `.github/workflows/ci.yml` wheel job to run the full `paaf_llm` suite without `[engine]`).
- [ ] `.importlinter`: add the `_engine` whitelist + the three provider modules to `forbidden_modules`; a negcontrol proving a stray provider import fails CI.
- [ ] `paaf-trace/schema.sql`: additive `served_by` + `fallback_trail` columns (or a `fallbacks` table) + a schema test.

## Security Domain

`security_enforcement: true`, ASVS level 1. Phase 3 is a headless library; the relevant surface is config/secret handling and the injection posture the project has *already committed to*.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth in this headless library (pairing is Phase 10/11) |
| V3 Session Management | no | Ephemeral in-memory history only; no sessions |
| V4 Access Control | partial | Peer/fallback cross-ref validation rejects undeclared targets at load (data-integrity, not authz); real handoff guard is Phase 4 (MESH-02) |
| V5 Input Validation | **yes** | Pydantic `AppConfig`/`LlmConfig` with `extra=forbid` validates the YAML tree on every read/write (CORE-01, reused) |
| V6 Cryptography | **yes (never hand-roll)** | API keys via `paaf-core` `SecretStore` (Fernet) by `api_key_ref`; never in YAML, never logged (CORE-04) |
| V7 Errors & Logging | **yes** | The prompt inspector prints the system prompt, which by construction contains no secrets (keys live in `SecretStore`, not the prompt); ensure adapter errors do not echo an `api_key` value |

### Known Threat Patterns for a provider-binding LLM library
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key leaking into YAML, logs, or the prompt inspector | Information Disclosure | `api_key_ref` indirection (CORE-04); a test asserting no secret value appears in composed prompt / trace / logs |
| Prompt injection via (future) tool results | Tampering | **Out of scope for Phase 3** — the permission model is the *only* documented defense (TOOL-07, Phase 5); PERS-05 forbids hidden defensive instructions. Do NOT add any hidden guard text. |
| Slopsquatted/hallucinated LangChain sub-package | Supply chain | Package Legitimacy Audit above; pin exact versions; imports confined + CI-enforced |
| A cloud profile silently used under offline mode | Policy violation | Each profile declares its `Endpoint`; `net/endpoint.non_lan_endpoints()` is what Phase-10 APP-08 refuses. Phase 3 must register profile endpoints so the registry sees them. |
| Config `extra` field smuggling a routing rule | Tampering | `extra=forbid` on every model; `capabilities` is free text, no rule DSL (D-08) |

## Sources

### Primary (HIGH confidence)
- `.planning/REQUIREMENTS.md` — MODEL-01..08, PERS-01..05, MESH-01..06 (what Phase 3 sets up).
- `.planning/ROADMAP.md` §Phase 3 / §Phase 4 / §"Notes on Structure" — the 5 Success Criteria, the mesh-is-the-spine framing.
- `DECISIONS.md` §"Agent-framework decision" — SPIKE-05 (Ollama usage post-aggregation, 1/334 chunks), SPIKE-06 (MCP falsifier negative), SPIKE-07 (0 framework types in public signatures, 61 translation lines either way; recoverable for ~250 lines), D-19 deferrals (fallback chains, `interrupt()`→confirm).
- `.claude/CLAUDE.md` §Decision 1 + §"The constraint that makes this decision cheap" — `init_chat_model` string factory, fallback mechanisms, `langchain*` confined to `_engine` (CI-enforced).
- Phase-2 source read directly: `paaf-core/config/schema.py`, `net/endpoint.py`, `secrets/interface.py`, `paaf-trace/store.py`+`schema.sql`, `.importlinter`, `paaf-llm/pyproject.toml` — the exact substrate this phase extends.

### Secondary (MEDIUM confidence)
- `reference.langchain.com` RunnableWithFallbacks / ModelFallbackMiddleware — API existence and shape.
- `github.com/langchain-ai/langchainjs#6026` + deepagents#2154, langchain#33129 — `RunnableWithFallbacks` streaming limitation and middleware/fallback interaction issues.
- Ollama cold-start latency: mljourney.com, markaicode.com, vibecodewithkai.substack.com — 3–10 s (7B) / 60–90 s (14B) cold load; 5-min default keep-alive.

### Tertiary (LOW confidence)
- LangChain `[engine]` exact version pins — must be re-verified at plan time (`pip index versions`).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — core deps verified installed; the `[engine]` extra is the right shape (LangChain chosen in Phase 1), exact pins pending.
- Architecture (one-method port + PAAF-owned fallback): HIGH — forced by SC#1 + D-04 + D-06, cross-checked against the documented `RunnableWithFallbacks` streaming limitation.
- Fallback mechanism finding: HIGH — three independent reasons converge; the streaming limitation is cited.
- Slow-first-token default: MEDIUM — grounded in cited Ollama cold-start data, but the exact number is a tuning recommendation (D-05, Assumptions A1).
- Capability/peer schema: HIGH — a straightforward Pydantic extension of the Phase-2 tree; validation rules are unambiguous (D-07/D-08).
- Trace integration: MEDIUM — requires a small additive schema change whose exact shape the planner picks (Assumptions A3).

**Research date:** 2026-08-04
**Valid until:** ~2026-09-04 for architecture (stable); ~2026-08-18 for LangChain version pins (fast-moving — re-pin at plan time).
