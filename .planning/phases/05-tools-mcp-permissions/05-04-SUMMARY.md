---
phase: "05"
plan: "04"
subsystem: tools
tags: [registry, permissions, confirmation, spoken-prompt, cli]
requires:
  - "05-01"
  - "05-02"
  - "05-03"
provides:
  - tool_registry
  - permission_engine
  - spoken_confirmation_loop
affects:
  - paaf-core
  - paaf-llm
  - paaf-trace
tech-stack:
  added: []
  patterns: [unified-registry, permission-hierarchy, spoken-prompt-invariant, default-deny-timeout]
key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/permissions.py
    - packages/paaf-llm/src/paaf_llm/registry.py
    - packages/paaf-llm/tests/test_tool_registry.py
    - packages/paaf-llm/tests/test_permission_engine.py
    - packages/paaf-llm/tests/test_spoken_confirmation.py
  modified:
    - packages/paaf-core/src/paaf_core/config/schema.py
    - packages/paaf-core/src/paaf_core/config/__init__.py
    - packages/paaf-llm/src/paaf_llm/cli.py
key-decisions:
  - "ToolRegistry unifies built-in, @tool, and MCP tools with collision-resilient scoped prefix fallback (e.g. mcp_server_tool)."
  - "PermissionEngine resolves tier hierarchy: CLI overrides -> AppConfig.tools.permissions -> default rules (observe for datetime/history, act otherwise)."
  - "Spoken confirmation loop enforces clean prompt format ('Can I use tool <name>?') with default-deny timeouts and paaf-trace audit logging."
  - "paaf tools list and paaf tools permission CLI commands support displaying and overriding permission tiers atomically."
requirements-completed:
  - TOOL-04
  - TOOL-05
  - TOOL-06
duration: "7 min"
completed: "2026-08-08"
coverage:
  - deliverable: "Unified ToolRegistry and name collision namespacing"
    verification: "packages/paaf-llm/tests/test_tool_registry.py::test_name_collision_scoped_prefix_fallback"
    status: pass
    human_judgment: false
  - deliverable: "PermissionEngine resolution hierarchy and CLI commands"
    verification: "packages/paaf-llm/tests/test_permission_engine.py::test_permission_engine_resolution_hierarchy"
    status: pass
    human_judgment: false
  - deliverable: "Spoken confirmation loop and clean prompt invariants"
    verification: "packages/paaf-llm/tests/test_spoken_confirmation.py::test_spoken_confirmation_granted"
    status: pass
    human_judgment: false
---

# Phase 05 Plan 04: Unified Tool Registry, Permission Engine, and Spoken Confirmation Loop Summary

Built the Unified Tool Registry, Permission Engine, and Spoken Confirmation Loop across built-in, `@tool`, and MCP sources.

## Key Accomplishments

- Extended `AppConfig` in `paaf-core` with `PermissionTier` (`observe`, `act`, `confirm`) and `ToolsConfig` permissions mapping.
- Implemented `ToolRegistry` unifying tools from built-in, `@tool`, and MCP sources with automatic scoped prefix fallback on name collisions (`mcp_<server>_<name>`).
- Built `PermissionEngine` evaluating permission hierarchy (CLI overrides -> `paaf.yaml` `tools.permissions` -> default rules).
- Added `paaf tools list` and `paaf tools permission <tool> <tier>` CLI commands with atomic persistence.
- Built spoken confirmation loop enforcing clean prompt invariant (`"Can I use tool <name>?"`), default-deny timeout policies, and `paaf-trace` audit logging.

## Verification Results

- `pytest packages/paaf-llm/tests/test_tool_registry.py packages/paaf-llm/tests/test_permission_engine.py packages/paaf-llm/tests/test_spoken_confirmation.py` passed (8 passed).
- All 405 tests across `paaf-core`, `paaf-llm`, and `paaf-trace` passed clean.

## Self-Check: PASSED
