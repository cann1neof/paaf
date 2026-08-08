---
phase: "05"
plan: "01"
subsystem: tools
tags: [builtins, datetime, history, trace, mesh]
requires: []
provides:
  - date_time_lookup
  - history_lookup
  - custom_events_table
  - builtin_tool_specs
affects:
  - paaf-trace
  - paaf-llm
tech-stack:
  added: []
  patterns: [parameterized-sql, tool-explainer-docstring, peer-graph-prompt-injection]
key-files:
  created:
    - packages/paaf-llm/src/paaf_llm/tools/datetime.py
    - packages/paaf-llm/src/paaf_llm/tools/history.py
    - packages/paaf-llm/src/paaf_llm/tools/__init__.py
    - packages/paaf-trace/tests/test_history_lookup.py
    - packages/paaf-llm/tests/test_tools.py
  modified:
    - packages/paaf-trace/src/paaf_trace/schema.sql
    - packages/paaf-trace/src/paaf_trace/store.py
    - packages/paaf-trace/tests/test_trace_schema.py
key-decisions:
  - "custom_events table added to paaf-trace with event_type and created_at indexing for background event logs."
  - "history_lookup provides parameterized SQL search over runs, tool_calls, and custom_events without raw SQL execution."
  - "peer graph awareness is injected directly into system prompts via prompt composition; list_peers tool is explicitly forbidden."
requirements-completed:
  - TOOL-01
  - TOOL-08
duration: "5 min"
completed: "2026-08-08"
coverage:
  - deliverable: "date_time_lookup tool"
    verification: "packages/paaf-trace/tests/test_history_lookup.py::test_date_time_lookup"
    status: pass
    human_judgment: false
  - deliverable: "history_lookup tool and custom_events trace integration"
    verification: "packages/paaf-trace/tests/test_history_lookup.py::test_history_lookup"
    status: pass
    human_judgment: false
  - deliverable: "peer graph prompt injection and no list_peers tool"
    verification: "packages/paaf-llm/tests/test_tools.py::test_peer_graph_injected_in_system_prompt"
    status: pass
    human_judgment: false
---

# Phase 05 Plan 01: Always-On Built-In Tools Summary

Implemented always-on built-in system tools (`date_time_lookup`, `history_lookup`, `handoff`, and Observer decision tools) and verified peer graph awareness in system prompts without a `list_peers` tool.

## Key Accomplishments

- Added `custom_events` table and indexing to `paaf-trace` schema.
- Implemented `date_time_lookup` returning ISO timestamp, local time/date, timezone, and offset details.
- Implemented `history_lookup` with parameterized SQL queries and embedded Tool Explainer & Schema Guide docstring.
- Exported built-in `ToolSpec` definitions for datetime, history, handoff, and Observer decision tools in `paaf_llm.tools`.
- Confirmed peer graph awareness is composed into prompts directly without `list_peers` tool.

## Verification Results

- `pytest packages/paaf-llm/tests/test_tools.py packages/paaf-trace/tests/test_history_lookup.py` passed (6 passed).
- All 330 tests across `paaf-llm` and `paaf-trace` passed clean.

## Self-Check: PASSED
