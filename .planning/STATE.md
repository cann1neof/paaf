---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: spike-gate
status: executing
stopped_at: Completed 01-04-PLAN.md
last_updated: "2026-07-25T07:13:11.059Z"
last_activity: 2026-07-23
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 12
  completed_phases: 0
  total_plans: 10
  completed_plans: 7
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-19)

**Core value:** The user owns the assistant's mind — they pick the model, write its persona, install its skills, expose its tools, and decide what it does while it thinks, without writing code and with nothing hidden from them.
**Current focus:** Phase 01 — spike-gate

## Current Position

Phase: 01 (spike-gate) — EXECUTING
Plan: 7 of 10
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
| Phase 01 P03 | 35min | 3 tasks | 5 files |
| Phase 01 P04 | 25min | 3 tasks | 5 files |
| Phase 01 P05 | 26min | 2 tasks | 9 files |
| Phase 01 P07 | 39min | 2 tasks | 5 files |

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
- [Phase 01]: GATE 0 is GREEN: Hebrew is synthesized WITH diacritics, usable device is mps, and seeded synthesis is bitwise identical so D-07's re-run-and-diff promise holds — Gate 0 must pass before any Hebrew clip reaches a native ear (Pitfall 1); MPS working contradicts the pessimistic prior and removes the expected CPU fallback
- [Phase 01]: UPSTREAM DEFECT: chatterbox-tts 0.1.7 calls Dicta() with no args while every dicta-onnx release requires model_path, and swallows the TypeError — 'pip install dicta-onnx' alone does NOT fix Pitfall 1 — The TypeError falls to except Exception, not except ImportError, so a different warning fires than Pitfall 1 says to watch for while Hebrew still reaches the model unvocalized; the repair seeds chatterbox's _dicta global so the measured pipeline stays the intended one
- [Phase 01]: Every Hebrew result must be attributed to CONFIG_REPAIRED, with CONFIG_DEFAULT reported separately as what a plain pip install yields — D-05: what an ordinary user gets is itself a finding; naming both configurations stops any result being quoted without its assembly
- [Phase 01]: Ollama model default RE-CHECKED and CHANGED: plain qwen3 is no longer in the top-20 tool-capable models, and qwen3.6 is disqualified because its ladder starts at 27b/17GB on an 18GB machine. Chose qwen3.5:9b (capability, SPIKE-05/06/07) + qwen3.5:2b (latency, SPIKE-08), both tools-capable and Apache-2.0, pinned by explicit tag never latest
- [Phase 01]: TOOL-CALL GATE GREEN: 30/30 well-formed calls, 100% in every condition, both models, via both the raw ollama client and init_chat_model
- [Phase 01]: PRIVACY BUG: the ollama python client 0.6.2 list() pydantic schema silently drops capabilities, so the PRIV-02 no-cloud check passed VACUOUSLY for every tag including the real qwen3.5:cloud. capabilities_of now reads /api/show and treats an empty list as an error
- [Phase 01]: Telemetry-off is enforced at TWO levels: langsmith and logfire-api ship as hard transitive deps of langchain and pydantic-ai, so env vars alone cannot establish PRIV-02. Runtime state is asserted and the plan's four vars were extended to nine incl. OTEL_EXPORTER_OTLP_ENDPOINT
- [Phase 01]: Held pydantic-ai-slim at 2.13.0 rather than today's 2.16.0. Cadence recorded as Decision-1 evidence: pydantic-ai shipped 7 minors in 9 days, langchain 8 patches in 43 days and is still on 1.3.x
- [Phase ?]: SPIKE-04: Whisper large-v3 locks to one language per clip; multilingual=True does not unlock code-switching (posterior identical 46/46). Embedded language transliterated/garbled into Latin unless locked to a non-Latin language; task=translate flattens to English. D-05 caveat binding: synthetic Chatterbox speech, Chatterbox/Whisper failures inseparable.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

- **Highest-risk unverified claim:** Chatterbox intra-sentence code-switching and Hebrew quality. Phase 1 exists to measure it. If it fails, the founding language promise needs its fallback ladder *before* Phase 6 begins.
- **Hardware not yet owned.** Budget is being saved. Phase 1 measurements determine what class of machine to buy; no phase before 12 may gate on it.
- **`langchain-mcp-adapters` is 0.x** and carries a core user-facing feature outside LangChain's 1.0 stability policy. SPIKE-06 is the falsification test.
- dicta-onnx is now on the CRITICAL PATH for Hebrew (Gate 0 proved Hebrew needs it plus a manually-supplied weights file), yet it declares NO LICENSE on PyPI or GitHub and is thinly maintained (9 stars, single individual, no release since 2025-05-31). An unlicensed transitive dep is a real distribution problem for an Apache-2.0 framework — must be resolved before Phase 6 / packaging.
- The conftest-shadowing trap is only half closed: spike/voice/ avoids it purely because 'voice' sorts after test_fixtures_smoke.py. Any future spike/<earlier-sorting-dir>/conftest.py will break the base suite collection entirely. Durable fix is moving 01-01's FakeModel/FakeTool into spike/fakes.py

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Hardware | Reference build, enclosure, mic-kill switch | Deferred to v2 | Milestone start |
| Memory | Semantic search, long-term conversational memory | Deferred to v2 | Milestone start |
| Routing | Sophisticated LLM-based model routing | Deferred to v2 | Milestone start |

## Session Continuity

Last session: 2026-07-25T07:13:03.706Z
Stopped at: Completed 01-04-PLAN.md
Resume file: None
