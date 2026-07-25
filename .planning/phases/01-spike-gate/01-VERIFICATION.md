---
phase: 01-spike-gate
verified: 2026-07-25T00:00:00Z
status: passed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
notes:
  - "ROADMAP marks this phase mode: mvp, but the goal is not a User Story ('As a…, I want to…, so that…'). Verified against the 5 explicit ROADMAP Success Criteria (the contract) using standard goal-backward methodology; MVP User-Flow-Coverage was not applicable to a spike-gate measurement phase. Informational, not a gap."
  - "SC#5 (no phase code survives) is a forward-looking prohibition. spike/ still exists but is quarantined (gitignored venvs), its durable content is lifted into .planning/, and it is flagged for deletion at phase close (DECISIONS.md §'No code from this phase survives'). Per launch instructions, impending deletion is NOT a gap. Reminder only: physically delete spike/ at phase boundary."
---

# Phase 1: Spike Gate Verification Report

**Phase Goal:** Replace the project's five load-bearing unverified claims with measurements, so the language promise, the agent-framework choice, and the hardware purchase are all decided by evidence rather than hope.
**Verified:** 2026-07-25
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

This is a spike-gate phase: the deliverable is recorded MEASUREMENTS and DECISIONS, not shippable code (SC#5 / D-18). Verification confirms the durable measurement artifacts exist, are substantive, and that every derived claim in `01-RESULTS.md` and `DECISIONS.md` traces back faithfully to a raw record without exceeding it (SC#4).

### Observable Truths (ROADMAP Success Criteria — the contract)

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| SC#1 | Native Hebrew verdict recorded verbatim + ≥20 mixed-script sentences run through Chatterbox (varying `language_id`) and Whisper, incl. lock-on/transliterate/translate | ✓ VERIFIED | `raw/hebrew-verdict.md` = 46 blind judgments (7 Hebrew, all quoted verbatim in DECISIONS §2); `corpus/corpus.jsonl` = 20 mixed en/ru/he/es sentences; 46 WAVs rendered (`corpus/timings.jsonl`); 138 Whisper rows (`corpus/transcripts.jsonl`); lock-on documented RESULTS §3 |
| SC#2 | TTFA known on Mac MPS and CPU + per-stage round-trip budget → hardware class | ✓ VERIFIED | `raw/ttfa.md` warm p50 mps 6.27s / cpu 21.70s (matches RESULTS §4); `raw/roundtrip.md` per-stage budget STT 34.1% / LLM 1.4% / TTS 64.5%, residual ≈0 (RESULTS §5); hardware inference carries D-12 caveat |
| SC#3 | LangChain vs Pydantic AI behind one port; Ollama token counts + MCP args/results confirmed visible via callbacks | ✓ VERIFIED | `raw/bakeoff-results.md`: 245 vs 228 port lines / 61-vs-61 translation lines (no decisive winner); token counts non-None both (`is_populated: true`); MCP args `{"room":"kitchen"}` + structured result byte-matched to frozen fixture both frameworks (RESULTS §7) |
| SC#4 | `DECISIONS.md` states measured reality in plain language; no repo claim exceeds it | ✓ VERIFIED | `DECISIONS.md` at repo root; D-05 (synthetic-speech) + D-12 (Apple-Silicon-not-CUDA) caveats attached at every citation; Hebrew summarized as "usable" (2 good / 4 fine / 1 partial breakdown) — does not exceed verbatim record; no README/PROJECT.md multilingual prose exists yet (grep clean) |
| SC#5 | No code written in this phase survives into a shipped package | ✓ VERIFIED (on-track) | Throwaway code confined to `spike/` (gitignored venvs); durable measurements lifted into `.planning/`; flagged for deletion (DECISIONS §final). No shipped package exists. Physical deletion is a phase-boundary reminder, not a gap |

**Score:** 5/5 Success Criteria verified (0 present-but-behavior-unverified)

### Plan-level truths (all backed by raw evidence)

- 01-08: verdict verbatim, no rating scale, blind-then-joined (D-14), Hebrew deep + ru/es spot-check (D-20 surfaced c20 ru & c03 es catastrophes), judged after Gate 0 — all evidenced in `raw/hebrew-verdict.md` / `raw/hebrew-judgments.json`.
- 01-09: TTFA mps AND cpu warm (cold excluded), round-trip budget with explicit `unattributed`≈0 residual (Pitfall 10), hardware inference tagged D-12, walking-skeleton round trip ran end-to-end — all in `raw/ttfa.md` / `raw/roundtrip.md`.
- 01-10: `01-RESULTS.md` committed before `DECISIONS.md` (D-09), caveats carried, no fallback rung locked (D-10 leans "none", explicitly "recorded, not locked"), no prose exceeds measured reality (SC#4 audit DONE) — all confirmed.

### Required Artifacts (durable measurement record)

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `.planning/phases/01-spike-gate/01-RESULTS.md` | Raw measured record, committed first | ✓ VERIFIED | 8 sections, every number sourced to a raw file; requirement evidence map §8 |
| `DECISIONS.md` (repo root) | Interpretation, links back to raw | ✓ VERIFIED | Present; caveats binding; leans not locks the fallback rung |
| `raw/hebrew-verdict.md` | Verbatim native-ear judgments | ✓ VERIFIED | 46 blind judgments joined to tags; RESULTS/DECISIONS quotes faithful |
| `raw/ttfa.md` | TTFA mps+cpu | ✓ VERIFIED | Numbers match RESULTS §4 exactly |
| `raw/roundtrip.md` | Per-stage latency budget | ✓ VERIFIED | Stage shares + residual match RESULTS §5 |
| `raw/bakeoff-results.md` | SPIKE-05/06/07 findings | ✓ VERIFIED | Token counts, MCP fixture match, port-line counts match RESULTS §7 |
| `corpus/corpus.jsonl` | ≥20 mixed sentences | ✓ VERIFIED | 20 rows, en/ru/he/es code-switched |
| `corpus/{timings,transcripts}.jsonl` | Render + Whisper data | ✓ VERIFIED | 46 timing rows, 138 transcript rows (46×3) |

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
| ----------- | -------------- | ------ | -------- |
| SPIKE-01 | 01-02, 01-03, 01-05 | ✓ SATISFIED | Corpus render + Whisper read + native-ear (RESULTS §1/§2/§3) |
| SPIKE-02 | 01-03, 01-08 | ✓ SATISFIED | Verbatim Hebrew verdict (RESULTS §2, raw/hebrew-verdict.md) |
| SPIKE-03 | 01-09 | ✓ SATISFIED | TTFA mps+cpu (RESULTS §4) |
| SPIKE-04 | 01-07 | ✓ SATISFIED | Whisper lock/transliterate/translate + D-05 (RESULTS §3) |
| SPIKE-05 | 01-06 | ✓ SATISFIED | Ollama token counts non-None both frameworks (RESULTS §7) |
| SPIKE-06 | 01-06 | ✓ SATISFIED | MCP args + structured results via callbacks, fixture-matched (RESULTS §7) |
| SPIKE-07 | 01-04, 01-06 | ✓ SATISFIED | Bake-off: no decisive winner; falsifier fired negative (RESULTS §7) |
| SPIKE-08 | 01-09 | ✓ SATISFIED | Round-trip per-stage budget (RESULTS §5) |
| SPIKE-09 | 01-01, 01-10 | ✓ SATISFIED | 01-RESULTS.md + DECISIONS.md, claim audit done |

All 9 phase requirement IDs are claimed by plans and satisfied. No orphaned requirements (REQUIREMENTS.md maps exactly SPIKE-01..09 to Phase 1; all present).

### Anti-Patterns Found

None material. No debt markers (TBD/FIXME/XXX) in the durable deliverables. The measurement-phase "artifacts" are evidence files, not code; no stub/placeholder patterns apply. Honest negatives are recorded as findings, not hidden (D-20 catastrophes c20/c03; embedded-segment babble; Russian rendered without stress labeling; the two 0.x LangChain packages).

### Behavioral Spot-Checks

Step 7b: SKIPPED — the only runnable code is the throwaway `spike/` harness (requires ~7 GB of model downloads, Ollama daemon, MPS) and is flagged for deletion. The deliverable is recorded measurement, which was verified by cross-checking each raw record against RESULTS.md and DECISIONS.md (all reconcile).

### Human Verification Required

None outstanding. The single irreplaceable human task — the blind native-ear Hebrew verdict — was executed 2026-07-25 and recorded verbatim (`raw/hebrew-verdict.md`). The SC#4 claim audit was completed (DECISIONS §Owed-item #1) and independently re-confirmed here (no repo prose exceeds the measured record).

### Gaps Summary

No gaps. All five ROADMAP Success Criteria are met with durable, cross-checked evidence. The phase goal — replacing five unverified claims with measurements — is achieved: the language promise (Hebrew usable / code-switching works-often-with-a-real-breakdown-mode / Whisper locks to one language), the agent-framework choice (LangChain stands, falsifier fired negative, recoverable for ~250 lines), and the hardware direction (TTS-dominated, 18 GB is the binding constraint, buy against Apple-Silicon inference not a measured CUDA number) are all evidence-backed and correctly caveated.

Two open items are correctly deferred, not gaps: the `dicta-onnx` no-license finding (L1, deferred to Phase 6 packaging) and real-voice code-switch evaluation (D-05, deferred to Phase 7). The Hebrew fallback rung is deliberately left unlocked (D-10, decided in Phase 6).

---

_Verified: 2026-07-25_
_Verifier: Claude (gsd-verifier)_
