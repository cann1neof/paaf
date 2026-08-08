# Phase 5: Tools, MCP & Permissions - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The assistant can act on the world and orchestrate its internal workflows through built-in framework tools (mesh handoff, observer control, peer & state inspection), user-defined Python functions via `@tool`, and external MCP servers — with every tool registered in a unified tool registry and carrying a permission tier (`act`, `confirm`, `observe`) that the user can set and override.

Home Assistant and third-party smart home integrations are out of scope / deferred to future external plugins and are NOT shipped out of the box in Phase 5.
</domain>

<decisions>
## Implementation Decisions

### Built-in System Tools (Mesh & Observer Infrastructure)
- **D-01 (Mesh Handoff Built-in Tool):** The `handoff` tool (used by agents in the mesh to delegate execution to a declared peer) is registered as a first-class built-in tool in the unified registry, wired to the Phase-4 mesh handoff loop seam (`TurnResult.handoff`). — **Reversibility:** costly — core mesh execution mechanism.
- **D-02 (Observer Control Built-in Tools):** The Observer model is provisioned with specific built-in decision tools (`approve_handoff`, `veto_handoff`, `reroute_handoff`) so its validation and re-routing of handoffs operate strictly through structured tool calls rather than unconstrained text, aligning with Phase 4's capability-removal principle. — **Reversibility:** costly — observer enforcement loop.
- **D-03 (Mesh & Session Inspection Built-in Tools):** Framework built-ins include system inspection tools such as `list_peers` (queries declared mesh graph and active agent state) and session history lookup helpers, laying the tool infrastructure for long-history lookup. — **Reversibility:** reversible — built-in tool additions.

### Permission Tiers & Spoken Confirmation Loop
- **D-04 (Default Permissions & Clean Spoken Prompt):** By default, all tools are executable by the agent (`act` tier). The user can explicitly enforce a `confirm` check for specific tools in config. When prompting for confirmation, the agent MUST keep the spoken/chat prompt clean and concise (e.g., `"Can I use tool <toolName>?"`) without raw command arguments, file paths, or syntax noise (`/ @ ~ sdhs bullshit`). — **Reversibility:** costly — affects tool execution turn loop in `paaf-session` / `paaf-llm`.
- **D-05 (Trace Event Logging):** Record distinct `tool_call_permission_requested` and `tool_call_permission_granted` / `tool_call_permission_denied` trace events in the `paaf-trace` SQLite store for full auditability. — **Reversibility:** reversible — schema extension in `paaf-trace`.
- **D-06 (Confirmation Timeout & Ambiguity Handling):** On timeout or unrecognized/ambiguous user response during a tool confirmation request, strictly treat as denied, inform the user that the tool invocation was skipped, and continue the turn. — **Reversibility:** reversible — turn loop policy.
- **D-07 (Permission Overrides Config & CLI):** Tool permission overrides can be specified both via `paaf.yaml` mapping under `tools.permissions: { <tool_name>: confirm }` and via interactive CLI (`paaf tools permission <tool> <tier>`) which updates `paaf.yaml`. — **Reversibility:** reversible — config parser & CLI command.

### Unified Registry & MCP Server Config
- **D-08 (MCP Server Config & CLI):** Declare MCP servers in `paaf.yaml` under `mcp_servers:` mapping (supporting stdio command/args/env and SSE URL endpoints) with standard CLI helper `paaf mcp add/list/remove`. — **Reversibility:** costly — config schema and MCP process lifecycle manager in `paaf-llm`.
- **D-09 (Namespacing in Unified Registry):** Flat tool names by default when unique (e.g., `handoff`, `veto_handoff`, `create_issue`), automatically prefixed with `mcp_<server>_<tool>` or `custom_<tool>` if name collisions occur. All tools in the unified registry carry full source metadata (`source`: `builtin` | `custom` | `mcp:<server>`). — **Reversibility:** reversible — internal registry composition logic.
- **D-10 (Non-Blocking Registry Startup):** MCP server launch failures or connection timeouts do not block assistant startup. Failed servers are logged as warnings and marked `offline`/`failed` in the registry status, allowing built-ins and custom tools to function normally; calling a tool on an offline MCP server returns a clean execution error. — **Reversibility:** reversible — error handling in registry loader.
- **D-11 (Tool List CLI Display):** `paaf tools list` CLI outputs a clean simple list view: `tool_name (source, tier)`. — **Reversibility:** reversible — CLI output formatting.

### Custom Tool Decorator API & Defaults
- **D-12 (@tool Decorator Interface):** `@tool` decorator exported directly from `paaf_llm` (`from paaf_llm import tool`). Supports bare `@tool` or `@tool(name="...", description="...", tier="act")`. — **Reversibility:** costly — public API contract for tool authors.
- **D-13 (Schema Generation via Inspection):** Automatic tool schema generation using `inspect.signature` and docstring parsing (supporting standard summary lines and Google/Sphinx parameter descriptions) to infer argument names, types, defaults, and required parameters into JSON Schema. — **Reversibility:** reversible — decorator reflection utility.
- **D-14 (Default Permission Tier):** Unspecified custom `@tool` functions default to `act` tier (executable directly by agent), aligning with D-04. — **Reversibility:** reversible — decorator parameter default.
- **D-15 (Sync & Async Tool Execution):** Support both synchronous and asynchronous functions in `@tool`. `paaf-llm` awaits coroutine functions directly and dispatches synchronous functions to an asyncio thread pool to prevent loop blocking. — **Reversibility:** reversible — execution dispatcher.

### Prompt Injection Defense & Governance
- **D-16 (Prompt Injection Defense via Permission Tiers):** Per TOOL-07, permission tiers (`act`, `confirm`, `observe`) are documented and enforced as the ONLY defense against prompt injection via tool outputs. Zero hidden defensive prompt instructions are allowed in any system prompt, verified by a dedicated CI test. — **Reversibility:** costly — architecture policy & CI assertion.

### Agent Discretion
- Namespacing fallback strategy: flat names when unique, scoped prefix on collision.
- Docstring parsing strategy: `inspect.signature` combined with standard docstring parsing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — TOOL-02..07 (unified tool registry, `@tool` decorator, MCP config, permission tiers, spoken confirmation, prompt injection governance).
- `.planning/ROADMAP.md` §"Phase 5: Tools, MCP & Permissions".

### Prior Phase Decisions & Core Constraints
- `.planning/phases/04-agent-mesh/04-CONTEXT.md` — Mesh handoff seam, Observer tool-based bounding (D-03..D-06, D-14, D-15), peer graph validation.
- `.planning/phases/02-foundation/02-CONTEXT.md` — Secret store (CORE-04, `paaf_core.secrets`) API keys in encrypted store, write-only.
- `.claude/CLAUDE.md` — Tool confinement, zero network/hardware dependencies in CI tests, import boundary rules.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `paaf_llm` package structure: `agent.py`, `mesh.py`, `observer.py`, `compose.py`, and `ports.py` ready for unified tool registry integration.
- `TurnResult.handoff` seam in `ports.py`: the handoff built-in tool directly populates this seam.
- `paaf_core.secrets` & `paaf_core.config`: typed Pydantic config & encrypted secret store ready for MCP server declarations.
- `paaf_trace.store`: SQLite trace store with event queue ready for recording permission request and approval events.

### Established Patterns
- Clean port/adapter architecture with 100% offline testability.
- Capability removal over prompt instructions: observer and mesh handoff governed via tool availability.
- No third-party network calls in default CI test suites.

### Integration Points
- `paaf-llm/src/paaf_llm/agent.py` & `cli.py`: tool execution integration into agent turn loop and `paaf chat` CLI.
</code_context>

<specifics>
## Specific Ideas

- Clean spoken prompt constraint for `confirm` tier: `"Can I use tool <toolName>?"` without raw command/arguments syntax noise.
- Out-of-the-box built-ins focused on Mesh & Observer operations (`handoff`, `approve_handoff`, `veto_handoff`, `reroute_handoff`, `list_peers`).
- Home Assistant is explicitly excluded from out-of-the-box shipping in Phase 5.
</specifics>

<deferred>
## Deferred Ideas

- **Home Assistant integration** — deferred to future plugin release; not included out of the box in Phase 5.
</deferred>

---

*Phase: 5-Tools, MCP & Permissions*
*Context gathered: 2026-08-08*
