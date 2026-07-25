---
phase: 01-spike-gate
plan: 10
subsystem: synthesis
tags: [spike-09, results, decisions, claim-audit, d-09, caveats, phase-exit-gate]

# Dependency graph
requires:
  - phase: "01-05"
    provides: "corpus render inventory + timings.jsonl (SPIKE-01 raw)"
  - phase: "01-07"
    provides: "transcripts.jsonl + raw/transcribe.md (SPIKE-04 raw, D-05)"
  - phase: "01-09"
    provides: "raw/ttfa.md + raw/roundtrip.md (SPIKE-03/08 raw, D-12)"
  - phase: "01-06"
    provides: "raw/bakeoff-results.md (SPIKE-05/06/07 raw); left SPIKE-05/06 record to 01-10"
  - phase: "01-03"
    provides: "raw/voice-provision.md (provisioning baseline, seed, MPS, permanent facts)"
  - phase: "01-08"
    provides: "NOT EXECUTED — no raw/hebrew-verdict.md; Hebrew verdict genuinely pending"
provides:
  - ".planning/phases/01-spike-gate/01-RESULTS.md — the raw measured record for SPIKE-01..08, committed before DECISIONS.md (D-09)"
  - "DECISIONS.md (repo root) — plain-language measured reality (SPIKE-09) with D-05/D-12 caveats, no fallback rung selected (D-10), spike/ flagged for deletion (SC#5)"
affects: [Phase-3, Phase-6, Phase-7]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw-before-interpretation (D-09): 01-RESULTS.md committed at 6beaef0 before DECISIONS.md at d45c8d4 — git order is the proof"
    - "PENDING is a valid recorded state: the Hebrew verdict is recorded as awaiting-human, never inferred from proxy data"
    - "Every public claim drafted to trace to a specific measurement so the human SC#4 audit is a check, not a rewrite"

key-files:
  created:
    - .planning/phases/01-spike-gate/01-RESULTS.md
    - DECISIONS.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
  deleted: []

key-decisions:
  - "SPIKE-05/06/07 marked complete: answered by the bake-off (raw/bakeoff-results.md) and now recorded in DECISIONS.md, the home 01-06 explicitly deferred them to (D-09)"
  - "SPIKE-09 marked complete: this plan is the raw record + interpretation it names"
  - "SPIKE-01 and SPIKE-02 left PENDING: both depend on the unexecuted 01-08 native-ear verdict; checking them would put an unmeasured claim into the matrix (exactly what SC#4 exists to catch)"
  - "No Hebrew fallback rung selected (D-10) — the required input (native-ear verdict) does not exist"
  - "Task 3 (SC#4 human claim audit) deferred, not blocked, per explicit user direction to focus on code"

requirements-completed: [SPIKE-05, SPIKE-06, SPIKE-07, SPIKE-09]

# Metrics
duration: 15min
completed: 2026-07-25
status: complete
---

# Phase 1 Plan 10: Synthesis — RESULTS + DECISIONS Summary

**Phase 1's durable exit gate now exists. The raw record (`01-RESULTS.md`) was committed at
`6beaef0` BEFORE the interpretation (`DECISIONS.md`) at `d45c8d4` — the D-09 ordering is proven in
git history, not just asserted. DECISIONS.md states the measured multilingual reality in plain
language (Whisper locks to one language and transliterates/collapses/translates the rest; latency
is TTS-dominated at ~49 s on Apple Silicon; LangChain stands but its basis moved), carries the D-05
synthetic-speech and D-12 Apple-Silicon caveats on their results, selects NO Hebrew fallback rung
(D-10), and flags `spike/` for deletion (SC#5). The one irreplaceable human input — the native-ear
Hebrew verdict (01-08) — is recorded as PENDING, never fabricated. Task 3's SC#4 claim audit is
deferred to the human per explicit direction; the automatable half (every claim drafted to trace to
a measurement, both caveats attached) is done.**

## What was produced

| Artifact | Role | Commit |
|---|---|---|
| `.planning/phases/01-spike-gate/01-RESULTS.md` | RAW record — SPIKE-01..08 + provisioning baseline, no conclusions | `6beaef0` |
| `DECISIONS.md` (repo root) | Interpretation — measured reality + caveats, links back to RESULTS | `d45c8d4` |

## D-09 ordering — proven, not claimed

`git log` order: `6beaef0` (RESULTS) precedes `d45c8d4` (DECISIONS). Before committing RESULTS the
executor asserted `DECISIONS.md` did not yet exist. The raw record is therefore re-readable without
the framing that interprets it — which is what gives D-08 (no pre-registered thresholds) its teeth.

## The measured reality recorded (SPIKE-09)

- **Whisper on synthetic mixed speech LOCKS to one language;** `multilingual=True` changed nothing (posterior identical 46/46). The other language is transliterated/garbled (Latin matrix) or preserved (locked to non-Latin); same-script ru/en collapses; `translate` flattens to English. **The old "STT is a non-issue" note is overturned.** D-05 binds: says nothing about the user's real speech.
- **Latency (Apple Silicon, D-12):** warm TTFA 6.27 s mps / 21.70 s cpu; round trip ~49 s warm, TTS-dominated (~65%), LLM trivial (~1.4%). Sentence-dependent ~10× tail; 18 GB is the binding constraint. Sizes a purchase; not a shipped-latency or CUDA claim.
- **Agent framework:** SPIKE-05 (token counts non-None) YES; SPIKE-06 (MCP args + structured results via callbacks) YES with zero cloud — CLAUDE.md's falsifier fired negative; SPIKE-07 no decisive winner. **LangChain recommendation stands, basis moved** from observability to coupling/ergonomics/transport; recoverable for ~250 lines if wrong.

## Requirement check-offs

| Requirement | Action | Why |
|---|---|---|
| SPIKE-05 | **Complete** | Answered by bake-off; 01-06 deferred the record to DECISIONS.md (now written) |
| SPIKE-06 | **Complete** | Same |
| SPIKE-07 | **Complete** | Verdict recorded in DECISIONS.md |
| SPIKE-09 | **Complete** | This plan is the raw record + interpretation it names |
| SPIKE-01 | **Left PENDING** | Intelligibility of code-switched audio is a listening judgment; depends on unexecuted 01-08 |
| SPIKE-02 | **Left PENDING** | Native-ear Hebrew verdict — 01-08 not executed; no proxy allowed (D-13) |

## Deviations from Plan

**None in the automatable scope.** Both artifacts were assembled exactly as Tasks 1–2 specify, in
the D-09 order. Task 3 is a human checkpoint handled per the policy below (deferred, not a
deviation). No genuine contradiction between raw records was found during assembly — the evidence
is mutually consistent (the `c08__he` render outlier in §1, the runaway caveat in §4, and the
co-resident drift in §5 corroborate the same sentence-dependent-tail property rather than
conflicting).

## Deferred — Human Action Required

Per explicit user direction ("ignore anything a human needs to do; focus on code — I will pick the
human items myself later"), the following are recorded and **not blocked**:

1. **SC#4 claim audit — Task 3 (`checkpoint:human-verify`), STILL OWED.** A human must read every
   public claim in the repo (DECISIONS.md, any README, PROJECT.md's multilingual claims, doc drafts)
   against `01-RESULTS.md` and edit down anything that exceeds the evidence, then type "audited".
   **Automatable half done for you:** every claim in DECISIONS.md is drafted to trace to a specific
   measurement in `01-RESULTS.md`, and the D-05/D-12 caveats are attached wherever their results are
   cited. **One claim you must source yourself when auditing:** any statement about Chatterbox
   Hebrew *quality* — there is currently NO evidence for it (see item 2), so any such claim must be
   deleted, not merely trimmed.
   - Files to audit: `DECISIONS.md`, `.planning/phases/01-spike-gate/01-RESULTS.md`, `spike/README.md` (before deletion), `.planning/PROJECT.md`, `.claude/CLAUDE.md`.

2. **Native-ear Hebrew verdict — SPIKE-01 / SPIKE-02 (plan 01-08), NOT EXECUTED.** The one
   irreplaceable human resource in this phase. There is **no `raw/hebrew-verdict.md`**. Everything
   the pass needs is on disk: listen to `corpus/clips_blind/blind_000.wav … blind_045.wav` (46 clips,
   ~194 s, no tags visible), record verbatim impressions (no rating scale, D-13), join tags back
   only afterward via `spike/voice/shuffle_blind.py join`. **No fallback rung (D-10) may be selected
   until this exists.** D-20 additionally asks for ru/es spot-checks; carry the caveat that all 9
   Russian clips were rendered without stress labeling (permanent).

3. **`dicta-onnx==1.0.9` supply-chain approval (01-03 Task 0), STILL OWED.** The programmatic audit
   came back clean (repo real, PyPI/GitHub identity match, import hard-coded by chatterbox upstream
   at `tokenizer.py:123`), but the explicit human yes/no was never given. Carried as an open item in
   DECISIONS.md.

4. **`dicta-onnx` no-license finding (L1), STILL OWED.** The package declares no license on PyPI or
   GitHub ("all rights reserved" by default). It sits on the Hebrew critical path and must be
   resolved before any Apache-2.0 shipping artifact depends on it (Phase 6 / packaging).

## SC#5 — spike/ flagged for deletion

`spike/` (repo root) is flagged for deletion per SC#5 / D-18. Its only durable content — the
provisioning records, raw write-ups, corpus, and bake-off findings — has been lifted into
`.planning/phases/01-spike-gate/` and `DECISIONS.md`. Deleting `spike/` (including `.venv`s,
`__pycache__`, `.pytest_cache`, harness `.py`, and `spike/README.md`) removes no evidence. This
plan flags it; it does not delete it here (the SC#4 audit reads `spike/README.md` first).

## Known Stubs

None. Both artifacts contain real synthesized-from-evidence content. The two PENDING states
(Hebrew verdict, and the SPIKE-01/02 check-offs that depend on it) are deliberate honest blanks,
recorded as such — not stubs to be silently filled.

## Threat Flags

None. No new security surface. The plan's threat register (T-01-10-CLAIM over-claiming,
T-01-10-SCOPE unmade-decision-leaking-forward) was mitigated as designed: RESULTS committed before
DECISIONS (D-09), every claim drafted to trace to a measurement, D-05/D-12 caveats mandatory, and
no fallback rung selected (D-10 — verified by a negative grep for any rung-selection verb).

## Self-Check: PASSED

Files verified present on disk:
- `.planning/phases/01-spike-gate/01-RESULTS.md` — FOUND
- `DECISIONS.md` — FOUND

Commits verified in `git log`: `6beaef0` (RESULTS), `d45c8d4` (DECISIONS) — both FOUND, in D-09 order.

Verification commands re-run:
- Task 1: `test -f 01-RESULTS.md && grep -qiE 'seed|resolved|version' && grep -qiE 'verbatim|Hebrew'` → PASS
- Task 1 D-09 ordering: DECISIONS.md confirmed absent at RESULTS commit time → PASS
- Task 2: `test -f DECISIONS.md && grep 'synthetic|D-05' && grep 'Apple Silicon|inference|D-12' && grep 'fallback|rung|Phase 6'` → PASS
- Task 2 D-10: negative grep for a rung-selection verb → OK, no rung selected

---
*Phase: 01-spike-gate*
*Completed: 2026-07-25*
