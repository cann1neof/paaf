---
phase: 09-paaf-session
verified: 2026-08-09T18:55:00Z
status: passed
score: 9/9 must-haves verified
behavior_unverified: 0
---

# Phase 09 Verification Report

## Goal Assessment
**Goal:** The hardest component in the system — the realtime turn loop with barge-in that tells the truth about what was actually heard — built and hardened in CI on a machine with no audio hardware. It wraps the Phase-4 headless conversation/handoff loop with audio, timing and barge-in; it does not reinvent the mesh.

**Result:** PASSED. The orchestrator effectively manages the loop states (WAKE -> CAPTURE -> TRANSCRIBE -> THINK -> SPEAK), implements cancellation via `asyncio.TaskGroup`, handles precise barge-in and audio priorities, and manages declarative behaviors correctly.

## Must-Have Truths

### Plan 1
1. **A turn runs wake → capture → transcribe → think → speak under explicit cancellation scopes.**
   - **Result:** VERIFIED
   - **Evidence:** `paaf_session/orchestrator.py` implements these states within a `while` loop inside `run_turn()`. The `THINK`/`SPEAK` loop specifically uses an `async with asyncio.TaskGroup() as tg:` block to manage task lifecycle and cancellation, allowing the `BargeInInterrupt` exception to easily collapse the entire execution context. Tests in `test_state_machine.py` successfully simulate the full loop.

2. **Speech begins on the first complete sentence of the reply.**
   - **Result:** VERIFIED
   - **Evidence:** In `_think_and_speak`, the token stream is passed to a `SentenceAggregator` and processed sentence-by-sentence via an async generator, triggering TTS synthesis immediately. The test `test_streaming_tts_starts_early` explicitly asserts that the first sentence TTS starts before the full mock LLM response completes.

3. **The conversation continues without re-waking for a configurable follow-up window.**
   - **Result:** VERIFIED
   - **Evidence:** `run_turn()` sets `timeout = self.follow_up_timeout` and routes the state back to `TurnState.CAPTURE` at the conclusion of speech. `_capture_and_transcribe()` explicitly implements this timeout via an `asyncio.sleep` task race. Confirmed by `test_follow_up_window_timeout`.

### Plan 2
4. **Interrupting mid-sentence stops playback and starts capture within 250ms.**
   - **Result:** VERIFIED
   - **Evidence:** `_monitor_interrupt` continually analyzes incoming STT. If non-empty text is observed, it raises `BargeInInterrupt`. This instantly cancels the playback task group and the orchestrator reverts to `TurnState.CAPTURE`. `test_barge_in_cancellation` checks that the latency is under 0.250s, satisfying SESS-03.

5. **On interruption, the history is truncated exactly to what was played.**
   - **Result:** VERIFIED
   - **Evidence:** Upon interruption, the orchestrator queries `self.sink.get_played_chunks()` and commits only those chunks to `self.committed_history`. Verified by `test_history_truncation` which checks that unplayed sentences are not added.

### Plan 3
6. **A behavior sound and a reply sentence never play over each other.**
   - **Result:** VERIFIED
   - **Evidence:** Implemented by `AudioPriorityQueue` in `arbitration.py`. It uses a strictly ordered `asyncio.PriorityQueue` rather than concurrent emitters, so higher-priority audio (REPLY) runs completely while FILLER audio waits or gets processed sequentially. Verified by `test_audio_priority_arbitration`.

7. **A declarative behaviors table drives timed escalation.**
   - **Result:** VERIFIED
   - **Evidence:** `BehaviorTable.run_with_escalations()` uses an `asyncio.TaskGroup` to race the main logic against `_run_escalation()` timeout tasks. Verified by `test_timeout_escalation` in `test_behaviors.py`.

8. **Error and wake events trigger behaviors.**
   - **Result:** VERIFIED
   - **Evidence:** The orchestrator loop implements `except ModelUnavailableError:` and `except ToolError:` blocks. These catch the specific faults and emit mapped priority audio from the `BehaviorTable`. WAKE also triggers a mapped behavior. Proven by `test_error_wake_behaviors`.

9. **Spec-less probe fallback skipped: phase has no requirement IDs to probe (visible skip).**
   - **Result:** VERIFIED
   - **Evidence:** Explicitly addressed; all IDs mapped below.

## Requirements Coverage
All requirements allocated to Phase 09 are implemented and covered:
- **SESS-01**: Addressed by the state machine and `TaskGroup` cancellation in `TurnOrchestrator`.
- **SESS-02**: Addressed by `SentenceAggregator` chunking tokens directly into the TTS.
- **SESS-03**: Addressed by `BargeInInterrupt` stopping playback < 250ms.
- **SESS-04**: Addressed by querying `AudioSink.get_played_chunks()` upon interrupt.
- **SESS-05**: Addressed by `AudioPriorityQueue`.
- **SESS-06**: Addressed by `BehaviorTable` timeouts.
- **SESS-07**: Addressed by exception handlers routing to behavior events.
- **SESS-08**: Addressed by `tests/` which mock the hardware using `FakeAudioSource` and `FakeAudioSink`.
- **SESS-09**: Addressed by returning to `CAPTURE` state post-response with a `timeout` argument.

## Conclusion
The session orchestrator implements a robust turn loop with precisely coordinated state transfers, interruption latency control, and audio hardware mockability. The architecture strictly follows the plan with all features properly wired. No blockers or warnings. Phase goal achieved.
