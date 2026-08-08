# Phase 5: Tools, MCP & Permissions - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The assistant can act on the world through built-ins (timers, alarms, weather, music), a plain decorated Python function (`@tool`), and an MCP server — with every tool carrying a permission tier (`act`, `confirm`, `observe`) that the user can set and override.
</domain>

<decisions>
## Implementation Decisions

### Permission Tiers & Spoken Confirmation Loop
- **D-01:** By default all tools are executable by the agent (`act` tier). The user can explicitly enforce a `confirm` check for specific tools in config. When prompting for confirmation, the agent MUST keep the spoken/chat prompt clean and concise (e.g., `"Can I use tool <toolName>?"`) without raw command arguments, file paths, or syntax noise (`/ @ ~ sdhs bullshit`). — **Reversibility:** costly — affects tool execution turn loop in `paaf-session` / `paaf-llm`.
- **D-02:** Record distinct `tool_call_permission_requested` and `tool_call_permission_granted` / `tool_call_permission_denied` trace events in the `paaf-trace` SQLite store for full auditability. — **Reversibility:** reversible — schema extension in `paaf-trace`.
- **D-03:** On timeout or unrecognized/ambiguous user response during a tool confirmation request, strictly treat as denied, inform the user that the tool invocation was skipped, and continue the turn. — **Reversibility:** reversible — turn loop policy.
- **D-04:** Tool permission overrides can be specified both via `paaf.yaml` mapping under `tools.permissions: { <tool_name>: confirm }` and via interactive CLI (`paaf tools permission <tool> <tier>`) which updates `paaf.yaml`. — **Reversibility:** reversible — config parser & CLI command.

### Unified Registry & MCP Server Config
- **D-05:** Declare MCP servers in `paaf.yaml` under `mcp_servers:` mapping (supporting stdio command/args/env and SSE URL endpoints) with standard CLI helper `paaf mcp add/list/remove`. — **Reversibility:** costly — config schema and MCP process lifecycle manager in `paaf-llm`.
- **D-06:** Flat tool names by default when unique (e.g., `timer_set`, `create_issue`), automatically prefixed with `mcp_<server>_<tool>` or `custom_<tool>` if name collisions occur. All tools in the unified registry carry full source metadata (`source`: `builtin` | `custom` | `mcp:<server>`). — **Reversibility:** reversible — internal registry composition logic.
- **D-07:** MCP server launch failures or connection timeouts do not block assistant startup. Failed servers are logged as warnings and marked `offline`/`failed` in the registry status, allowing built-ins and custom tools to function normally; calling a tool on an offline MCP server returns a clean execution error. — **Reversibility:** reversible — error handling in registry loader.
- **D-08:** `paaf tools list` CLI outputs a clean simple list view: `tool_name (source, tier)`. — **Reversibility:** reversible — CLI output formatting.

### Custom Tool Decorator API & Defaults
- **D-09:** `@tool` decorator exported directly from `paaf_llm` (`from paaf_llm import tool`). Supports bare `@tool` or `@tool(name="...", description="...", tier="act")`. — **Reversibility:** costly — public API contract for tool authors.
- **D-10:** Automatic tool schema generation using `inspect.signature` and docstring parsing (supporting standard summary lines and Google/Sphinx parameter descriptions) to infer argument names, types, defaults, and required parameters into JSON Schema. — **Reversibility:** reversible — decorator reflection utility.
- **D-11:** Unspecified custom `@tool` functions default to `act` tier (executable directly by agent), aligning with D-01. — **Reversibility:** reversible — decorator parameter default.
- **D-12:** Support both synchronous and asynchronous functions in `@tool`. `paaf-llm` awaits coroutine functions directly and dispatches synchronous functions to an asyncio thread pool to prevent loop blocking. — **Reversibility:** reversible — execution dispatcher.

### Built-in Tools & Home Assistant Skill
- **D-13:** Built-in tools ship in `paaf_llm.tools.builtin` featuring an in-memory asyncio Timer/Alarm manager and mockable Weather/Music adapters to support 100% offline, hardware-free CI testing. — **Reversibility:** costly — builtin tool module structure.
- **D-14:** Home Assistant example skill (`paaf-skill-homeassistant`) is a standalone tool package driving HA REST/WebSocket APIs via `httpx`/`aiohttp`, with strictly ZERO dependency on the `homeassistant` Python package in `paaf-llm` core dependencies. — **Reversibility:** costly — skill boundary and dependencies.
- **D-15:** Home Assistant API credentials (`HA_URL`, `HA_TOKEN`) are loaded from `paaf_core.secrets` (encrypted secret store via `paaf secrets set`), with fallback to environment variables (`HA_URL`, `HA_TOKEN`). — **Reversibility:** reversible — credential resolver.
- **D-16:** Per TOOL-07, permission tiers (`act`, `confirm`, `observe`) are documented and enforced as the ONLY defense against prompt injection via tool outputs. Zero hidden defensive prompt instructions are allowed in any system prompt, verified by a dedicated CI test. — **Reversibility:** costly — architecture policy & CI assertion.

### Agent Discretion
- Namespacing fallback strategy: flat names when unique, scoped prefix on collision.
- Docstring parsing strategy: `inspect.signature` combined with standard docstring parsing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — TOOL-01..08 (the 8 Phase-5 tool, MCP, and permission requirement IDs).
- `.planning/ROADMAP.md` §"Phase 5: Tools, MCP & Permissions" — goal and the 5 Success Criteria.

### Prior Phase Decisions & Core Constraints
- `.planning/phases/02-foundation/02-CONTEXT.md` — Secret store (CORE-04, `paaf_core.secrets`) API keys in encrypted store, write-only.
- `.claude/CLAUDE.md` — Tool confinement, zero network/hardware dependencies in CI tests, import boundary rules.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `paaf_llm` package structure: contains existing agent turn loop, profile parser, and engine adapters ready for tool integration.
- `paaf_core.secrets` & `paaf_core.config`: typed Pydantic config & encrypted secret store ready for MCP server declarations and HA credentials.
- `paaf_trace.store`: SQLite trace store with event queue ready for recording permission request and approval events.

### Established Patterns
- Clean port/adapter architecture with 100% offline testability.
- No third-party network calls in default CI test suites.

### Integration Points
- `paaf-llm/src/paaf_llm/agent.py` & `cli.py`: tool execution integration into agent turn loop and `paaf chat` CLI.
</code_context>

<specifics>
## Specific Ideas

- Clean spoken prompt constraint for `confirm` tier: `"Can I use tool <toolName>?"` without raw command/arguments syntax noise.
</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.
</deferred>

---

*Phase: 5-Tools, MCP & Permissions*
*Context gathered: 2026-08-08*
