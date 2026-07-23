---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: spike-gate
status: executing
stopped_at: Completed 01-01-PLAN.md
last_updated: "2026-07-23T10:33:07.099Z"
last_activity: 2026-07-23
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 10
  completed_plans: 2
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-19)

**Core value:** The user owns the assistant's mind — they pick the model, write its persona, install its skills, expose its tools, and decide what it does while it thinks, without writing code and with nothing hidden from them.
**Current focus:** Phase 01 — spike-gate

## Current Position

Phase: 01 (spike-gate) — EXECUTING
Plan: 3 of 10
Status: Ready to execute
Last activity: 2026-07-23 — Phase 01 execution started

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 12min | 2 tasks | 7 files |
| Phase 01 P02 | 6min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 1 is throwaway spike code. Nothing ships from it; its exit gate constrains every later public claim about multilingual behavior.
- [Roadmap]: Fake adapters precede real implementations in both `paaf-llm` (Phase 3) and `paaf-voice` (Phase 6). A port with one implementation is a mirror.
- [Roadmap]: Import contracts (FOUND-04), endpoint declaration (CORE-05) and the TTFA CI gate (TRACE-04) all land in Phase 2 — retrofitting any of them is an unwinnable audit.
- [Roadmap]: `paaf-llm` ships to PyPI in Phase 5, mid-roadmap, as burnout mitigation — not at launch.
- [Roadmap]: Only Phase 12 is hardware-gated. AEC quality, far-field accuracy, real-device latency, and GPIO are the only four things needing the target device.
- [Phase ?]: [01-01] Phase 1 throwaway code is quarantined under spike/; SC#5 is enforceable by one 'ls'. Test config lives INSIDE spike/ — no root pyproject.toml, pytest.ini or .venv, since Phase 2 (FOUND-01) owns the uv workspace.
- [Phase ?]: [01-01] Toolchain baseline: uv 0.11.31, CPython 3.12.13, ffmpeg 8.1.2, pytest 9.1.1 + pytest-asyncio 1.4.0 in spike/.venv. Canonical test command is 'uv run --python spike/.venv/bin/python pytest spike/ -q' — a bare 'uv run' cannot resolve without a root project.
- [Phase ?]: [01-01] Shared spike fixtures import stdlib + pytest only, so they collect in both the voice and bake-off venvs. The device fixture yields the STRINGS 'cpu'/'mps' because Chatterbox compares device by string equality despite its torch.device type hint.
- [Phase 01]: Corpus same-script category uses Cyrillic/Latin homoglyph pairs (РЕСТОРАН vs PECTOPAH), never Latin transliteration of Russian — Transliteration bypasses Chatterbox's russian_text_stresser / add_hebrew_diacritics paths entirely, so the spike would measure a pipeline it never ran (01-RESEARCH Pitfall 1)
- [Phase 01]: D-14 blindness is enforced structurally: shuffle_blind refuses to write mapping.json inside the directory being judged, and seed is keyword-only with no default — A mapping next to the clips defeats the blind pass in the most banal way; an unseeded shuffle makes the listening order unreproducible for Phase 7's re-run-and-diff (D-07)
- [Phase 01]: SPIKE-01 left unchecked after 01-02 — this plan builds the measuring instrument, plan 01-05 takes the measurement — SPIKE-01 says 'Measure whether Chatterbox handles intra-sentence code-switching'; no model was loaded here, and a premature checkbox is exactly what the SC#4 claim audit exists to catch

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

- **Highest-risk unverified claim:** Chatterbox intra-sentence code-switching and Hebrew quality. Phase 1 exists to measure it. If it fails, the founding language promise needs its fallback ladder *before* Phase 6 begins.
- **Hardware not yet owned.** Budget is being saved. Phase 1 measurements determine what class of machine to buy; no phase before 12 may gate on it.
- **`langchain-mcp-adapters` is 0.x** and carries a core user-facing feature outside LangChain's 1.0 stability policy. SPIKE-06 is the falsification test.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Hardware | Reference build, enclosure, mic-kill switch | Deferred to v2 | Milestone start |
| Memory | Semantic search, long-term conversational memory | Deferred to v2 | Milestone start |
| Routing | Sophisticated LLM-based model routing | Deferred to v2 | Milestone start |

## Session Continuity

Last session: 2026-07-23T10:33:07.094Z
Stopped at: Completed 01-01-PLAN.md
Resume file: None
