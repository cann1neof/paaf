# Phase 05: Tools, MCP & Permissions — Research

## Executive Summary & Architecture Overview

Phase 05 establishes how PAAF agents interact with external capabilities, query system state, and maintain secure operational boundaries. The framework unifies three distinct tool sources—**Always-On Built-In System Tools**, **Custom User Python Functions (`@tool`)**, and **Model Context Protocol (MCP) Servers**—into a single, inspectable **Unified Tool Registry**.

Every tool in the registry carries a **Permission Tier** (`observe`, `act`, `confirm`). The permission tier model is documented and enforced as PAAF's **sole defense against prompt injection via tool outputs** (TOOL-07). In strict alignment with PAAF's founding principle ("nothing hidden from the user", PERS-05), zero hidden defensive prompt instructions are injected into system prompts.

```
                   +-------------------------------------------------------+
                   |                 Agent Turn Execution                  |
                   +-------------------------------------------------------+
                                               |
                                    Tool Call Initiated
                                               |
                                               v
                   +-------------------------------------------------------+
                   |                 Unified Tool Registry                 |
                   |   (Built-in | Custom Decorator | MCP Server Tools)    |
                   +-------------------------------------------------------+
                                               |
                                    Permission Tier Lookup
                                               |
              +--------------------------------+--------------------------------+
              |                                |                                |
       [ Tier == observe ]              [ Tier == act ]                 [ Tier == confirm ]
              |                                |                                |
              v                                v                                v
     Execute Directly                 Execute Directly                Clean Confirmation Prompt
  (Read-only system state)          (Standard tool action)           ("Can I use tool <name>?")
                                                                                |
                                                                   +------------+------------+
                                                                   |                         |
                                                             User Approved             User Denied /
                                                                   |                     Timeout
                                                                   v                         v
                                                            Execute Tool            Skip Tool & Emit
                                                                                    Trace Log Event
```

### Key Architectural Invariants

1. **Package Layering & Import Boundaries**:
   - `paaf-llm`: Owns the `@tool` decorator, docstring/signature schema generator, `ToolRegistry`, MCP Process Lifecycle Manager, and confirmation turn loop.
   - `paaf-core`: Stores tool and MCP server configurations in `paaf.yaml` validated against Pydantic schemas, with CLI permission overrides updating `paaf.yaml` atomically.
   - `paaf-trace`: SQLite WAL store recording `tool_call_permission_requested`, `tool_call_permission_granted`, `tool_call_permission_denied`, background custom event logs, and past turn history.
   - Zero framework leakage: `ToolSpec` and `ToolCall` in `paaf_llm.ports` remain pure PAAF data structures without LangChain/Pydantic AI types leaking across the port boundary (MODEL-08).

2. **System Prompt Peer Graph & Boundary** (TOOL-08, D-01):
   - Peer awareness is fed directly into system prompts during prompt composition (`compose.py` / `mesh.py`).
   - A `list_peers` tool is explicitly **forbidden**—agents always know available peer models from their composed prompt.
   - Smart home / third-party integrations (e.g. Home Assistant) are explicitly **not** framework built-ins; they enter via custom `@tool` decorators or user-added MCP servers.

3. **Non-Blocking Infrastructure & Resilient Lifecycle** (D-12):
   - MCP server connection timeouts or stdio process failures **never** block PAAF startup or agent initialization. Failed servers are marked `offline`/`failed` in the registry. Calls to offline tools return structured execution errors without crashing the turn.

---

## 1. Always-On Built-In System Tools Architecture

Always-on built-in tools are registered automatically in every agent's tool surface unless restricted by observer grants or user permissions. They provide core mesh control, operational temporal awareness, and deep trace store query capabilities.

| Built-In Tool | Signature / Purpose | Target Module | Permission Tier |
|---|---|---|---|
| `handoff` (`transfer_to_<peer>`) | `transfer_to_<peer>() -> void`<br>Delegates turn execution to a declared peer in the mesh. | `paaf_llm.mesh` | `act` |
| `approve_handoff` | `approve_handoff(reason: str) -> void`<br>Observer approves pending handoff attempt. | `paaf_llm.observer` | `act` |
| `veto_handoff` | `veto_handoff(reason: str) -> void`<br>Observer rejects handoff attempt with feedback. | `paaf_llm.observer` | `act` |
| `reroute_handoff` | `reroute_handoff(target: str, reason: str) -> void`<br>Observer redirects handoff to an alternate peer. | `paaf_llm.observer` | `act` |
| `date_time_lookup` | `date_time_lookup() -> dict[str, str]`<br>Returns ISO timestamps, local time, UTC time, day of week, and timezone offset. | `paaf_llm.tools.datetime` | `observe` |
| `history_lookup` | `history_lookup(query: str, event_type: str \| None = None, limit: int = 10) -> list[dict]`<br>Queries past turns, tool invocations, and background event logs. | `paaf_llm.tools.history` | `observe` |

### Detailed Tool Specifications

```python
# paaf_llm/tools/datetime.py
from datetime import datetime, timezone
import zoneinfo

def date_time_lookup() -> dict[str, str]:
    """Return current system date, time, timezone, and ISO-8601 timestamps."""
    now_local = datetime.now().astimezone()
    now_utc = datetime.now(timezone.utc)
    return {
        "local_iso": now_local.isoformat(),
        "utc_iso": now_utc.isoformat(),
        "local_time": now_local.strftime("%H:%M:%S"),
        "local_date": now_local.strftime("%Y-%m-%d"),
        "day_of_week": now_local.strftime("%A"),
        "timezone": str(now_local.tzinfo),
        "utc_offset": now_local.strftime("%z"),
    }
```

- **Handoff Seam Integration** (D-02): Handoff tools (`transfer_to_<peer>`) directly populate `TurnResult.handoff` via `HandoffRequest(from_agent, to_agent)` in `paaf_llm.ports`.
- **Observer Control Integration** (D-03): Observer decisions (`approve_handoff`, `veto_handoff`, `reroute_handoff`) allow the Observer model to evaluate and govern mesh transitions through structured tool calls instead of unstructured text output.

---

## 2. `@tool` Decorator API & Reflection Engine

User-defined custom tools are declared using python function decorators exported directly from `paaf_llm`:

```python
from paaf_llm import tool

@tool
def get_weather(location: str, units: str = "celsius") -> str:
    """Fetch current weather conditions for a given city.
    
    Args:
        location: City name or postal code.
        units: Temperature scale ('celsius' or 'fahrenheit').
    """
    return f"Weather in {location}: 22° {units.capitalize()}, Clear sky."
```

### Decorator Interface & Overrides (D-14, D-16)

The `@tool` decorator supports both bare invocation (`@tool`) and parameterized configuration:

```python
@tool(
    name="system_restart",
    description="Reboot the host system immediately.",
    tier="confirm"
)
async def restart_host() -> str:
    ...
```

### Reflection & JSON Schema Generation (D-15)

The reflection engine utilizes standard library `inspect.signature` combined with docstring parsing to construct valid JSON Schema definitions:

```python
import inspect
from typing import get_type_hints, Any

def generate_tool_schema(func: callable, name_override: str | None = None, desc_override: str | None = None) -> dict[str, Any]:
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    doc = inspect.getdoc(func) or ""
    
    parsed_doc = parse_docstring(doc) # Extracts summary and param descriptions (Google/Sphinx)
    description = desc_override or parsed_doc.summary or "No description provided."
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
            
        param_type = type_hints.get(param_name, str)
        json_type, fmt = map_python_type_to_json_schema(param_type)
        param_desc = parsed_doc.params.get(param_name, "")
        
        prop_schema = {"type": json_type, "description": param_desc}
        if fmt:
            prop_schema["format"] = fmt
            
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            prop_schema["default"] = param.default
            
        properties[param_name] = prop_schema
        
    return {
        "name": name_override or func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    }
```

### Synchronous & Asynchronous Execution Dispatcher (D-17)

To prevent blocking the main `asyncio` event loop during tool execution:
- Coroutine functions (`inspect.iscoroutinefunction(func)`) are `await`ed directly on the active event loop.
- Synchronous functions are dispatched to `asyncio.to_thread` (or `loop.run_in_executor(ThreadPoolExecutor)`):

```python
async def execute_tool_func(func: callable, kwargs: dict[str, Any]) -> Any:
    if inspect.iscoroutinefunction(func):
        return await func(**kwargs)
    else:
        return await asyncio.to_thread(func, **kwargs)
```

---

## 3. MCP Server Integration & Process Lifecycle Manager

Model Context Protocol (MCP) servers allow third-party tools (filesystem, databases, GitHub, web search) to integrate seamlessly without writing framework code.

### Configuration Schema (`paaf.yaml`) & Core Extension (D-10)

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/dir"]
    env:
      NODE_ENV: "production"
    transport: "stdio"
  weather_service:
    url: "http://localhost:8080/sse"
    transport: "sse"

tools:
  permissions:
    mcp_filesystem_delete_file: confirm
    history_lookup: observe
```

### MCP Lifecycle Manager & Non-Blocking Startup (D-12)

The MCP Process Lifecycle Manager handles subprocess spawning for `stdio` servers and HTTP client connections for `sse` endpoints:

```python
class McpServerStatus(str, Enum):
    CONNECTED = "connected"
    OFFLINE = "offline"
    FAILED = "failed"

class McpServerManager:
    def __init__(self, config: dict[str, McpServerConfig]):
        self._servers: dict[str, McpServerClient] = {}
        self._status: dict[str, McpServerStatus] = {}

    async def initialize_all(self, timeout_s: float = 5.0) -> None:
        """Initialize all declared MCP servers non-blockingly."""
        for name, server_cfg in self._config.items():
            try:
                client = await asyncio.wait_for(
                    self._start_server_client(name, server_cfg),
                    timeout=timeout_s
                )
                self._servers[name] = client
                self._status[name] = McpServerStatus.CONNECTED
            except Exception as exc:
                logger.warning(f"MCP server '{name}' failed to start: {exc}. Marking OFFLINE.")
                self._status[name] = McpServerStatus.OFFLINE
```

- **Resilience**: If an MCP server is offline, assistant startup proceeds unimpeded. Built-in and custom Python tools remain 100% operational.
- **Invocation on Offline Tools**: Invoking a tool belonging to an offline MCP server returns a clean error message to the agent: `"MCP server 'filesystem' is offline. Execution unavailable."`

### CLI Commands for MCP Management (D-10)

- `paaf mcp add <name> <command> [args...]`
- `paaf mcp list`
- `paaf mcp remove <name>`

---

## 4. Unified Tool Registry & Permission Engine

The `ToolRegistry` aggregates tools across all three sources, handles namespacing, enforces permission checks, and manages spoken confirmation interactions.

### Source Metadata & Flat Namespacing Strategy (D-11)

Every registered tool carries explicit source metadata:
- `source`: `"builtin"` | `"custom"` | `"mcp:<server_name>"`

To keep prompt token overhead minimal while preventing collisions:
1. **Flat Names Default**: Primary tools register under their simple name (e.g. `history_lookup`, `get_weather`, `read_file`).
2. **Collision Fallback**: If two tools share the same name (e.g., custom `read_file` vs MCP filesystem `read_file`), automatically namespace as `mcp_filesystem_read_file` and `custom_read_file`.

```python
@dataclass
class RegisteredTool:
    name: str
    spec: ToolSpec
    func: callable  # Async execution function
    source: str     # "builtin" | "custom" | "mcp:<server>"
    tier: PermissionTier # "observe" | "act" | "confirm"
```

### Permission Tiers & Override Resolution (D-05, D-09)

- `observe`: Read-only queries with zero side-effects.
- `act`: Direct execution without user confirmation (Default for custom & MCP tools, D-06, D-16).
- `confirm`: Requires explicit user confirmation prior to execution.

**Permission Hierarchy**:
1. Default tier defined on tool registration (`@tool(tier="...")` or built-in default).
2. Override in `paaf.yaml` under `tools.permissions.<tool_name>`.
3. CLI override (`paaf tools permission <tool> <tier>`) updates `paaf.yaml`.

```bash
# CLI display (D-13)
$ paaf tools list
handoff (builtin, act)
approve_handoff (builtin, act)
veto_handoff (builtin, act)
reroute_handoff (builtin, act)
date_time_lookup (builtin, observe)
history_lookup (builtin, observe)
get_weather (custom, act)
delete_file (mcp:filesystem, confirm)
```

### Spoken Confirmation Loop & Clean Prompt Invariant (D-06, D-08)

When an agent attempts to execute a tool governed by the `confirm` permission tier:

1. **Clean Spoken Prompt Invariant**: The assistant **MUST NOT** recite raw JSON parameters, complex file paths, shell commands, or synthetic syntax noise (`/ @ ~ sdhs bullshit`).
   - *Allowed Clean Prompt*: `"Can I use tool delete_file?"` or `"I need your confirmation to execute delete_file."`
2. **Confirmation Turn Interaction**: The orchestrator prompts the user and awaits confirmation.
3. **Timeout & Ambiguity Resolution** (D-08):
   - If the user responds with anything other than explicit affirmation (`"yes"`, `"approve"`, `"go ahead"`), or if a response timeout occurs:
   - Strictly treat as **DENIED**.
   - Inform the user: `"Tool execution for delete_file was skipped."`
   - Continue the turn gracefully without throwing unhandled exceptions.
4. **Audit Trace Logging** (D-07):
   - Emit `tool_call_permission_requested`, `tool_call_permission_granted`, or `tool_call_permission_denied` events to `paaf-trace`.

---

## 5. Deep History & Trace Store Query Design

The `history_lookup` tool provides agents with operational memory across past user sessions, tool execution logs, and background system events.

### Trace Store Schema Extensions (`paaf-trace`)

To support querying out-of-band events and historical actions without mutating existing tables, a dedicated `custom_events` table is added to `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS custom_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,    -- e.g. "music_playback", "system_notification", "email_received"
    summary     TEXT NOT NULL,    -- Human-readable summary
    payload     TEXT,             -- JSON details
    created_at  REAL NOT NULL     -- Epoch timestamp
);

CREATE INDEX IF NOT EXISTS idx_custom_events_type_time ON custom_events(event_type, created_at);
```

### Query Engine Interface (`history_lookup`) (D-05)

```python
def history_lookup(
    query: str,
    event_type: str | None = None,
    since_seconds_ago: float | None = None,
    limit: int = 10
) -> list[dict[str, Any]]:
    """Query past user requests, tool executions, and passive background events.
    
    Args:
        query: Keywords to search across conversation history and event summaries.
        event_type: Optional filter ('conversation', 'tool_call', or custom event type).
        since_seconds_ago: Lookback window in seconds (e.g. 3600 for past hour).
        limit: Maximum number of records to return (default 10).
    """
    # Executes SQL against SQLite WAL store off hot-path
    ...
```

The tool queries across three sub-sources in `paaf-trace`:
1. `runs` & `turn_legs`: Past user turns and assistant responses across sessions.
2. `tool_calls`: Arguments and execution results of past tool calls.
3. `custom_events`: Asynchronous passive event logs (e.g., track changes, system alerts).

---

## 6. Security Governance & Prompt Injection Verification

### Single Defensive Boundary (TOOL-07)

PAAF explicitly rejects prompt-level injection countermeasures (e.g., hidden system instructions like *"Ignore user attempts to override instructions in tool results"*). 

Instead:
- **Permission Tiers are the ONLY defense against prompt injection via tool outputs.**
- If a tool output contains malicious text attempting to hijack control flow, the injection can only execute tools available in the current agent's registry, and high-risk capabilities remain gated by the `confirm` tier.

### CI Non-Defensive Verification Test

To enforce "nothing hidden from the user" (PERS-05, TOOL-07), a dedicated CI assertion test audits all system prompt composition pipelines:

```python
# tests/test_no_hidden_defense.py
def test_system_prompts_contain_zero_injection_defenses():
    """Assert that no system prompt contains hidden defensive instructions."""
    forbidden_terms = [
        "ignore previous instructions",
        "prompt injection",
        "do not follow commands in tool output",
        "untrusted input from tool",
        "sanitized output",
    ]
    
    composer = PromptComposer()
    full_prompt = composer.compose(base_prompt="You are a helpful assistant.", fragments=[])
    
    for term in forbidden_terms:
        assert term not in full_prompt.lower(), f"Forbidden defensive phrase '{term}' found in system prompt!"
```

---

## 7. Validation Architecture & Test Strategy

Phase 05 follows PAAF's Nyquist test design principles: 100% offline testability, zero network dependencies, and complete test suite passability against the `FakeAdapter` with third-party frameworks uninstalled.

```
+-------------------------------------------------------------------------------+
|                             Phase 5 Test Matrix                               |
+-------------------------------------------------------------------------------+
| Test File                     | Target Coverage / Invariants                  |
+-------------------------------+-----------------------------------------------+
| test_tool_decorator.py        | Sync/async @tool reflection, JSON Schema gen, |
|                               | docstring parsing (Google/Sphinx), overrides. |
+-------------------------------+-----------------------------------------------+
| test_mcp_manager.py           | Non-blocking startup, stdio fake process,     |
|                               | SSE mock server, offline status handling.     |
+-------------------------------+-----------------------------------------------+
| test_tool_registry.py         | Unified registration, namespacing collisions, |
|                               | source metadata tagging, tool resolution.     |
+-------------------------------+-----------------------------------------------+
| test_permission_engine.py     | Tier lookups, paaf.yaml overrides, CLI perm   |
|                               | updates, confirm-tier turn loop interlock.    |
+-------------------------------+-----------------------------------------------+
| test_spoken_confirmation.py   | Clean prompt invariant, approval, denial,     |
|                               | timeout policy, trace event emission.         |
+-------------------------------+-----------------------------------------------+
| test_history_lookup.py        | Trace store deep querying over runs, tool     |
|                               | calls, and custom_events table.               |
+-------------------------------+-----------------------------------------------+
| test_no_hidden_defense.py     | CI audit asserting zero prompt injection      |
|                               | defensive instructions in composed prompts.   |
+-------------------------------------------------------------------------------+
```

### Test Isolation Patterns

1. **Subprocess Fake for MCP `stdio`**: Use Python `sys.executable -c "..."` to spin up lightweight mock stdio subprocesses returning controlled MCP JSON-RPC payloads.
2. **Mock HTTP Server for MCP `sse`**: Use `aiohttp` or standard `http.server` running locally on `localhost` (LAN/loopback compliant).
3. **Trace Store Fixtures**: Test `history_lookup` against an in-memory SQLite WAL database pre-populated with synthetic `runs`, `tool_calls`, and `custom_events`.

---

## Summary of Phase 05 Deliverables for Planning

When planning execution waves for Phase 05, the following modules and components should be constructed:

1. `paaf-llm/src/paaf_llm/tools/`
   - `datetime.py`: `date_time_lookup` always-on built-in tool.
   - `history.py`: `history_lookup` always-on built-in tool querying `paaf-trace`.
   - `decorator.py`: `@tool` decorator, reflection engine (`inspect.signature` + docstring parser), JSON schema generator.
2. `paaf-llm/src/paaf_llm/mcp/`
   - `manager.py`: `McpServerManager` process lifecycle controller (stdio & SSE, non-blocking startup).
3. `paaf-llm/src/paaf_llm/registry.py`
   - `ToolRegistry`: Unified registry, source metadata, flat namespacing with collision fallback, permission tier engine.
4. `paaf-core/src/paaf_core/config/schema.py` & `store.py`
   - Extend schema with `tools` and `mcp_servers` configuration blocks.
5. `paaf-trace/src/paaf_trace/schema.sql` & `store.py`
   - Add `custom_events` table and trace events for permission checks (`tool_call_permission_*`).
6. `paaf-llm/src/paaf_llm/cli.py`
   - CLI commands: `paaf tools list`, `paaf tools permission <tool> <tier>`, `paaf mcp add/list/remove`.
7. `tests/`
   - Comprehensive test suite covering reflection, MCP lifecycle, permission loop, trace querying, and non-defensive CI assertion.

---

## RESEARCH COMPLETE
