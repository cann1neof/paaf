---
phase: 09
plan: 03
subsystem: paaf-session
tags:
  - behaviors
  - arbitration
  - orchestrator
requires: [paaf-voice]
provides: [paaf-session audio queue]
affects: [orchestrator state machine]
tech_stack:
  added:
    - asyncio TaskGroup
  patterns_used:
    - Non-blocking async queue
    - TaskGroup Racing State Machine
key_files:
  created:
    - packages/paaf-session/src/paaf_session/arbitration.py
    - packages/paaf-session/src/paaf_session/behaviors.py
    - packages/paaf-session/tests/test_audio_arbitration.py
    - packages/paaf-session/tests/test_behaviors.py
  modified:
    - packages/paaf-session/src/paaf_session/orchestrator.py
key_decisions:
  - "Decided to implement audio arbitration as a non-blocking queue to prevent hot path stalls."
  - "Implemented declarative behaviors using task group racing so background delays handle escalation."
status: complete
actuals:
  tokens: 65000
  tasks: 3
  commits: 5
---

# Phase 09 Plan 03: Audio Arbitration and Declarative Behaviors Summary

Implemented audio arbitration using a priority queue to ensure filler sounds and reply sentences do not overlap. Introduced a declarative behaviors table that uses asyncio TaskGroups to spawn background timeouts, emitting mapped behaviors when timers trigger. Mapped exceptions for model unavailability and tool errors to emit specific behaviors.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None.

## Self-Check: PASSED
