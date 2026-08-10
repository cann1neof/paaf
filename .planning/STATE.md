---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 10
current_phase_name: The Appliance
status: planning
stopped_at: Phase 09.1 context gathered
last_updated: "2026-08-10T08:33:00.042Z"
last_activity: 2026-08-09
last_activity_desc: Phase 09 execution started
progress:
  total_phases: 11
  completed_phases: 9
  total_plans: 61
  completed_plans: 61
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-19)

**Core value:** The user owns the assistant's mind — they pick the model, write its persona, install its skills, expose its tools, and decide what it does while it thinks, without writing code and with nothing hidden from them.
**Current focus:** Phase 09 — paaf-session

## Current Position

Phase: 10 — The Appliance
Plan: Not started
Status: Ready to plan
Last activity: 2026-08-09 — Phase 09 complete, transitioned to Phase 10

Progress: [██████████] 100%  (3/3 plans in phase 06)

## Performance Metrics

**Velocity:**

- Total plans completed: 46
- Average duration: ~32 min
- Total execution time: ~25 hours

**Recent Trend:**

- Last 5 plans: ~50 min/plan average
- Trend: stable

*Updated after each plan completion*
| Phase 01 P01 | 12min | 2 tasks | 7 files |
| Phase 01 P02 | 6min | 3 tasks | 4 files |
| Phase 01 P03 | 35min | 3 tasks | 5 files |
| Phase 01 P04 | 25min | 3 tasks | 5 files |
| Phase 01 P05 | 26min | 2 tasks | 9 files |
| Phase 01 P07 | 39min | 2 tasks | 5 files |
| Phase 01 P09 | 37min | 2 tasks | 7 files |
| Phase 01 P10 | 15min | 2 tasks | 5 files |
| Phase 02 P01 | 15min | 2 tasks | 20 files |
| Phase 02 P02 | 12min | 3 tasks | 10 files |
| Phase 02 P03 | 5min | 2 tasks | 5 files |
| Phase 02 P04 | 3min | 2 tasks | 8 files |
| Phase 02 P05 | 3min | 2 tasks | 4 files |
| Phase 02 P06 | 8min | 1 tasks | 3 files |
| Phase 02 P07 | 25min | 3 tasks | 8 files |
| Phase 02 P08 | 4min | 3 tasks | 7 files |
| Phase 02 P09 | 12min | 2 tasks | 4 files |
| Phase 04 P01 | 50m | 3 tasks | 11 files |
| Phase 04 P02 | ~35 min | 2 tasks | 6 files |
| Phase 04 P03 | ~30 min | 3 tasks | 9 files |
| Phase 04 P04 | 25min | 2 tasks | 4 files |
| Phase 04 P05 | 55min | 3 tasks | 9 files |
| Phase 04 P06 | ~65 min | 3 tasks | 9 files |
| Phase 04 P07 | ~70 min | 3 tasks | 7 files |
| Phase 04 P08 | ~35 min | 3 tasks | 6 files |
| Phase 04 P09 | ~20 min | 2 tasks | 5 files |
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 09 P01 | 5min | 3 tasks | 2 files |
| Phase 09-paaf-session P02 | 9min | 2 tasks | 5 files |
| Phase 09 P03 | 25min | 3 tasks | 5 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 1 is throwaway spike code. Nothing ships from it; its exit gate constrains every later public claim about multilingual behavior.
- [Roadmap]: Fake adapters precede real implementations in both `paaf-llm` (Phase 3) and `paaf-voice` (Phase 6). A port with one implementation is a mirror.
- [Roadmap]: Import contracts (FOUND-04), endpoint declaration (CORE-05) and the TTFA CI gate (TRACE-04) all land in Phase 2 — retrofitting any of them is an unwinnable audit.
- [Roadmap]: `paaf-llm` ships to PyPI in Phase 5, mid-roadmap, as burnout mitigation — not at launch.
- [Roadmap]: Only Phase 12 is hardware-gated. AEC quality, far-field accuracy, real-device latency, and GPIO are the only four things needing the target device.
- [Phase 04]: Hop budget floor and default are ONE constant (mesh.HOP_BUDGET_FLOOR=3), imported by the Pydantic constraint.
- [Phase 04]: At budget exhaustion with no default_agent, the currently-awake agent answers with the tools withdrawn (OQ-2).
- [Phase 04]: Assumption A1 CONFIRMED: tool calls execute with 30/30 (100%) reliability across local models.
- [Phase 04]: Explainer generated from capability manifest and peer graph is inspectable verbatim in prompt inspector (MESH-04, PERS-05).
- [Phase 04]: Trace schema carries turn_legs and handoffs rows correlated by turn_id (MESH-05).
- [Phase 04]: The observer is a reserved profile name ('observer') judging handoffs via tool grants (MESH-06).
- [Phase 04]: Unobserved mesh operations and fail-open loud behavior state plainly when unobserved or unreachable (D-07, OQ-4).
- [Phase ?]: [Phase 09]: Combined all 3 tasks (tracer, streaming TTS, follow-up window) into a single atomic commit because they were implemented concurrently with the same testbed.
- [Phase ?]: Wrapped TTS synthesis inside a TaskGroup to allow immediate cancellation via BargeInInterrupt.
- [Phase ?]: Updated AudioSink port to track history via mark_chunk and get_played_chunks.
- [Phase ?]: Decided to implement audio arbitration as a non-blocking queue to prevent hot path stalls.
- [Phase ?]: Implemented declarative behaviors using task group racing so background delays handle escalation.

### Pending Todos

None.

### Blockers/Concerns

None.

### Roadmap Evolution

- Phase 4 completed: Agent Mesh (LLM-driven handoff with observer constraints and trace auditability).
- Phase 9.1 inserted after Phase 9: Restructure project folders and publish framework to PyPI (URGENT)

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Hardware | Reference build, enclosure, mic-kill switch | Deferred to v2 | Milestone start |
| Memory | Semantic search, long-term conversational memory | Deferred to v2 | Milestone start |
| Routing | Automated mis-route detection / routing-quality eval (ROUTE-01) | Deferred to v2 | 2026-08-04 |

## Session Continuity

Last session: 2026-08-10T08:33:00.020Z
Stopped at: Phase 09.1 context gathered
Resume file: /Users/alexanderikonnikov/Documents/repos/paaf/.planning/phases/09.1-restructure-project-folders-and-publish-framework-to-pypi/09.1-CONTEXT.md
