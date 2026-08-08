---
phase: "05"
plan: "03"
subsystem: mcp
tags: [mcp, stdio, sse, lifecycle, cli]
requires:
  - "05-01"
provides:
  - mcp_server_config
  - mcp_server_manager
  - paaf_mcp_cli
affects:
  - paaf-core
  - paaf-llm
tech-stack:
  added: []
  patterns: [non-blocking-initialization, per-server-timeout, atomic-yaml-config]
key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/mcp/manager.py
    - packages/paaf-llm/src/paaf_llm/mcp/__init__.py
    - packages/paaf-llm/tests/test_mcp_manager.py
  modified:
    - packages/paaf-core/src/paaf_core/config/schema.py
    - packages/paaf-core/src/paaf_core/config/__init__.py
    - packages/paaf-core/tests/test_config_schema.py
    - packages/paaf-llm/src/paaf_llm/cli.py
key-decisions:
  - "McpServerConfig supports stdio and sse transport models with Pydantic validation."
  - "McpServerManager initializes server connections with a non-blocking timeout (5s); offline or failing servers do not block app startup."
  - "Invoking tools on offline MCP servers returns a clean status='offline' error dict without crashing."
  - "paaf mcp add/list/remove CLI commands manage MCP server declarations atomically via paaf-core config writing."
requirements-completed:
  - TOOL-03
  - TOOL-04
duration: "6 min"
completed: "2026-08-08"
coverage:
  - deliverable: "McpServerConfig schema validation"
    verification: "packages/paaf-core/tests/test_config_schema.py::test_mcp_servers_config_validation"
    status: pass
    human_judgment: false
  - deliverable: "McpServerManager non-blocking initialization"
    verification: "packages/paaf-llm/tests/test_mcp_manager.py::test_mcp_server_manager_initialization"
    status: pass
    human_judgment: false
  - deliverable: "paaf mcp CLI commands"
    verification: "packages/paaf-llm/tests/test_mcp_manager.py::test_cli_mcp_add_list_remove"
    status: pass
    human_judgment: false
---

# Phase 05 Plan 03: MCP Server Lifecycle Management Summary

Implemented Model Context Protocol (MCP) server lifecycle management, configuration schema integration, and CLI helper commands.

## Key Accomplishments

- Extended `AppConfig` in `paaf-core` with `McpServerConfig` supporting `stdio` and `sse` transports with Pydantic validation.
- Built `McpServerManager` in `paaf-llm` for non-blocking server initialization (`timeout_s=5.0`) and status tracking (`CONNECTED`, `OFFLINE`, `FAILED`).
- Provided clean execution error responses when invoking tools on offline or missing MCP servers.
- Added `paaf mcp add`, `paaf mcp list`, and `paaf mcp remove` CLI commands with atomic `paaf.yaml` persistence.

## Verification Results

- `pytest packages/paaf-llm/tests/test_mcp_manager.py packages/paaf-core/tests/test_config_schema.py` passed (9 passed).
- All 397 tests across `paaf-core`, `paaf-llm`, and `paaf-trace` passed clean.

## Self-Check: PASSED
