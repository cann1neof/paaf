# Phase 5: Tools, MCP & Permissions - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The assistant can act on the world, navigate its mesh network, and query its operational history through always-on built-in framework tools (`handoff`, observer control tools, `date_time_lookup`, `history_lookup`), user-defined Python functions via `@tool`, and external MCP servers — with every tool registered in a unified tool registry carrying a permission tier (`act`, `confirm`, `observe`) set and overridden by the user.

Peer graph awareness is fed directly into system prompts of each agent (no `list_peers` tool). Third-party domain tools (e.g., Home Assistant, weather APIs, music players) are NOT built-in out of the box — they are provided by end-users via `@tool` decorators or MCP servers.
</domain>

<decisions>
## Implementation Decisions

### Always-On Built-in System Tools
- **D-01 (Peer Graph in System Prompt):** Peer graph awareness is fed directly into the system prompt of each agent during prompt composition (`compose.py`). A `list_peers` tool is explicitly NOT used — agents always know their available peers from their system prompt. — **Reversibility:** costly — system prompt composition architecture.
- **D-02 (Mesh Handoff Tool):** The `handoff` tool (used by agents in the mesh to delegate turn execution to a declared peer) is an always-on built-in tool in the unified registry, backing the Phase-4 mesh handoff loop seam (`TurnResult.handoff`). — **Reversibility:** costly — core mesh execution mechanism.
- **D-03 (Observer Control Tools):** The Observer model is provisioned with always-on decision tools (`approve_handoff`, `veto_handoff`, `reroute_handoff`) so its validation and re-routing of handoffs operate strictly through structured tool calls rather than unconstrained text. — **Reversibility:** costly — observer enforcement loop.
- **D-04 (Date & Time Lookup Tool):** An always-on `date_time_lookup` built-in tool provides current local and UTC date, time, day of week, and timezone offsets to any agent. — **Reversibility:** reversible — built-in tool implementation.
- **D-05 (Deep History & Event Log Lookup Tool):** An always-on `history_lookup` built-in tool queries `paaf-trace` for timestamped records of:
  1. Past conversations (User requests + resolutions across sessions)
  2. Past tool calls and their arguments/results
  3. Passive / background custom event logs (e.g. music track start events, system notifications, emails) that occurred outside the active conversation session.
  This allows users to ask the assistant about out-of-band events and historical actions that were not part of the active turn context. — **Reversibility:** costly — core framework trace store query feature.

### Permission Tiers & Spoken Confirmation Loop
- **D-06 (Default Permissions & Clean Spoken Prompt):** By default, all tools are executable by the agent (`act` tier). The user can explicitly enforce a `confirm` check for specific tools in config. When prompting for confirmation, the agent MUST keep the spoken/chat prompt clean and concise (e.g., `"Can I use tool <toolName>?"`) without raw command arguments, file paths, or syntax noise (`/ @ ~ sdhs bullshit`). — **Reversibility:** costly — affects tool execution turn loop in `paaf-session` / `paaf-llm`.
- **D-07 (Trace Event Logging):** Record distinct `tool_call_permission_requested` and `tool_call_permission_granted` / `tool_call_permission_denied` trace events in the `paaf-trace` SQLite store for full auditability. — **Reversibility:** reversible — schema extension in `paaf-trace`.
- **D-08 (Confirmation Timeout & Ambiguity Handling):** On timeout or unrecognized/ambiguous user response during a tool confirmation request, strictly treat as denied, inform the user that the tool invocation was skipped, and continue the turn. — **Reversibility:** reversible — turn loop policy.
- **D-09 (Permission Overrides Config & CLI):** Tool permission overrides can be specified both via `paaf.yaml` mapping under `tools.permissions: { <tool_name>: confirm }` and via interactive CLI (`paaf tools permission <tool> <tier>`) which updates `paaf.yaml`. — **Reversibility:** reversible — config parser & CLI command.

### Unified Registry & MCP Server Config
- **D-10 (MCP Server Config & CLI):** Declare MCP servers in `paaf.yaml` under `mcp_servers:` mapping (supporting stdio command/args/env and SSE URL endpoints) with standard CLI helper `paaf mcp add/list/remove`. — **Reversibility:** costly — config schema and MCP process lifecycle manager in `paaf-llm`.
- **D-11 (Namespacing in Unified Registry):** Flat tool names by default when unique (e.g., `handoff`, `history_lookup`, `date_time_lookup`, `create_issue`), automatically prefixed with `mcp_<server>_<tool>` or `custom_<tool>` if name collisions occur. All tools in the unified registry carry full source metadata (`source`: `builtin` | `custom` | `mcp:<server>`). — **Reversibility:** reversible — internal registry composition logic.
- **D-12 (Non-Blocking Registry Startup):** MCP server launch failures or connection timeouts do not block assistant startup. Failed servers are logged as warnings and marked `offline`/`failed` in the registry status, allowing built-ins and custom tools to function normally; calling a tool on an offline MCP server returns a clean execution error. — **Reversibility:** reversible — error handling in registry loader.
- **D-13 (Tool List CLI Display):** `paaf tools list` CLI outputs a clean simple list view: `tool_name (source, tier)`. — **Reversibility:** reversible — CLI output formatting.

### Custom Tool Decorator API & Defaults
- **D-14 (@tool Decorator Interface):** `@tool` decorator exported directly from `paaf_llm` (`from paaf_llm import tool`). Supports bare `@tool` or `@tool(name="...", description="...", tier="act")`. — **Reversibility:** costly — public API contract for tool authors.
- **D-15 (Schema Generation via Inspection):** Automatic tool schema generation using `inspect.signature` and docstring parsing (supporting standard summary lines and Google/Sphinx parameter descriptions) to infer argument names, types, defaults, and required parameters into JSON Schema. — **Reversibility:** reversible — decorator reflection utility.
- **D-16 (Default Permission Tier):** Unspecified custom `@tool` functions default to `act` tier (executable directly by agent), aligning with D-06. — **Reversibility:** reversible — decorator parameter default.
- **D-17 (Sync & Async Tool Execution):** Support both synchronous and asynchronous functions in `@tool`. `paaf-llm` awaits coroutine functions directly and dispatches synchronous functions to an asyncio thread pool to prevent loop blocking. — **Reversibility:** reversible — execution dispatcher.

### Prompt Injection Defense & Governance
- **D-18 (Prompt Injection Defense via Permission Tiers):** Per TOOL-07, permission tiers (`act`, `confirm`, `observe`) are documented and enforced as the ONLY defense against prompt injection via tool outputs. Zero hidden defensive prompt instructions are allowed in any system prompt, verified by a dedicated CI test. — **Reversibility:** costly — architecture policy & CI assertion.

### Agent Discretion
- Namespacing fallback strategy: flat names when unique, scoped prefix on collision.
- Docstring parsing strategy: `inspect.signature` combined with standard docstring parsing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Scope
- `.planning/REQUIREMENTS.md` — TOOL-01..08 (always-on built-ins, `@tool` decorator, MCP config, permission tiers, spoken confirmation, prompt injection governance).
- `.planning/ROADMAP.md` §"Phase 5: Tools, MCP & Permissions".

### Prior Phase Decisions & Core Constraints
- `.planning/phases/04-agent-mesh/04-CONTEXT.md` — Mesh handoff seam, Observer tool-based bounding (D-03..D-06, D-14, D-15), peer graph in system prompt.
- `.planning/phases/02-foundation/02-CONTEXT.md` — Secret store (`paaf_core.secrets`) & SQLite trace store (`paaf_trace`).
- `.claude/CLAUDE.md` — Tool confinement, zero network/hardware dependencies in CI tests, import boundary rules.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `paaf_llm`: `agent.py`, `mesh.py`, `observer.py`, `compose.py`, and `ports.py` ready for unified tool registry and system prompt peer feeding.
- `TurnResult.handoff` seam in `ports.py`: the handoff built-in tool directly populates this seam.
- `paaf_trace.store`: SQLite trace store with event queue ready for `history_lookup` queries across past turns, tool calls, and background events.

### Established Patterns
- Clean port/adapter architecture with 100% offline testability.
- Capability removal over prompt instructions: observer and mesh handoff governed via tool availability.

### Integration Points
- `paaf-llm/src/paaf_llm/compose.py`: feed declared peer list into agent system prompt.
- `paaf-llm/src/paaf_llm/agent.py` & `cli.py`: tool execution integration into agent turn loop and `paaf chat` CLI.
</code_context>

<specifics>
## Specific Ideas

- Always-on Built-in Tools: `handoff`, `approve_handoff`, `veto_handoff`, `reroute_handoff`, `date_time_lookup`, `history_lookup`.
- Peer graph awareness fed directly into system prompts (no `list_peers` tool).
- `history_lookup` enables asking about past sessions, tool calls, and background event logs (e.g., track playback starts, notifications, emails).
- Clean spoken confirmation prompt: `"Can I use tool <toolName>?"` without command/path syntax noise.
</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.
</deferred>

---

*Phase: 5-Tools, MCP & Permissions*
*Context gathered: 2026-08-08*
