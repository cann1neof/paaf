# Phase 05: Tools, MCP & Permissions — Pattern Mapping

**Gathered:** 2026-08-08  
**Status:** Complete  

---

## Executive Summary

Phase 05 establishes how PAAF agents interact with external capabilities, query operational memory, and maintain strict permission boundaries. This document maps the existing architectural patterns, signatures, design idioms, and concrete codebase seams in PAAF that will guide implementation planning for Phase 05.

Every pattern identified here adheres strictly to PAAF's founding principles:
1. **Zero Framework Leakage (MODEL-08)**: Core domain models, port protocols, and tool specs remain pure PAAF data structures without third-party framework dependencies.
2. **Capability Removal over Prompt Instructions (TOOL-07 / D-18)**: Permission tiers (`observe`, `act`, `confirm`) serve as the single defense against prompt injection. Zero hidden defensive prompt instructions are added to system prompts (PERS-05).
3. **Deterministic Prompt Composition**: Peer graph awareness is fed directly into system prompts during prompt composition (`compose.py`). No `list_peers` tool is used.
4. **Resilient Non-Blocking Infrastructure (D-12)**: External tool integrations (MCP servers) fail gracefully without blocking assistant startup or agent execution.
5. **Durability & Provenance**: Every tool call and permission check event is recorded in SQLite WAL trace logs (`paaf-trace`) off the hot execution path.

---

## Existing Architectural Patterns & Code Analogues

### 1. Port/Adapter Boundary & PAAF-Typed Data Structures
* **Source Files**: [`packages/paaf-llm/src/paaf_llm/ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/ports.py), [`packages/paaf-llm/src/paaf_llm/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/__init__.py)
* **Pattern Overview**: All model interactions, tools, messages, and signals cross a narrow PAAF-typed protocol boundary. The core layer (`paaf_llm`) defines protocols and dataclasses with zero imports of third-party frameworks (e.g. LangChain, Pydantic AI, or MCP SDKs).
* **Key Components & Signatures**:
  ```python
  @dataclass(frozen=True, slots=True)
  class ToolSpec:
      name: str
      description: str
      parameters: dict[str, object]  # JSON Schema dictionary

  @dataclass(frozen=True, slots=True)
  class ToolCall:
      name: str
      arguments: dict[str, object]
      call_id: str | None = None

  @runtime_checkable
  class ToolCallingChatAdapter(ChatAdapter, Protocol):
      def stream_with_tools(
          self, profile: ModelProfile, messages: Sequence[Message], tools: Sequence[ToolSpec]
      ) -> AsyncIterator[str]: ...
      def last_tool_calls(self) -> tuple[ToolCall, ...]: ...
  ```
* **Phase 05 Application**: `ToolRegistry` aggregates built-in, `@tool`, and MCP tools into `ToolSpec` instances passed into `stream_with_tools`. Tool execution results map back cleanly to agent turns without leaking adapter-specific objects.

---

### 2. Capability Removal & Two-Pass Defense
* **Source Files**: [`packages/paaf-llm/src/paaf_llm/mesh.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/mesh.py#L274-L353), [`packages/paaf-llm/src/paaf_llm/mesh.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/mesh.py#L577-L610)
* **Pattern Overview**: Boundaries are enforced by **withdrawing tools** from the offered tool surface rather than instructing models to behave. A second validation pass (`resolve_*`) checks execution against explicit rules so misbehaving models cannot bypass restrictions.
* **Key Components & Signatures**:
  ```python
  # Pass 1: Surface Generation (Capability Removal)
  def tools_for_leg(awake_name: str, awake: ModelProfile, ...) -> tuple[ToolSpec, ...]:
      if hops_used >= budget:
          return () # Tools withdrawn at budget wall
      return handoff_tools(awake_name, awake, ...)

  # Pass 2: Hard Verification
  def resolve_handoff(awake_name: str, awake: ModelProfile, call: ToolCall) -> str:
      if target not in awake.peers:
          raise UndeclaredPeer(...)
  ```
* **Phase 05 Application**:
  - Permission tiers (`observe`, `act`, `confirm`) determine tool availability and execution flow.
  - The `confirm` tier gates tool invocation behind explicit user confirmation before execution.
  - Verification CI assertions ensure zero prompt-level injection defenses exist in system prompts.

---

### 3. Byte-Exact Prompt Composition & Peer Graph Injection
* **Source Files**: [`packages/paaf-llm/src/paaf_llm/compose.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/compose.py), [`packages/paaf-llm/src/paaf_llm/mesh.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/mesh.py#L532-L561)
* **Pattern Overview**: A single deterministic function `PromptComposer.compose` builds system prompts by joining labeled `Segment` instances with `\n\n`. PAAF adds zero preambles or hidden defensive text. Peer graph awareness is fed directly into system prompts during composition (D-01). A `list_peers` tool is explicitly forbidden.
* **Key Components & Signatures**:
  ```python
  @dataclass(frozen=True, slots=True)
  class Segment:
      source: str
      text: str

  class PromptComposer:
      def compose(self, base_prompt: str, fragments: list[tuple[str, str]], mesh_fragments: Sequence[tuple[str, str]] = ()) -> str:
          return SEGMENT_SEPARATOR.join(s.text for s in self.segments(base_prompt, fragments, mesh_fragments))
  ```
* **Phase 05 Application**: `compose.py` remains the PERS-05 enforcement point. Peer graph information is included in prompt composition while built-in tools (`date_time_lookup`, `history_lookup`, `handoff`, observer tools) are offered via `ToolSpec` in the tool surface.

---

### 4. Atomic Configuration Persistence & Optimistic Locking
* **Source Files**: [`packages/paaf-core/src/paaf_core/config/schema.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-core/src/paaf_core/config/schema.py), [`packages/paaf-core/src/paaf_core/config/store.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-core/src/paaf_core/config/store.py)
* **Pattern Overview**: `paaf.yaml` is validated against Pydantic models with `model_config = {"extra": "forbid"}` and explicit `ReloadTier` metadata (`HOT`, `WARM`, `COLD`, `RESTART`). Writes are durable and atomic (tempfile write + `fsync` + `os.replace` + parent directory `fsync`) and protected against concurrent edits using `FileLock` and a monotonic `revision` counter.
* **Key Components & Signatures**:
  ```python
  class ReloadTier(str, Enum):
      HOT = "hot"
      WARM = "warm"
      COLD = "cold"
      RESTART = "restart-only"

  def write_config(path: str, lock_path: str, new_model: AppConfig, expected_revision: int) -> int:
      with FileLock(lock_path):
          current = load_config(path)
          if current.revision != expected_revision:
              raise ConflictError(...)
          new_model.revision = current.revision + 1
          atomic_write_bytes(path, dump_config(new_model))
          return new_model.revision
  ```
* **Phase 05 Application**: Extend `AppConfig` with schema sections for `tools` (permission overrides) and `mcp_servers` (stdio and SSE configurations). CLI commands (`paaf tools permission`, `paaf mcp add/remove`) persist changes atomically using `write_config`.

---

### 5. Non-Blocking Async Trace Store & Event Queueing
* **Source Files**: [`packages/paaf-trace/src/paaf_trace/store.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-trace/src/paaf_trace/store.py), [`packages/paaf-trace/src/paaf_trace/schema.sql`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-trace/src/paaf_trace/schema.sql)
* **Pattern Overview**: `TraceStore` uses SQLite WAL mode + `synchronous=NORMAL` with a single background writer task consuming events from a bounded `asyncio.Queue`. Producers call synchronous non-blocking `.emit(event)`. Events are raw dataclasses exposing `.as_sql() -> (sql, params)`. Schema changes use `CREATE TABLE IF NOT EXISTS` for new event tables without mutating existing tables.
* **Key Components & Signatures**:
  ```python
  class TraceSink(Protocol):
      def emit(self, event: object) -> None: ...

  class TraceStore:
      def emit(self, event: object) -> None:
          try:
              self._q.put_nowait(event)
          except asyncio.QueueFull:
              self._dropped += 1
  ```
* **Phase 05 Application**:
  - Add `custom_events` table to `schema.sql` for background/out-of-band event logging.
  - Define `ToolCallPermissionRequestedEvent`, `ToolCallPermissionGrantedEvent`, and `ToolCallPermissionDeniedEvent`.
  - Implement `history_lookup` built-in tool by executing SQLite queries against `runs`, `turn_legs`, `tool_calls`, and `custom_events`.

---

### 6. CLI Command Extensions & Rich Console Protection
* **Source Files**: [`packages/paaf-llm/src/paaf_llm/cli.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/cli.py)
* **Pattern Overview**: CLI subcommands are thin click wrappers around core domain logic. Console output uses `Console(markup=False, highlight=False, soft_wrap=True)` to prevent untrusted input or prompt strings from triggering rich formatting side-effects. Passphrases are read via environment variables or TTY prompts, never command-line arguments.
* **Key Components & Signatures**:
  ```python
  def _make_console() -> Console:
      return Console(markup=False, highlight=False, soft_wrap=True)

  @click.group()
  def main(): ...
  ```
* **Phase 05 Application**:
  - Add CLI subcommands: `paaf tools list`, `paaf tools permission <tool> <tier>`, and `paaf mcp add/list/remove`.
  - Format output safely using `_make_console()`.

---

### 7. Dual Sync/Async Execution Dispatcher
* **Source Files**: [`packages/paaf-llm/src/paaf_llm/agent.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/agent.py#L383-L420)
* **Pattern Overview**: Async execution loop awaits coroutine functions directly on the active event loop and dispatches synchronous functions to an executor thread (`asyncio.to_thread`) to prevent blocking main loop execution.
* **Key Components & Signatures**:
  ```python
  async def execute_tool_func(func: callable, kwargs: dict[str, Any]) -> Any:
      if inspect.iscoroutinefunction(func):
          return await func(**kwargs)
      else:
          return await asyncio.to_thread(func, **kwargs)
  ```
* **Phase 05 Application**: Custom `@tool` decorator supports both `async def` and synchronous `def` functions. Synchronous tool calls are offloaded to `asyncio.to_thread`.

---

## Phase 05 Feature Mapping Matrix

| Feature | Target Module(s) | Architectural Pattern / Analogue | Key Invariants & Design Notes |
|---|---|---|---|
| **Always-On Built-In Tools** | `paaf_llm.tools.datetime`<br>`paaf_llm.tools.history`<br>`paaf_llm.mesh`<br>`paaf_llm.observer` | **Pattern 1 & 2** (Port boundary & tool surface) | Built-ins registered automatically: `date_time_lookup` (observe tier), `history_lookup` (observe tier), `handoff` (act tier), Observer tools (`approve_handoff`, `veto_handoff`, `reroute_handoff`). |
| **`@tool` Decorator API** | `paaf_llm.tools.decorator` | **Pattern 7 & 1** (Reflection & execution dispatcher) | Supports bare `@tool` or `@tool(name=..., description=..., tier=...)`. Uses `inspect.signature` and docstring parser (Google/Sphinx) for JSON Schema generation. Supports sync/async functions. |
| **MCP Server Lifecycle Manager** | `paaf_llm.mcp.manager` | **Pattern 1 & 7** (Async process lifecycle & resilience) | Spawns stdio subprocesses or connects to SSE endpoints. Startup is non-blocking (D-12); failed servers marked `offline`. Invocations on offline tools return clean error strings. |
| **Unified Tool Registry** | `paaf_llm.registry` | **Pattern 2 & 4** (Surface composition & metadata tagging) | Aggregates built-in, `@tool`, and MCP tools. Tags tools with `source` (`builtin`, `custom`, `mcp:<server>`). Flat default namespacing, falling back to `mcp_<server>_<tool>` or `custom_<tool>` on collision (D-11). |
| **Permission Tier Engine & Confirmation Loop** | `paaf_llm.permissions`<br>`paaf_session.orchestrator` | **Pattern 2, 4 & 5** (Capability interlock & trace logging) | Resolves tier (`observe`, `act`, `confirm`) from tool default, `paaf.yaml` overrides, or CLI. On `confirm` tier, requires clean spoken confirmation prompt (`"Can I use tool <name>?"`). Timeout/ambiguity resolves to DENIED (D-08). Emits trace events (`tool_call_permission_*`). |
| **Deep History Query Engine** | `paaf_trace.store`<br>`paaf_llm.tools.history` | **Pattern 5** (Trace store schema extension & querying) | Extends `schema.sql` with `custom_events` table. `history_lookup` queries across past runs, tool calls, and passive custom event logs off the hot execution path. |
| **Prompt Injection Defense & Governance** | `paaf_llm.compose`<br>`tests/test_no_hidden_defense.py` | **Pattern 2 & 3** (Zero hidden defensive prompts) | Permission tiers are the ONLY defense against prompt injection via tool outputs (TOOL-07). CI test asserts system prompt composition contains zero hidden defensive instructions (PERS-05). |
| **CLI Management Tools** | `paaf_llm.cli` | **Pattern 6** (Click command extensions & rich console) | Provides `paaf tools list`, `paaf tools permission <tool> <tier>`, and `paaf mcp add/list/remove` commands, persisting changes to `paaf.yaml` via `write_config`. |

---

## Detailed Implementation Idioms for Wave Planning

### Idiom A: Non-Blocking MCP Initialization (D-12)
```python
# paaf_llm/mcp/manager.py
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)

class McpServerStatus(str, Enum):
    CONNECTED = "connected"
    OFFLINE = "offline"
    FAILED = "failed"

class McpServerManager:
    def __init__(self, config: dict[str, McpServerConfig]):
        self._config = config
        self._clients: dict[str, McpClient] = {}
        self._status: dict[str, McpServerStatus] = {}

    async def initialize_all(self, timeout_s: float = 5.0) -> None:
        """Initialize declared MCP servers non-blockingly."""
        for name, cfg in self._config.items():
            try:
                client = await asyncio.wait_for(self._connect_server(name, cfg), timeout=timeout_s)
                self._clients[name] = client
                self._status[name] = McpServerStatus.CONNECTED
            except Exception as exc:
                logger.warning("MCP server '%s' failed to start: %s. Marking OFFLINE.", name, exc)
                self._status[name] = McpServerStatus.OFFLINE
```

### Idiom B: Unified Tool Registry & Collision Fallback (D-11)
```python
# paaf_llm/registry.py
from dataclasses import dataclass
from typing import Callable, Any
from paaf_llm.ports import ToolSpec

@dataclass(frozen=True, slots=True)
class RegisteredTool:
    name: str
    spec: ToolSpec
    func: Callable[..., Any]
    source: str           # "builtin" | "custom" | "mcp:<server>"
    tier: str             # "observe" | "act" | "confirm"

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}
        self._raw_names: dict[str, list[RegisteredTool]] = {}

    def register(self, raw_name: str, spec: ToolSpec, func: Callable[..., Any], source: str, tier: str) -> None:
        # Resolves flat names by default; applies prefix on collision
        ...
```

### Idiom C: Clean Confirmation Spoken Prompt Invariant (D-06, D-08)
```python
# Confirmation prompt rule:
# Clean, concise spoken phrase without raw paths or command syntax.
CONFIRMATION_PROMPT_TEMPLATE = "Can I use tool {tool_name}?"

# Timeout or unrecognized response policy:
# Treat strictly as DENIED, inform user tool was skipped, continue turn.
DENIED_NOTICE_TEMPLATE = "Tool execution for {tool_name} was skipped."
```

### Idiom D: Non-Defensive System Prompt CI Assertion (TOOL-07)
```python
# tests/test_no_hidden_defense.py
def test_system_prompts_contain_zero_injection_defenses():
    """Assert that system prompt composition contains zero hidden defensive instructions."""
    forbidden_phrases = [
        "ignore previous instructions",
        "prompt injection",
        "do not follow commands in tool output",
        "untrusted input from tool",
        "sanitized output",
    ]
    composer = PromptComposer()
    full_prompt = composer.compose(base_prompt="You are a helpful assistant.", fragments=[])
    
    for phrase in forbidden_phrases:
        assert phrase not in full_prompt.lower(), f"Forbidden defensive phrase '{phrase}' found in composed system prompt!"
```

---

## Conclusion & Next Steps

All architectural patterns required for Phase 05 exist cleanly within the codebase and are documented above. Implementation will proceed according to the established execution waves in Phase 05 planning.

## PATTERN MAPPING COMPLETE
