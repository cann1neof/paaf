# Phase 9: paaf-session - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning

<domain>
## Phase Boundary

The realtime turn loop with barge-in that tells the truth about what was actually heard, built and hardened in CI on a machine with no audio hardware. It wraps the Phase-4 headless conversation/handoff loop with audio, timing, and barge-in (SESS-01 through SESS-09). It does not reinvent the mesh.

</domain>

<decisions>
## Implementation Decisions

### State Machine Implementation
- **D-01:** Implement a bespoke async loop using `asyncio.TaskGroup` and `asyncio.Event` flags for state tracking. — **Reversibility:** costly — Requires refactoring the core turn loop if strict state constraints become too difficult to manage manually, but provides the necessary absolute low-level control over cancellation for the 250ms barge-in latency requirement.

### History Truncation Strategy (Barge-in)
- **D-02:** The AudioSink explicitly reports back which sentence chunks have finished playing, and sentences are only committed to history once confirmed by the sink. — **Reversibility:** costly — Couples history tracking to explicit sink feedback rather than playhead time estimations, providing exact truth without estimation.

### Escalation Timers (SESS-06)
- **D-03:** Execute timeouts via background `asyncio` tasks spawned at the start of the state that sleep and race the main task. — **Reversibility:** reversible — Clean `asyncio` integration that fires exactly when needed, avoiding CPU-heavy polling loops.

### Follow-up Window (SESS-09)
- **D-04:** The state machine transitions back to the standard `CAPTURE` state, passing a timeout parameter. — **Reversibility:** reversible — Reuses existing capture logic and keeps the state count low.

### the agent's Discretion
None — all 4 implementation decisions were explicitly selected.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Requirements
- `.planning/ROADMAP.md` § Phase 9 — paaf-session goal and scope
- `.planning/REQUIREMENTS.md` — Requirements SESS-01 through SESS-09

### Prior Phase Context
- `.planning/phases/08-real-engines-live-audio/08-CONTEXT.md` — STT/TTS engine interfaces
- `.planning/phases/07-paaf-voice-ports-fakes/07-CONTEXT.md` — Voice ports and test doubles (`FakeAudioSink`, `FakeAudioSource`)
- `.planning/phases/04-agent-mesh/04-CONTEXT.md` — Headless agent mesh and conversation handoff mechanics

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `paaf_voice.ports` (AudioSource, AudioSink, STTPort, TTSPort, WakeWordPort, VADPort): Provides the interfaces for the loop to interact with audio.
- `FakeAudioSource` and `FakeAudioSink` in `paaf_voice.testing`: Essential for deterministic testing in CI without hardware.
- Sentence aggregator (`paaf_voice`): Splits LLM output into chunks.

### Established Patterns
- Zero-hardware CI testing for audio components using fake WAV fixtures.
- Pure `asyncio` concurrency for audio/LLM streaming.

### Integration Points
- `packages/paaf-session`: The new package integrating `paaf-voice` audio streams with `paaf-llm`'s conversational agent mesh.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- **Unspoken Intention Memory:** Storing what the model "wanted to say but didn't have enough time to say" on barge-in, to pass back as context so the model can smoothly continue its thought (e.g., "exactly, it was something i was gonna say..."). Deferred to a future conversation memory phase.

</deferred>

---

*Phase: 09-paaf-session*
*Context gathered: 2026-08-09*
