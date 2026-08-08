# Phase 5: Tools, MCP & Permissions - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-08
**Phase:** 5-Tools, MCP & Permissions
**Areas discussed:** Built-in System Tools (Mesh & Observer Infrastructure), Permission Tiers & Spoken Confirmation Loop, Unified Registry & MCP Server Config, Custom Tool Decorator API & Defaults

---

## Built-in System Tools (Mesh & Observer Infrastructure)

| Concept | Scope / Decision | Reason |
|---------|------------------|--------|
| Mesh Handoff Tool (`handoff`) | Registered as built-in tool in unified registry | Enables agent-to-agent delegation via standard tool calling seam |
| Observer Tools (`approve_handoff`, `veto_handoff`, `reroute_handoff`) | Registered as built-in tools for Observer profile | Structurally bounds observer to structured tool calls (capability-removal principle) |
| System / Peer Inspection Tools (`list_peers`) | Registered as built-in tools | Allows agents to discover declared peer graph and session context |
| Home Assistant | **EXCLUDED** from Phase 5 out-of-the-box shipping | Deferred to future external plugin release |

---

## Permission Tiers & Spoken Confirmation Loop

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit per-call prompt | Prompt out loud/in text, wait for explicit confirmation, default to deny on timeout | |
| Session-scoped grant | Ask on first call, allow subsequent calls to that tool for remainder of session | |
| User Constraint | By default all tools are executable by agent ('act'). User can enforce 'confirm' on specific tools. Agent confirmation prompt must be clean ('Can I use tool <toolName>?') without command/path syntax noise. | ✓ |

**User's choice:** Custom constraint: All tools executable by default ('act'), user can enforce confirm check for specific tools. Spoken confirmation prompt must be clean and concise ("Can I use tool <toolName>?") with zero path/command syntax noise.

| Option | Description | Selected |
|--------|-------------|----------|
| Record distinct permission events | Record permission_requested and permission_granted/denied trace events in SQLite trace store | ✓ |
| Single tool_call status | Log single tool_call event with status='approved'/'denied' | |
| Agent discretion | You decide | |

**User's choice:** Record distinct permission_requested and permission_granted/denied trace events in SQLite trace store.

| Option | Description | Selected |
|--------|-------------|----------|
| Strict denial on timeout | Treat as denied and inform user tool was skipped | ✓ |
| Re-prompt once | Re-prompt once if user response is ambiguous | |
| Agent discretion | You decide | |

**User's choice:** Strict denial on timeout / unrecognized response — treat as denied and inform user tool was skipped.

| Option | Description | Selected |
|--------|-------------|----------|
| paaf.yaml configuration mapping | Configuration mapping in paaf.yaml (e.g. tools.permissions: { <tool_name>: confirm }) | |
| CLI command | Interactive CLI command (paaf tools permission <tool> confirm) | |
| Both | Support both paaf.yaml mapping and CLI override command | ✓ |

**User's choice:** Both paaf.yaml mapping and interactive CLI command.

---

## Unified Registry & MCP Server Config

| Option | Description | Selected |
|--------|-------------|----------|
| paaf.yaml section + CLI | Support mcp_servers section in paaf.yaml + paaf mcp add/list/remove CLI command | ✓ |
| Dedicated JSON file | Dedicated mcp_servers.json config file | |
| Agent discretion | You decide | |

**User's choice:** Support mcp_servers section in paaf.yaml (with stdio command/args/env & sse url support) + paaf mcp add/list/remove CLI command.

| Option | Description | Selected |
|--------|-------------|----------|
| Prefixed names | Prefixed names internally (e.g., builtin:timer_set, mcp:server_name:tool_name) | |
| Flat names with collision check | Flat names by default, collision error if duplicate | |
| Agent discretion | You decide | ✓ |

**User's choice:** Agent discretion / You decide (Resolved: Flat names when unique, scoped prefix on collision).

| Option | Description | Selected |
|--------|-------------|----------|
| Non-blocking startup | Log warning, mark server offline/failed in registry, allow rest of assistant to work | ✓ |
| Strict startup failure | Fail assistant boot immediately if any configured MCP server fails | |
| Agent discretion | You decide | |

**User's choice:** Non-blocking registry startup — log warning, mark server offline/failed in registry, allow rest of assistant to work; return clean tool execution error if called.

| Option | Description | Selected |
|--------|-------------|----------|
| Rich table view | Tool Name \| Source \| Tier \| Description \| Server Status | |
| Simple list view | tool_name (source, tier) | ✓ |
| Agent discretion | You decide | |

**User's choice:** Simple list view: tool_name (source, tier).

---

## Custom Tool Decorator API & Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| Export @tool from paaf_llm | Supports bare @tool and @tool(tier='act', name=...) | |
| Export @tool from paaf_core | Separate package import | |
| Agent discretion | You decide | ✓ |

**User's choice:** Agent discretion / You decide (Resolved: Export @tool directly from paaf_llm).

| Option | Description | Selected |
|--------|-------------|----------|
| Automatic inspection | Python type hints -> JSON schema types; docstrings -> parameter descriptions | |
| Pydantic model only | Pydantic BaseModel parsing only | |
| Agent discretion | You decide | ✓ |

**User's choice:** Agent discretion / You decide (Resolved: Automatic inspection via inspect.signature and docstring parsing).

| Option | Description | Selected |
|--------|-------------|----------|
| 'act' tier default | 'act' tier by default (following user constraint) | ✓ |
| 'confirm' tier default | 'confirm' tier by default for safety | |
| Agent discretion | You decide | |

**User's choice:** 'act' tier by default (following user constraint that tools are executable by default unless user sets confirm override).

| Option | Description | Selected |
|--------|-------------|----------|
| Seamless sync and async | Await coroutines directly, run synchronous tools in asyncio thread pool | ✓ |
| Async only | Require all custom @tool functions to be async def | |
| Agent discretion | You decide | |

**User's choice:** Seamless sync and async support — await coroutines directly, run synchronous tools in asyncio thread pool.

---

## Agent's Discretion

- Namespacing fallback: Flat tool names when unique, scoped prefix on collision.
- Tool schema extraction: inspect.signature combined with standard docstring parsing.
- @tool decorator export path: `from paaf_llm import tool`.

## Deferred Ideas

- **Home Assistant integration** — deferred to future plugin release; not included out of the box in Phase 5.
