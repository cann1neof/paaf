---
phase: 09-paaf-session
plan: 01
subsystem: paaf-session
tags:
  - state-machine
  - audio-streaming
  - session-management
requires:
  - paaf-voice (AudioSource, AudioSink, STT, TTS)
provides:
  - TurnOrchestrator
affects:
  - paaf-session.orchestrator
tech_stack_added:
  - asyncio.TaskGroup
key_files_created:
  - packages/paaf-session/src/paaf_session/orchestrator.py
  - packages/paaf-session/tests/test_state_machine.py
key_files_modified: []
decisions:
  - "Combined all 3 tasks (tracer, streaming TTS, follow-up window) into a single atomic commit because they were implemented concurrently with the same testbed."
actuals:
  tokens: 2341
  tasks: 3
  commits: 1
status: complete
---

# Phase 09 Plan 01: End-to-end Turn Loop and Streaming TTS Summary

Implemented the core asyncio state machine for the conversation loop using `asyncio.TaskGroup`, integrating early TTS streaming and follow-up window transitions.

## Deviations from Plan

### Combined Tasks
- **Found during:** Task execution
- **Issue:** The three tasks (tracer turn loop, streaming TTS, follow-up window) shared the same test setup and implementation surface.
- **Fix:** Implemented and tested all three requirements simultaneously, recording them in a single atomic commit instead of three separate commits.
- **Files modified:** `packages/paaf-session/src/paaf_session/orchestrator.py`, `packages/paaf-session/tests/test_state_machine.py`
- **Commit:** d541217

### Fixed Infinite Test Loop (Rule 1 - Bug)
- **Found during:** Task 3
- **Issue:** `FakeSTT` in `paaf_voice.testing.fakes` loops endlessly over `canned_transcriptions`, causing infinite state machine loops in `test_follow_up_window_timeout`.
- **Fix:** Created a `OneShotSTT` test double within `test_state_machine.py` that yields an empty string on subsequent calls to correctly simulate silence/timeout after the first turn.

## Self-Check: PASSED
- `packages/paaf-session/src/paaf_session/orchestrator.py` exists
- `packages/paaf-session/tests/test_state_machine.py` exists
- Commit `d541217` exists
