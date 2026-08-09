# Phase 9: paaf-session - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-09
**Phase:** 09-paaf-session
**Areas discussed:** State Machine Implementation, History Truncation Strategy, Escalation Timers, Follow-up Window

---

## State Machine Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| Bespoke async loop | Bespoke async loop using `asyncio.TaskGroup` and `asyncio.Event` flags (gives us absolute, low-level control over cancellation for the 250ms barge-in latency requirement). | ✓ |
| Formal library | Formal state machine library like `transitions` or `statemachine` (provides rigid transition rules, strict state boundaries, and easy visualizability). | |

**User's choice:** (Recommended) Bespoke async loop using `asyncio.TaskGroup` and `asyncio.Event`
**Notes:** User asked for more details on the options before selecting the bespoke async loop for cleaner cancellation integration.

---

## History Truncation Strategy (Barge-in)

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit Sink feedback | The AudioSink explicitly reports back which sentence chunks have finished playing. | ✓ |
| Playhead time calc | We calculate based on the virtual playhead time. | |

**User's choice:** Explicit Sink feedback
**Notes:** User agreed with explicit feedback, but suggested keeping "What model wanted to say but didn't have enough time to say" in context. This was captured as a Deferred Idea (scope creep).

---

## Escalation Timers (SESS-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Background tasks | Background `asyncio` tasks spawned at the start of the state that sleep and race the main task. | ✓ |
| Sync poll loop | A tick-based synchronous check loop that polls elapsed time every N milliseconds. | |

**User's choice:** Background `asyncio` tasks
**Notes:** N/A

---

## Follow-up Window (SESS-09)

| Option | Description | Selected |
|--------|-------------|----------|
| CAPTURE + timeout | The state machine transitions back to the standard `CAPTURE` state, but passes a timeout parameter. | ✓ |
| Distinct state | We create a distinct `FOLLOW_UP` state that explicitly handles the timeout logic before transitioning. | |

**User's choice:** CAPTURE + timeout
**Notes:** N/A

---

## the agent's Discretion

None

## Deferred Ideas

- Storing the "unspoken intention" (what the model wanted to say but was interrupted) to pass back as context for a smoother continuation.
