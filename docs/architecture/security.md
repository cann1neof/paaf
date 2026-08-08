# PAAF Security Architecture: Non-Defensive Prompt Injection Governance

## Overview

PAAF (Personalized Agentic Assistant Framework) implements a **non-defensive prompt injection governance model** (TOOL-07, PERS-05, D-18).

Unlike traditional LLM wrappers that inject hidden system instructions to filter, sanitize, or guard prompt text, PAAF enforces absolute prompt transparency (**"nothing hidden from the user"**, PERS-05).

## Core Security Principles

1. **Zero Hidden Defensive Instructions (PERS-05)**:
   - System prompts contain ONLY base agent instructions, declared skills, and explicit peer/mesh explainers.
   - PAAF never injects secret prompt defenses, hidden guardrails, or instruction overrides.
   - Automated CI testing (`tests/test_no_hidden_defense.py`) continuously verifies the complete absence of defensive prompt phrases across all composed prompts.

2. **Permission Tiers as Sole Injection Defense (TOOL-05, TOOL-07)**:
   - Tool execution authority is governed exclusively by **Permission Tiers** (`observe`, `act`, `confirm`).
   - `observe`: Read-only queries (e.g. `date_time_lookup`, `history_lookup`).
   - `act`: Safe active tools (e.g. custom `@tool` functions, standard MCP tools).
   - `confirm`: Actionable or high-risk tools (e.g. system modifications, file writes, code execution).

3. **Spoken Confirmation Interlock (TOOL-06)**:
   - Any tool assigned `confirm` tier MUST pause execution and ask the user for explicit spoken confirmation.
   - Prompt format is strictly clean and concise: `"Can I use tool <name>?"` (D-06).
   - Non-affirmative responses or timeouts default to **DENIED** (D-08).

4. **Auditing and Verification**:
   - Every permission request, grant, and denial is logged as a non-repudiable audit row in `paaf-trace`.
   - `paaf prompt` prints exact bytes sent to the model without alteration.
