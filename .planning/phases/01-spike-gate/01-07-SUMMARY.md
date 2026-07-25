---
phase: 01-spike-gate
plan: 07
subsystem: voice
tags: [faster-whisper, stt, code-switching, language-detection, spike-04, transliteration, synthetic-speech]

# Dependency graph
requires:
  - phase: "01-05"
    provides: "corpus/clips/ — 46 rendered WAVs (matrix+embedded+none), shuffle_blind.parse_clip_name naming, corpus.jsonl"
  - phase: "01-03"
    provides: "voice venv, faster-whisper 1.2.1 + Whisper large-v3 weights cached, Pitfall 7 vad_filter correction, two-venv conftest guard"
provides:
  - "spike/voice/transcribe.py — the SPIKE-04 harness: both multilingual conditions + all_language_probs + detect_language + a translate probe, engine imports inside functions"
  - ".planning/phases/01-spike-gate/corpus/transcripts.jsonl — 138 rows (46 clips x {ml=False, ml=True, translate}), each carrying the D-05 and Segment-no-language caveats"
  - ".planning/phases/01-spike-gate/raw/transcribe.md — the lock-on / transliterate / translate write-up with D-05 at the top"
  - "spike/voice/test_transcribe_harness.py — 6 slow voice-venv tests proving both conditions run and the posterior is non-empty, with a negative control"
  - "SPIKE-04 answer: Whisper LOCKS to one language per clip; multilingual=True does not unlock it; the embedded language is transliterated/garbled (Latin matrix) or preserved (locked to non-Latin); translate flattens to English"
affects: [01-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Engine-imports-inside-functions so the run plan (list_clips/build_plan) is checkable in the base venv before a CPU-minute of Whisper is spent — mirrors 01-05's render_corpus"
    - "Resumable append-only measurement: already_done() keys on (clip_id, condition) so a long CPU run can be re-entered, and each row is flushed as it completes"
    - "The binding caveat travels ON the data: every transcripts.jsonl row carries d05_caveat + segment_language_caveat, so no downstream quote can strip it"
    - "detect_language() called once per clip (task-agnostic) and attached to all three condition rows — self-contained rows without paying for three detection passes"

key-files:
  created:
    - spike/voice/transcribe.py
    - spike/voice/test_transcribe_harness.py
    - .planning/phases/01-spike-gate/corpus/transcripts.jsonl
    - .planning/phases/01-spike-gate/raw/transcribe.md
  modified:
    - spike/voice/conftest.py

key-decisions:
  - "large-v3 (first-party Systran), not large-v3-turbo (community conversion): a measurement phase must not attribute a conversion's flaws to Whisper"
  - "The multilingual flag is a FINDING, not a knob to leave on: run BOTH conditions on all 46 clips and record that the posterior was identical 46/46 — turning on per-segment detection changed nothing here"
  - "detect_language() takes a DECODED audio array in 1.2.1, not a path — decode via faster_whisper.audio.decode_audio (Rule 1 bug fix)"
  - "test_transcribe_harness.py added to conftest's VOICE_ONLY_MODULES so its faster-whisper import cannot abort the base-venv stdlib suite (preserves 01-01's two-venv property, same pattern 01-03 used)"
  - "SPIKE-04 IS marked complete: unlike SPIKE-01/02 (evidence-only in prior plans), this plan takes the verdict with the correct instrument — the D-05 caveat qualifies the answer but does not withhold it"

patterns-established:
  - "Measure-both-conditions-then-report-the-null: the instrument's best case (multilingual=True) is exercised even when it turns out to make no difference, because 'the flag did nothing' is itself the answer to 'does it lock on'"
  - "Caveat-as-column: a binding provenance caveat (D-05) is stored per-row, not just in prose, so the surviving data cannot be over-read"

requirements-completed: [SPIKE-04]

coverage:
  - id: D1
    description: "transcribe.py runs BOTH multilingual=False and multilingual=True per clip, sets vad_filter=False, and captures all_language_probs + a separate detect_language() posterior + a task=translate probe"
    requirement: "SPIKE-04"
    verification:
      - kind: unit
        ref: "spike/voice/test_transcribe_harness.py::test_harness_runs_both_multilingual_conditions, ::test_all_language_probs_is_a_real_distribution, ::test_detect_language_call_returns_a_posterior, ::test_translate_probe_targets_english"
        status: pass
      - kind: other
        ref: "uv run python -c ast.parse(transcribe.py) + assert multilingual/all_language_probs/detect_language present -> ok"
        status: pass
    human_judgment: false
  - id: D2
    description: "The Segment-has-no-.language limitation is recorded as a caveat on every row and in the write-up"
    requirement: "SPIKE-04"
    verification:
      - kind: unit
        ref: "spike/voice/test_transcribe_harness.py::test_build_row_carries_the_d05_and_segment_caveats"
        status: pass
    human_judgment: false
  - id: D3
    description: "transcripts.jsonl has 138 rows (>=30) covering both multilingual conditions plus the translate probe, with non-empty language posteriors + detect_language on every row"
    requirement: "SPIKE-04"
    verification:
      - kind: integration
        ref: "wc -l transcripts.jsonl == 138; per-condition counts {46,46,46}; all rows all_language_probs_topk + detect_language.topk non-empty"
        status: pass
    human_judgment: false
  - id: D4
    description: "raw/transcribe.md answers, per language pair, the lock-on / transliterate / translate behavior and states the D-05 synthetic-speech caveat at the top; corrects the 'STT is a non-issue' claim (SC#4)"
    requirement: "SPIKE-04"
    verification:
      - kind: integration
        ref: "grep -qiE 'D-05|synthetic' raw/transcribe.md; the file's headline findings + per-pair table"
        status: pass
    human_judgment: true
    rationale: "The narrative interpretation of the transcripts (whether the write-up faithfully characterizes lock-on/transliterate/translate) is a human reading the analyst text against the data, not a machine assertion."

# Metrics
duration: 39min
completed: 2026-07-25
status: complete
---

# Phase 1 Plan 07: SPIKE-04 Whisper Code-Switching Summary

**Whisper large-v3 LOCKS onto exactly one language per clip, and the `multilingual=True` "detect on every segment" instrument did not unlock it — the language posterior was byte-identical under both conditions on 46/46 clips. What moved detection was the Chatterbox `language_id` tag (9/20 sentences), not the Whisper flag: a textbook instance of D-05. The embedded language is transliterated or garbled into Latin unless Whisper locked to the non-Latin language (then both scripts survive), the same-script ru/en pair collapses entirely, and `task=translate` flattens everything to English. This corrects the old "STT is a non-issue" claim (SC#4) — with the binding caveat that this is SYNTHETIC speech and Chatterbox-vs-Whisper failures are inseparable here (D-05).**

## Performance

- **Duration:** 39 min
- **Started:** 2026-07-25T06:32:32Z
- **Completed:** 2026-07-25T07:11:00Z
- **Tasks:** 2
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments

- **The lock-on question is answered with the right instrument.** All 46 clips transcribed under `multilingual=False` (production default) AND `multilingual=True` (per-segment best case) plus a `task=translate` probe — 138 rows in `transcripts.jsonl`, each with `all_language_probs`, an independent `detect_language()` posterior, full transcript + segments, and the binding caveats.
- **The instrument's headline null result:** `multilingual=True` changed the posterior on **0/46** clips and the transcript on only 2/46 (both trivial). Whisper assigns one language to the whole clip regardless. That null is the finding, not a harness failure — the flag was genuinely exercised (proven by `test_transcribe_harness.py`).
- **A concrete, per-language-pair characterization** of transliterate vs preserve vs collapse vs translate, written up in `raw/transcribe.md` with D-05 stated at the top.
- **The old "STT is a non-issue" claim is corrected** for SC#4 — with the honest boundary that real-voice behavior is unmeasured (deferred to Phase 7).

## Task Commits

1. **Task 1: Transcribe harness + self-check (test-first)** — `f77644a` (feat; includes the Rule 1 detect_language fix and the conftest guard)
2. **Task 2: Transcribe the corpus + record with the D-05 caveat** — `bf70d6f` (feat)

**Plan metadata:** see the `docs(01-07)` commit following this SUMMARY.

## Files Created/Modified

- `spike/voice/transcribe.py` — SPIKE-04 harness. Engine imports inside functions (base-venv testable planning); `run()` is resumable and flushes per row; every row carries `d05_caveat` + `segment_language_caveat`.
- `spike/voice/test_transcribe_harness.py` — 6 slow, voice-venv-only tests; both conditions run, posterior non-empty, a negative control, and the caveats asserted on a built row.
- `spike/voice/conftest.py` — added `test_transcribe_harness.py` to `VOICE_ONLY_MODULES`.
- `.planning/phases/01-spike-gate/corpus/transcripts.jsonl` — 138 rows of surviving DATA (D-07).
- `.planning/phases/01-spike-gate/raw/transcribe.md` — the write-up.

## Findings (the SPIKE-04 answer)

| Question | Answer |
|---|---|
| Does Whisper lock onto one language? | **Yes** — one `info.language` per clip, both conditions. |
| Does `multilingual=True` unlock code-switching? | **No** — posterior identical 46/46; transcript identical 44/46. |
| What moves the detected language? | The Chatterbox `language_id` **tag** (9/20 sentences flipped), not the flag. |
| What happens to the *other* language? | **Transliterated/garbled** into Latin when the matrix is Latin (`סופגניות`→"Sifakonat", `sobremesa`→"Sober Misa"); **preserved in native script** only when Whisper locked to the non-Latin language (`c04__ru` keeps Cyrillic + English). |
| Hardest category? | Same-script ru/en **collapses** (`СОК`→"Sock", `c20`→"OnWebRailPyroid torqued"). |
| Does `task=translate` translate the rest? | **Yes** — flattens the whole utterance to English (`c09` he→"Remind me to take the ball at 8.45 tomorrow morning"). |

## Decisions Made

- **`large-v3` first-party, not turbo** — a measurement phase must not attribute a community conversion's flaws to Whisper (inherited from 01-03).
- **Report the null.** Both multilingual conditions run on every clip precisely so "the flag did nothing" is an evidenced claim, not an omission.
- **Caveat as a column, not just prose.** `d05_caveat` + `segment_language_caveat` ride on all 138 rows.
- **SPIKE-04 marked complete.** This plan takes the verdict with the correct instrument; the D-05 caveat qualifies but does not withhold the answer. (Contrast SPIKE-01/02, left unchecked in prior plans because those plans only produced evidence.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `detect_language()` takes a decoded audio array, not a path (faster-whisper 1.2.1)**
- **Found during:** Task 1 (self-check)
- **Issue:** `model.detect_language(str(clip_path))` raised `AttributeError: 'str' object has no attribute 'dtype'` — unlike `transcribe()`, `detect_language(audio=..., features=...)` expects a decoded numpy array. RESEARCH's code example (`model.detect_language("clip.wav")`) is wrong for this version; it was read from the `transcribe` path, not `detect_language`.
- **Fix:** Decode via `faster_whisper.audio.decode_audio(path)` (16 kHz mono, the model's rate) and pass `audio=`. The instrument the plan requires (`detect_language` posterior) is preserved; only the call shape changed.
- **Files modified:** `spike/voice/transcribe.py`
- **Verification:** `--self-check` green; `test_detect_language_call_returns_a_posterior` passes; all 138 rows carry a non-empty `detect_language.topk`.
- **Committed in:** `f77644a` (Task 1 commit)

**2. [Rule 3 - Blocking] The new slow test module would abort the base-venv suite**
- **Found during:** Task 1
- **Issue:** `test_transcribe_harness.py` loads faster-whisper. Under 01-01's canonical `pytest spike/ -q` (base venv, stdlib-only), a module-scope engine import raises `ModuleNotFoundError` during collection, which pytest treats as a hard error that aborts the whole run — the exact two-venv breakage 01-03 fixed for `test_lang_ids`/`test_readiness`, and the failure mode the prior-wave notes warned about.
- **Fix:** Added `test_transcribe_harness.py` to `conftest.py`'s `VOICE_ONLY_MODULES` (interpreter-keyed `collect_ignore`, never a blanket `importorskip` — a gate that can vanish is worse than no gate). Outside the voice venv the module is ignored with the reason reported; inside it, it is always collected.
- **Files modified:** `spike/voice/conftest.py`
- **Verification:** base venv `pytest spike/ -q -m "not slow"` → **119 passed**; voice venv non-slow → **100 passed, 22 deselected**; the collect-ignore notice names the new module.
- **Committed in:** `f77644a` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking). Both necessary for correctness/for preserving a prior-plan guarantee. No scope creep.
**Impact on plan:** Every acceptance criterion passes; the deviations repaired a wrong RESEARCH code example and a regression this plan's own new file would have caused to the base suite.

## Issues Encountered

- **The `multilingual` instrument gave no lift on this corpus.** Not a bug — the flag was exercised and the posteriors were simply identical. On genuinely long, segmented multi-language audio it may matter; these clips are short and single-locked. Reported as a finding.
- **Russian and same-script ru/en clips garble badly**, but per D-05 this is inseparable from Chatterbox — all 9 Russian clips were rendered without stress labeling (01-03 / Pitfall 2). The write-up refuses to blame Whisper for it.
- **CPU-only, ~13 s/clip across 3 conditions, ~30 min for the corpus.** Not a latency measurement — SPIKE-03 (01-09) owns that.

## Known Stubs

None. Every declared artifact exists, is verified, and is committed. No hardcoded/placeholder data: `transcripts.jsonl` is real Whisper output over the real corpus.

## Threat Flags

None. The plan's threat register (T-01-07-INT measurement validity, T-01-07-DL model fetch) was mitigated as designed: the correct instrument was used, `vad_filter=False` avoids clipping short clips, the D-05 caveat is recorded per-row so the result cannot be over-claimed, and no new network surface was introduced (weights were already cached, no HF_TOKEN).

## User Setup Required

None. No accounts, no credentials, no downloads — Whisper large-v3 weights were cached by 01-03.

## Next Phase Readiness

**Ready.** `transcripts.jsonl` + `raw/transcribe.md` are the surviving SPIKE-04 evidence, re-runnable via `spike/voice/transcribe.py` (resumable).

- **For 01-10 (SPIKE-09, "record measured reality"):** the SPIKE-04 finding to carry into `DECISIONS.md` is "Whisper locks to one language; multilingual=True does not change it; transliterate/collapse/translate as detailed" — and the **D-05 caveat must travel with it** (synthetic speech, Chatterbox and Whisper failures inseparable). 01-05's deviation 5 also flags that **SPIKE-01's check-off has no owner on current frontmatter** and proposes 01-10 own it.
- **Real-voice STT evaluation** (to lift the D-05 restriction) is deferred to Phase 7, whose SC#1 already compares observed behavior against these Phase 1 measurements.

## Self-Check: PASSED

Files verified present on disk:

- `spike/voice/transcribe.py` — FOUND
- `spike/voice/test_transcribe_harness.py` — FOUND
- `spike/voice/conftest.py` — FOUND (VOICE_ONLY_MODULES now lists 3 modules)
- `.planning/phases/01-spike-gate/corpus/transcripts.jsonl` — FOUND, **138** rows, per-condition {46,46,46}
- `.planning/phases/01-spike-gate/raw/transcribe.md` — FOUND, D-05 at top

Commits verified in `git log`: `f77644a`, `bf70d6f` — both FOUND.

Plan verification commands re-run at self-check time:

- Task 1: `ast.parse(transcribe.py)` + `multilingual`/`all_language_probs`/`detect_language` present → `ok`
- Task 1: `pytest spike/voice/test_transcribe_harness.py -q` → **6 passed** (78 s)
- Task 2: `transcripts.jsonl` exists, **138 ≥ 30** rows, `grep -qiE 'D-05|synthetic' raw/transcribe.md` → exit 0
- Regression, base venv: `pytest spike/ -q -m "not slow"` → **119 passed**
- Regression, voice venv: `pytest spike/voice/ -q -m "not slow"` → **100 passed, 22 deselected**

No unintended deletions: both task commits are insertions only over new files (transcripts.jsonl was regenerated clean, not previously committed).

---
*Phase: 01-spike-gate*
*Completed: 2026-07-25*
