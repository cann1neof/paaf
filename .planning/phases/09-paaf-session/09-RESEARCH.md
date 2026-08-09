# Phase 09: paaf-session - Research

**Researched:** 2026-08-09
**Domain:** Realtime Turn Orchestration & Concurrency Control
**Confidence:** HIGH

## Summary

This phase implements `paaf-session`, the central state machine and turn loop that wraps the headless `paaf-llm` agent mesh with audio, timing, and barge-in semantics. It bridges `paaf-voice` streams and `paaf-llm` text generation. The entire lifecycle operates in an asynchronous loop built on `asyncio.TaskGroup` and `asyncio.Event` flags to tightly control cancellation scopes and meet the strict 250ms barge-in latency requirement. 

**Primary recommendation:** Implement a custom `asyncio.TaskGroup`-based state machine where state transitions cancel and recreate tasks, relying on explicit feedback from `paaf_voice.ports.AudioSink` to assert the true conversation history upon barge-in.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Implement a bespoke async loop using `asyncio.TaskGroup` and `asyncio.Event` flags for state tracking. — **Reversibility:** costly — Requires refactoring the core turn loop if strict state constraints become too difficult to manage manually, but provides the necessary absolute low-level control over cancellation for the 250ms barge-in latency requirement.
- **D-02:** The AudioSink explicitly reports back which sentence chunks have finished playing, and sentences are only committed to history once confirmed by the sink. — **Reversibility:** costly — Couples history tracking to explicit sink feedback rather than playhead time estimations, providing exact truth without estimation.
- **D-03:** Execute timeouts via background `asyncio` tasks spawned at the start of the state that sleep and race the main task. — **Reversibility:** reversible — Clean `asyncio` integration that fires exactly when needed, avoiding CPU-heavy polling loops.
- **D-04:** The state machine transitions back to the standard `CAPTURE` state, passing a timeout parameter. — **Reversibility:** reversible — Reuses existing capture logic and keeps the state count low.

### the agent's Discretion
None — all 4 implementation decisions were explicitly selected.

### Deferred Ideas (OUT OF SCOPE)
- **Unspoken Intention Memory:** Storing what the model "wanted to say but didn't have enough time to say" on barge-in, to pass back as context so the model can smoothly continue its thought (e.g., "exactly, it was something i was gonna say..."). Deferred to a future conversation memory phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SESS-01 | A turn state machine drives wake → capture → transcribe → think → speak, with explicit cancellation scopes | Addressed by D-01: Bespoke async loop using `asyncio.TaskGroup`. |
| SESS-02 | LLM tokens stream into sentence-chunked TTS so speech begins on the first complete sentence, not the full reply | Reuse sentence aggregator from `paaf_voice` and stream via async generators. |
| SESS-03 | User interrupts the assistant mid-sentence; playback stops and capture begins within 250ms | `TaskGroup` cancellation combined with `AudioSink` immediate flush guarantees sub-250ms termination. |
| SESS-04 | On interruption, conversation history is truncated to what was actually played out of the speaker, not what the model generated | Addressed by D-02: explicit feedback tracking which sentences the sink played. |
| SESS-05 | Audio output is arbitrated by priority so a behavior sound and a reply sentence never play over each other | Introduce a prioritized Audio Priority Queue feeding the sink. |
| SESS-06 | A declarative behaviors table drives timed escalation during a long request — a sound at one threshold, speech at another, ambient audio at a third | Addressed by D-03: background racing `asyncio.sleep` tasks spawning escalation events. |
| SESS-07 | Behaviors also cover model-unavailable, tool-error, and on-wake events | Hook error catchers in state machine transitions to emit behavior events. |
| SESS-08 | The full turn lifecycle including barge-in is tested deterministically in CI with fake audio and a virtual playhead, no hardware | Rely on `FakeAudioSource` and `FakeAudioSink` emitting events deterministically in a Pytest event loop. |
| SESS-09 | Conversation continues without re-waking for a configurable follow-up window | Addressed by D-04: Transition to `CAPTURE` with a timeout parameter. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Turn State Machine (SESS-01) | API / Backend | — | Core logic residing entirely within the `paaf-session` Python process. |
| History Truncation (SESS-04) | API / Backend | — | The session orchestrator receives sink reports and mutates the `paaf-llm` memory store before next turn. |
| Escalation Timers (SESS-06) | API / Backend | — | Asynchronous sleep tasks running alongside the orchestrator in the backend loop. |
| Hardware Test Fakes (SESS-08) | Test Fixtures | — | Emulates hardware boundaries completely in-memory using `pytest-asyncio`. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` | (stdlib) | Concurrency & state machine | Built-in async primitives, zero external dependencies. |
| `pytest-asyncio` | ^0.23.0 | Asynchronous testing | De-facto standard for testing async loops in Python. |

**Installation:**
No new production packages needed.

## Architecture Patterns

### Pattern 1: `TaskGroup` Racing State Machine
**What:** Spawning a main task and competing background timer/escalation tasks using `asyncio.TaskGroup`.
**When to use:** Managing timeout behaviors (SESS-06, SESS-09) and barge-in (SESS-03) where events race against completion.
**Example:**
```python
import asyncio

async def run_state(timeout: float):
    try:
        async with asyncio.TaskGroup() as tg:
            main_task = tg.create_task(do_work())
            timeout_task = tg.create_task(asyncio.sleep(timeout))
            
            # First one to finish triggers cancellation of the other
            done, pending = await asyncio.wait(
                [main_task, timeout_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if timeout_task in done:
                # Handle timeout escalation
                pass
                
    except asyncio.CancelledError:
        # Handle barge-in (external cancellation)
        raise
```

### Pattern 2: Sink Confirmation for History (SESS-04)
**What:** The `AudioSink` API must return identifiers (or indices) of completed playback chunks.
**When to use:** Truncating LLM generated messages before appending to conversation memory.
**Example:**
```python
async for sentence in llm_stream:
    chunk_id = await tts.synthesize(sentence)
    await audio_sink.enqueue(chunk_id)

# Upon barge-in:
played_chunks = audio_sink.get_played_chunks()
history.append(" ".join(sentences[i] for i in played_chunks))
```

### Anti-Patterns to Avoid
- **CPU Polling:** Do not use `while time.time() < end_time:` loops for timeout checks. Always use `asyncio.sleep` to release the event loop (D-03).
- **Time-based estimation:** Do not guess how much audio played based on time elapsed since playback started. Use explicit chunk completion feedback (D-02).
- **Nested exception hiding:** Do not blanket-catch `Exception` in state tasks without explicitly catching and re-raising `asyncio.CancelledError`. Doing so breaks barge-in responsiveness.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Task teardown | Custom task registries | `asyncio.TaskGroup` | Ensures hard cancellation guarantees across all children without orphan tasks. |
| Concurrency flags | Shared mutable booleans | `asyncio.Event` | Thread-safe async waiting instead of CPU-bound polling loops. |

## Common Pitfalls

### Pitfall 1: Orphaned Background Tasks on Barge-In
**What goes wrong:** A barge-in triggers state transition, but a previously spawned timeout/escalation task keeps running and fires later during a new state.
**Why it happens:** Spawning tasks using `asyncio.create_task()` without tracking or cancelling them when the state ends.
**How to avoid:** Always enclose state operations and their associated timeouts within an `asyncio.TaskGroup`.

### Pitfall 2: Audio Sink Buffer Underruns vs Overwrites
**What goes wrong:** Sentence 2 finishes TTS and is sent to the sink while Sentence 1 is still playing. If the sink isn't a queue, it overwrites Sentence 1.
**Why it happens:** Misunderstanding the sink interface.
**How to avoid:** Ensure the `AudioSink` interface behaves as a queue or blocks until ready, avoiding overlapping playback. 

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Quick run command | `uv run pytest packages/paaf-session/tests/ -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SESS-01 | State machine transitions correctly | unit | `pytest packages/paaf-session/tests/ -k test_state_transitions` | ❌ Wave 0 |
| SESS-02 | TTS streaming begins on first sentence | unit | `pytest packages/paaf-session/tests/ -k test_streaming_tts_starts_early` | ❌ Wave 0 |
| SESS-03 | Barge-in cancels playback <250ms | unit | `pytest packages/paaf-session/tests/ -k test_barge_in_cancellation_latency` | ❌ Wave 0 |
| SESS-04 | History truncates to played sentences | integration | `pytest packages/paaf-session/tests/ -k test_history_truncation_on_barge_in` | ❌ Wave 0 |
| SESS-05 | Behavior sound preempts output | unit | `pytest packages/paaf-session/tests/ -k test_audio_priority_arbitration` | ❌ Wave 0 |
| SESS-06 | Escalation fires on timeout | unit | `pytest packages/paaf-session/tests/ -k test_timeout_escalation_triggers` | ❌ Wave 0 |
| SESS-07 | Error events trigger behaviors | unit | `pytest packages/paaf-session/tests/ -k test_error_behavior_triggers` | ❌ Wave 0 |
| SESS-08 | Fake audio testing without hardware | integration | `pytest packages/paaf-session/tests/ -k test_full_turn_with_fakes` | ❌ Wave 0 |
| SESS-09 | Follow-up window transition | unit | `pytest packages/paaf-session/tests/ -k test_follow_up_window_timeout` | ❌ Wave 0 |

### Wave 0 Gaps
- [ ] `packages/paaf-session/tests/test_state_machine.py` — covers SESS-01, SESS-06, SESS-09
- [ ] `packages/paaf-session/tests/test_barge_in.py` — covers SESS-03, SESS-04
- [ ] `packages/paaf-session/tests/test_audio_arbitration.py` — covers SESS-02, SESS-05
- [ ] `packages/paaf-session/tests/test_fakes.py` — covers SESS-08

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No external dependencies or hardware drivers are required for this phase due to reliance on Fake audio ports | Environment | Build requires missing C-libraries or system components |

## Open Questions (RESOLVED)

1. **Audio priority implementation (SESS-05)**
   - What we know: A behavior sound and reply sentence shouldn't overlap.
   - What's unclear: Does the AudioSink handle prioritization, or does the session orchestrator maintain a priority queue and feed the sink?
   - Recommendation: The session orchestrator should own the priority logic, only handing the sink the audio it explicitly wants played *now*.
   - RESOLVED: Yes, follow the recommendation. The session orchestrator owns priority logic.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - `asyncio` built-ins are required by decision D-01.
- Architecture: HIGH - Dictated directly by CONTEXT.md decisions.
- Pitfalls: HIGH - Well-documented asynchronous Python orchestration pitfalls.

**Research date:** 2026-08-09
**Valid until:** 2026-09-09
