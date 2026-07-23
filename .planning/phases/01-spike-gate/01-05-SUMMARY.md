---
phase: 01-spike-gate
plan: 05
subsystem: voice
tags: [chatterbox, corpus-render, code-switching, reproducibility, leak-isolation, blind-judgment, mps]

# Dependency graph
requires:
  - "01-02: corpus.jsonl (20-record failure grid), shuffle_blind.py (clip_filename + seeded blind shuffle)"
  - "01-03: voice venv, GATE 0 GREEN, repair_dicta(), the measured device answer (mps) and the bitwise-reproducibility answer"
provides:
  - ".planning/phases/01-spike-gate/corpus/clips/ — 46 rendered WAVs (40 matrix+embedded per D-06, 6 untagged language_id=None controls), seed 1234, device mps, configuration repaired"
  - ".planning/phases/01-spike-gate/corpus/timings.jsonl — one row per clip: device, seed, every generation parameter, synth seconds, duration, per-clip degradation record"
  - ".planning/phases/01-spike-gate/corpus/clips_blind/ + mapping.json — seeded (20260723) reversible blind view, verified bijective and byte-identical"
  - "spike/voice/render_corpus.py — leak-isolated, seeded, repair-asserting render harness"
  - "spike/voice/test_render_plan.py — 28 torch-free tests over the render plan and its failure classification"
  - "shuffle_blind.UNTAGGED_TAG / JUDGABLE_TAGS — the shared naming convention now expresses language_id=None"
  - ".planning/phases/01-spike-gate/raw/render-aborted-run.jsonl — the first, mixed-device attempt kept verbatim"
affects: [01-06, 01-08, 01-09, 01-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Leak-isolated batch rendering: N=6 clips per fresh subprocess, model reloaded each batch (Pattern 2 / Pitfall 5)"
    - "Re-assert, never re-assume: a process-local repair is proven live inside every subprocess before that subprocess writes data"
    - "Expected-vs-blocking failure classification, failing closed: an unclassified warning is fatal, a measured-and-accepted one is recorded"
    - "Distinct exit code for a data-integrity abort so it can never be retried as if it were a device failure"
    - "Testable plan, untestable render: every engine import lives inside a function so the job plan is checkable in the base venv before a GPU-minute is spent"

key-files:
  created:
    - spike/voice/render_corpus.py
    - spike/voice/test_render_plan.py
    - .planning/phases/01-spike-gate/corpus/clips/ (46 WAVs)
    - .planning/phases/01-spike-gate/corpus/clips_blind/ (46 WAVs)
    - .planning/phases/01-spike-gate/corpus/mapping.json
    - .planning/phases/01-spike-gate/corpus/timings.jsonl
    - .planning/phases/01-spike-gate/raw/render-aborted-run.jsonl
  modified:
    - spike/voice/shuffle_blind.py
    - spike/voice/test_blind_mapping.py
  deleted: []

key-decisions:
  - "The untagged control is 6 clips, one per D-02 category, DERIVED from the corpus rather than hard-coded — a hard-coded list stops covering all six categories the moment the corpus is edited"
  - "shuffle_blind gained UNTAGGED_TAG rather than the renderer formatting 'c08__none.wav' itself: the plan requires both the None control and the use of clip_filename(), and the two were incompatible"
  - "The known-unfixable russian_text_stresser warning is RECORDED per clip, not fatal; every other degradation warning — classified or not — is fatal"
  - "A data-integrity abort exits with a distinct code and is never retried on another device: a different backend cannot repair a degradation path"
  - "The first (mixed-device) attempt was archived verbatim rather than deleted, and its 6 clips were re-rendered from scratch on one device"
  - "clips_blind/ is committed despite being byte-identical to clips/: git stores 46 unique blobs for 92 paths, so the blind view costs tree entries, not megabytes"
  - "SPIKE-01 deliberately left unchecked — see Deliberate Non-Action, which also flags that no remaining plan carries it"

patterns-established:
  - "Render-then-verify-mechanically-then-stop: file count, non-silence, duration, sample rate and bijection are checked by machine; audio quality is not characterised by the executor at all"
  - "Every subprocess re-proves the invariant it inherited, because process-local state does not survive Pattern 2"

requirements-completed: []

coverage:
  - id: D1
    description: "Each of the 20 corpus sentences is rendered twice — once under its matrix_lang tag, once under its embedded_lang tag (D-06) — plus a language_id=None control for a subset spanning all six D-02 categories"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "test_render_plan.py::test_every_sentence_is_rendered_under_its_matrix_and_its_embedded_tag, ::test_the_tagged_render_is_exactly_two_clips_per_sentence, ::test_the_untagged_control_spans_every_failure_grid_category"
        status: pass
      - kind: integration
        ref: "46 WAVs on disk; conditions = {matrix: 20, embedded: 20, none: 6}; timings.jsonl row set == disk file set"
        status: pass
    human_judgment: false
  - id: D2
    description: "torch.manual_seed(1234) is set immediately before EACH generate() call, and the seed plus every generation parameter is recorded per clip (D-07 / Pitfall 6)"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "test_render_plan.py::test_the_seed_is_fixed_and_recorded, ::test_every_generation_parameter_is_stated_explicitly"
        status: pass
      - kind: integration
        ref: "all 46 timings.jsonl rows carry seed=1234 and the full gen_params object"
        status: pass
    human_judgment: false
  - id: D3
    description: "The render runs in leak-isolated subprocess batches of N in [5,8] with a fresh model per batch (Pattern 2 / Pitfall 5)"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "test_render_plan.py::test_the_batch_size_is_inside_the_pattern_2_band, ::test_batching_covers_every_job_exactly_once"
        status: pass
      - kind: integration
        ref: "8 subprocesses, distinct model_load_seconds per batch; no monotonic synth-time trend by position-in-batch (medians 8.8-10.9 s across positions 0-5)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The 01-03 Dicta repair is proven ACTIVE inside every render subprocess before that subprocess writes a clip — never assumed"
    requirement: "SPIKE-02"
    verification:
      - kind: integration
        ref: "render_corpus._assert_repair_active; all 46 rows carry configuration=repaired, native_zero_arg_dicta_works=false, dicta_probe_out='שְׁלוֹם עוֹלָם'"
        status: pass
    human_judgment: false
  - id: D5
    description: "clips_blind/ + mapping.json give a reversible blind view over the whole render, controls included, with no blind name leaking a clip id or a tag (D-14)"
    requirement: "SPIKE-02"
    verification:
      - kind: unit
        ref: "test_blind_mapping.py::test_untagged_clips_shuffle_and_join_back_alongside_tagged_ones; test_render_plan.py::test_the_whole_plan_is_shufflable_by_the_blind_harness"
        status: pass
      - kind: integration
        ref: "46 blind files; join_back restores all 46 source names; SHA-256 of every blind copy matches its mapped source; zero names contain a clip id or tag"
        status: pass
    human_judgment: false
  - id: D6
    description: "A device failure would be recorded verbatim as data and fall mps -> cpu (D-11/D-12), while a data-integrity abort is never retried on another device"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "test_render_plan.py::test_a_device_failure_is_recorded_as_data_with_the_verbatim_exception, ::test_an_integrity_abort_is_a_different_outcome_from_a_device_crash"
        status: pass
      - kind: integration
        ref: "raw/render-aborted-run.jsonl — the fallback path exercised for real (incorrectly, see deviation 1) and its verbatim record kept; final render: 46/46 on mps, zero failure rows"
        status: pass
    human_judgment: false

# Metrics
duration: 26min
completed: 2026-07-23
status: complete
---

# Phase 1 Plan 05: Corpus Render Summary

**46 clips rendered — 40 matrix+embedded (D-06) plus 6 untagged `language_id=None` controls — all on `mps`, all at seed 1234, all in `CONFIG_REPAIRED`, in 8 leak-isolated subprocesses. Zero device failures, zero blocking degradations, zero silent or truncated clips. The blind view is bijective and byte-verified. The phase's durable audio evidence now exists, and the Hebrew verdict remains untaken and unprimed.**

> ⚠️ **If you are about to take the 01-08 native-ear judgment, stop reading here.** The "Mechanical Observations" section below contains per-clip render statistics. They say nothing about audio quality, but D-14 exists because expectation contaminates a first impression, and the safest reading of that decision is that the judge sees the clips and nothing else.

## What Was Produced

| Artifact | Contents |
|---|---|
| `corpus/clips/` | 46 WAVs, 24 kHz mono, 194.2 s of audio, 9.32 MB |
| `corpus/clips_blind/` | 46 opaque `blind_NNN.wav` copies, seed `20260723` |
| `corpus/mapping.json` | blind name → `clip_id` + `language_id` + `source_name`, count-checked |
| `corpus/timings.jsonl` | 46 rows, one per clip, all `ok: true` |
| `raw/render-aborted-run.jsonl` | the first attempt's 7 rows, kept verbatim (see deviation 1) |

### The render conditions

| Condition | Clips | What it isolates |
|---|---:|---|
| `matrix` — tagged with the sentence's dominant language | 20 | D-06 |
| `embedded` — tagged with the sentence's embedded language | 20 | D-06 |
| `none` — `language_id=None`, no tag at all | 6 | RESEARCH Open Q5 |

The 6 controls are `c01, c04, c08, c12, c15, c18` — the first record of each of the six D-02 categories, **derived from the corpus at runtime**, not hard-coded. A hard-coded list silently stops spanning the failure grid the moment the corpus is edited, and spanning the grid is the control's entire value: without a same-category control, "the tagged renders sound alike" cannot be told apart from "the tag did the wrong thing" *in that category*.

Tag distribution across the 46: `en` 18, `ru` 9, `he` 7, `es` 6, `none` 6.

### Recorded knobs (D-07)

| Knob | Value |
|---|---|
| seed | `1234`, set immediately before **each** `generate()` (Pitfall 6) |
| device | `"mps"` — the string, per Pitfall 4 |
| configuration | `repaired` (01-03) |
| batch size | 6 clips per fresh subprocess (Pattern 2, N≈5–8) |
| generation params | `exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=2.0, min_p=0.05, top_p=1.0` — all stated explicitly, none inherited |
| watermarking | unconditional, **inside** the timed region (Pitfall 11 / VOICE-12) |
| blind shuffle seed | `20260723` |

## The Repair Was Re-Proven 8 Times, Not Assumed Once

01-03's binding instruction was that every render process must re-apply `repair_dicta()`, because Pattern 2's fresh subprocesses reset chatterbox's module-level `_dicta` global and an unrepaired subprocess emits consonant-skeleton Hebrew that is **indistinguishable from good output by inspection**.

Re-applying it is not enough — a repair that silently no-ops looks exactly like a repair that worked. So each worker mutates a known Hebrew string and refuses to render if it comes back unchanged. Evidence, from all 46 rows:

- `configuration` = `repaired` — 46/46
- `native_zero_arg_dicta_works` = `false` — 46/46 (the upstream defect is still there; the repair is what made Hebrew work)
- `dicta_probe_out` = `שְׁלוֹם עוֹלָם` — 46/46, niqqud present

## Mechanical Verification

Every claim below is machine-checked, not listened to.

| Check | Result |
|---|---|
| clip count | **46** (plan floor ≥30, target ~40 + controls) |
| `timings.jsonl` rows == files on disk | **True**, 46 == 46 |
| silent clips (peak < 0.01) | **0** — peak amplitude ranges 0.591–1.000 |
| near-silent RMS | **0** |
| truncated clips (< 0.5 s) | **0** — durations 2.52 s – 10.44 s |
| sample rate | **24000 Hz**, uniform (`tts.sr` / `S3GEN_SR`) |
| device uniformity | **`mps` on 46/46** |
| blind view bijective | **True** — `join_back` restores all 46 source names |
| blind copies byte-identical to sources | **True** — SHA-256 matched for all 46 |
| blind names leaking a clip id or tag | **0** |
| blocking degradation warnings | **0** |

## Mechanical Observations for Downstream Plans

*(Render statistics only. Nothing here is a quality claim, and none of it should reach 01-08's judge before judging.)*

**Leak isolation appears to have worked.** Pitfall 5's failure mode is later clips being slower because of memory pressure. Median synth time by position within a batch: pos 0 `10.5 s`, pos 1 `8.8 s`, pos 2 `9.0 s`, pos 3 `8.9 s`, pos 4 `10.1 s`, pos 5 `10.9 s`. No monotonic trend. Either the batching prevented the accumulation or it never manifested at this scale — the two are not distinguishable from this data, which is precisely why the insurance was cheap.

**Model load is now ~11 s per batch**, not 01-03's 60.9 s cold figure: the weights are OS-cached after Gate 0. Eight batches, ~88 s of the ~13 min total spent reloading. That is the price of leak isolation and it is worth naming for 01-09.

**These are NOT SPIKE-03 numbers.** Per Pitfall 5, TTFA must be measured in a dedicated single-purpose process. Median real-time factor here is ~2.0–3.3× across tags, but it is contaminated by batch position and reload effects. 01-09 owns the latency metric; do not quote `timings.jsonl` as latency.

**`c08__he.wav` is a duration outlier**: 10.44 s of audio and 63.2 s of synthesis, against a corpus-wide median of ~4 s / ~9 s. Recorded as a mechanical fact — a possible runaway generation — so that whoever reads the eventual verdict can attribute an anomaly correctly rather than rediscover it.

**41 of 46 clips emitted `forcing EOS token` from `alignment_stream_analyzer`, and 7 emitted `Detected 2x repetition of token N`.** 01-03 saw both on its 4-word Hebrew probe and explicitly asked this plan to check whether they generalise. They do: they are the *common* case across all four languages, not a Hebrew-specific signal. That is useful — it means their presence on any single clip carries little information.

**Russian is rendered without stress labeling on all 9 Russian-tagged clips**, each emitting `russian_text_stresser not available` exactly as 01-03 predicted. The warning is now recorded per clip in `timings.jsonl`, so D-20's Russian spot-check carries its caveat as data rather than as a footnote.

## Task Commits

| Task | Commit | Type |
|---|---|---|
| Task 1 — render harness, plan tests, `UNTAGGED_TAG` | `d5b8e20` | feat |
| Deviation 1 fix — degradation classification + integrity exit code | `f00a7ad` | fix |
| Task 2 — the 46 clips, timings, blind view, mapping | `9e883c4` | feat |

**Plan metadata:** see the `docs(01-05)` commit following this SUMMARY.

## Test Results

| Suite | Venv | Tests | Result |
|---|---|---:|---|
| Full quarantine `spike/` | base | **91** | pass (0.38 s) |
| `spike/voice/` excluding the slow gate | voice | **100** | pass (4.26 s) |
| `spike/voice/` collection | voice | 116 collected | GATE 0 modules present |

New this plan: 28 tests in `test_render_plan.py` (all torch-free, so the render plan is checkable in the base venv before a GPU-minute is spent) and 6 in `test_blind_mapping.py` for the untagged tag.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The harness aborted the render on a degradation the phase had already measured and accepted — and then compounded it by treating the abort as a device failure**

- **Found during:** Task 2, first real batch
- **Issue:** Two bugs, the second much worse than the first.
  - Chatterbox emits `russian_text_stresser not available - Russian stress labeling skipped` on every Russian-bearing clip. It matches `gate_readiness.DEGRADATION_MARKERS` because those markers are deliberately generic *shapes* ("not available", "skipped"). GATE 0 never met it — its probe clip was Hebrew-only. My harness treated any degradation record as fatal, so it aborted on `c01__ru.wav`: a condition that is unfixable (permanent PyPI 404, 01-03 Check 3), already measured, and already carries a recorded D-05/D-20 consequence.
  - The driver then read that abort as a **device** failure and fell `mps → cpu`, rendering the batch's remaining 4 clips on CPU. The result was a mixed-device series that looked complete. A different backend cannot repair a degradation path, so the retry was never going to help — it only destroyed device uniformity, which is the one property the timing series depends on.
- **Fix:** `classify_degradation()` splits warnings into expected and blocking, **failing closed** — an unclassified warning is fatal, so the list cannot go stale into false safety. Only `russian_text_stresser` is on the expected list; the Hebrew diacritization path stays fatal, because that one *is* repairable and unrepaired Hebrew clips look fine. Separately, the worker now exits with a distinct `EXIT_INTEGRITY = 2` and the driver refuses to fall back to another device on it. Device fallback still applies to genuine crashes.
- **Files modified:** `spike/voice/render_corpus.py`, `spike/voice/test_render_plan.py` (+9 tests)
- **Recovery:** the 6 contaminated clips were deleted and re-rendered from scratch on a single device; the aborted run's `timings.jsonl` was archived verbatim to `raw/render-aborted-run.jsonl` rather than discarded, since it is the record of the incident.
- **Commit:** `f00a7ad`

**2. [Rule 3 - Blocking] The shared naming convention could not express the control condition the plan requires**

- **Found during:** Task 1
- **Issue:** The plan requires a `language_id=None` control **and** requires naming clips via 01-02's `shuffle_blind.clip_filename()` — the exported single definition that stops producer and consumer drifting. But `clip_filename` validated against `LANGUAGES = {en, ru, he, es}` and rejected `None`. The two requirements were incompatible, and the tempting workaround — formatting `f"{cid}__none.wav"` in the renderer — is precisely the drift the exported function exists to prevent.
- **Fix:** Added `UNTAGGED_TAG = "none"` and `JUDGABLE_TAGS = LANGUAGES | {UNTAGGED_TAG}` to `shuffle_blind`. `clip_filename` accepts `None` (or the string `"none"`); `parse_clip_name` and `shuffle_blind` default to `JUDGABLE_TAGS`. `LANGUAGES` is untouched and still means *languages*, so any downstream code counting languages is unaffected. The guard's purpose survives: `none` is admitted, `nonw`/`null`/`iw` are still rejected — asserted by `test_widening_the_tag_set_did_not_widen_it_to_typos`.
- **Files modified:** `spike/voice/shuffle_blind.py`, `spike/voice/test_blind_mapping.py` (+6 tests)
- **Commit:** `d5b8e20`

**3. [Rule 2 - Missing Critical] The render plan had no mechanical check, and it is the most expensive thing to get wrong**

- **Found during:** Task 1
- **Issue:** The plan specifies the harness, not a test for it. But a *wrong plan* is the worst failure available here: rendering 20 clips instead of 40, or a control subset that misses a D-02 category, produces a **complete-looking** corpus whose gaps only surface after the irreplaceable unprimed listening pass has been spent on it.
- **Fix:** `test_render_plan.py` — 28 tests over job planning, naming, batching, resumability and failure classification. All engine imports in `render_corpus` live inside functions specifically so this suite runs in the base venv with no torch and no GPU time.
- **Commit:** `d5b8e20`, extended in `f00a7ad`

### Budget overrun (recorded, not fixed)

**4. The clip payload is 9.32 MB, against D-07's ~3–5 MB estimate**

46 clips (not the 40 D-07 assumed) at 194.2 s of 24 kHz 16-bit mono. Roughly 2× the estimate; git-lfs is still unnecessary and the decision needs no revisiting. Worth noting for Phase 7, which re-runs and diffs against this.

`clips_blind/` adds 46 more paths but **not** 9 MB: the blind copies are byte-identical to their sources, so git stores **46 unique blobs for 92 tracked paths**. Verified — `.git` is 12 MB total. Committing the blind view therefore costs tree entries, which is why it was committed rather than left regenerable.

### Deliberate non-action

**5. `SPIKE-01` was NOT marked complete — and no remaining plan carries it**

SPIKE-01 reads *"**Measure** whether Chatterbox Multilingual V3 handles intra-sentence code-switching…"*. This plan renders the clips under varying `language_id` across 20 mixed-script sentences; it takes no verdict. The verdict comes from 01-08's blind impressions and 01-06's Whisper transcription. Checking the box now would put an unmeasured claim into the traceability matrix, which is exactly what SC#4's claim audit exists to catch — the same reasoning 01-02 and 01-03 applied.

⚠️ **But this is the last plan whose frontmatter carries `SPIKE-01`.** 01-06 is tagged SPIKE-04, 01-08 SPIKE-02, 01-10 SPIKE-09. On current frontmatter, SPIKE-01 will never be checked off by any plan. **01-10 (SPIKE-09, "record measured reality") should own the check-off**, since it is the plan that actually states the code-switching finding. Flagged here so it is a decision rather than an oversight.

---

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing-critical), 1 recorded budget overrun, 1 deliberate non-action with a flagged gap.
**Impact on plan:** No scope creep — the two modified prior-plan files were modified to satisfy this plan's own stated requirements, and every acceptance criterion passes.

## Issues Encountered

- **A generic degradation detector met a degradation it was never shown.** 01-03 deliberately made `DEGRADATION_MARKERS` generic shapes so the gate could not go stale against upstream rewording. That is the right call and it stays. But generic markers plus "any match is fatal" is only safe if every match has been classified — hence failing closed with an explicit expected-list, rather than loosening the markers.
- **Silent device fallback is a dangerous default.** The fallback existed for a good reason (D-11/D-12: an unusable MPS is a *result*). Applied to the wrong class of failure it produced a mixed-device series that no downstream check would have caught, because file count, durations and bijection all looked perfect. The fix was not to remove the fallback but to make the two failure classes structurally distinguishable.
- **`c08__he` took 63 s to render 10.4 s of audio.** Recorded, not investigated: investigating it means listening, and that is not this plan's to spend.

## Known Stubs

None. Every declared artifact exists, is verified, and is committed.

## Deferred — Human Action Required

**1. The SPIKE-02 native-ear Hebrew verdict (D-13, blind per D-14) is now fully unblocked and untaken.**

This plan deliberately stopped at mechanical verification. No clip was listened to, no Hebrew quality was inferred from waveform statistics, and nothing above pre-frames the judgment — the one irreplaceable, unprimed resource in this phase.

Everything the pass needs is on disk:

- **Listen to:** `.planning/phases/01-spike-gate/corpus/clips_blind/blind_000.wav` … `blind_045.wav` (46 clips, ~194 s total). The directory contains no tags, no clip ids and no mapping.
- **Generate the blank judgment file** (keys already aligned to the mapping, contains no tags — safe to keep open while judging):
  `./spike/voice/.venv/bin/python spike/voice/shuffle_blind.py shuffle … --template` , or directly `shuffle_blind.judgment_template(".planning/phases/01-spike-gate/corpus/mapping.json", "judgments.json")`
- **Record verbatim impressions** per D-13 — no rating scale.
- **Join the tags back only afterwards:**
  `./spike/voice/.venv/bin/python spike/voice/shuffle_blind.py join .planning/phases/01-spike-gate/corpus/mapping.json --judgments judgments.json`
- D-20 additionally asks for Russian and Spanish spot-checks alongside the deep Hebrew judgment. Carry the caveat that **all 9 Russian clips were rendered without stress labeling** (unfixable, 01-03).

01-08 owns this. It is listed here because it is human-gated and this plan is what unblocked it.

**2. Still owed from 01-03: the `dicta-onnx==1.0.9` supply-chain approval, and the L1 unlicensed-dependency ruling before Phase 6.** Unchanged by this plan, but now with more at stake: 46 clips of committed evidence depend on that package being the right one.

## User Setup Required

None. No accounts, no credentials, no downloads — all model weights were already cached by 01-03.

## Next Phase Readiness

**Ready. The phase's durable audio evidence exists and is re-runnable.**

For **01-06 (SPIKE-04, Whisper):** transcribe `corpus/clips/*.wav`. Filenames carry the tag; use `shuffle_blind.parse_clip_name()` with the default `JUDGABLE_TAGS` so the 6 `__none` control clips parse rather than raise. Join transcripts back to source text via `corpus.jsonl` on `clip_id`. D-05's binding caveat travels: this is *synthetic* mixed speech, and Chatterbox failures are not separable from Whisper failures.

For **01-08 (SPIKE-02):** see Deferred above. Do not read this SUMMARY's "Mechanical Observations" before judging.

For **01-09 (SPIKE-03, latency):** `timings.jsonl` is **not** your metric — it is contaminated by batch position and per-batch model reload. Take TTFA in a dedicated single-purpose process (Pitfall 5). Two inputs from here: model load is ~11 s warm-cached (not 01-03's 60.9 s cold), and **the CPU baseline is still missing** — 46/46 clips ran on `mps`, so D-12's hardware-class inference remains one-sided. The 4 accidental CPU renders in `raw/render-aborted-run.jsonl` are a curiosity, not a baseline.

For **01-10 (SPIKE-09):** see deviation 5 — SPIKE-01's check-off has no owner on current frontmatter.

**Carried concerns:**

- **No CPU baseline for Chatterbox** (unchanged from 01-03, now confirmed across a full corpus).
- **`dicta-onnx` is on the critical path for Hebrew**, unlicensed and thinly maintained — a Phase 6 risk.
- **The D-07 size estimate was ~2× low.** Not a problem; worth correcting if it is quoted again.
- Ollama still gates SPIKE-05/06/07/08 (unchanged).

## Self-Check: PASSED

Files verified present on disk:

- `spike/voice/render_corpus.py` — FOUND
- `spike/voice/test_render_plan.py` — FOUND
- `.planning/phases/01-spike-gate/corpus/clips/` — FOUND, **46** WAVs, 9.32 MB
- `.planning/phases/01-spike-gate/corpus/clips_blind/` — FOUND, **46** WAVs
- `.planning/phases/01-spike-gate/corpus/mapping.json` — FOUND, `count: 46`, `seed: 20260723`
- `.planning/phases/01-spike-gate/corpus/timings.jsonl` — FOUND, 46 rows, all `ok: true`
- `.planning/phases/01-spike-gate/raw/render-aborted-run.jsonl` — FOUND, 7 rows

Commits verified in `git log`: `d5b8e20`, `f00a7ad`, `9e883c4` — all FOUND.

Plan verification commands re-run at self-check time:

- Task 1: `ast.parse(render_corpus.py)` + `manual_seed`/`language_id` present → `ok`, exit 0
- Task 2: `clips=46` (≥30), `mapping.json` present, `clips_blind/` present, `timings.jsonl` present → exit 0
- Regression, base venv: `pytest spike/ -q` → **91 passed**, exit 0
- Regression, voice venv: `pytest spike/voice/ -q --ignore=test_readiness.py` → **100 passed**, exit 0

No unintended deletions: `git diff --diff-filter=D HEAD~1 HEAD` on the data commit is empty. The 6 clips deleted mid-plan were the mixed-device artifacts of deviation 1, were never committed, and were re-rendered — the incident's record survives in `raw/render-aborted-run.jsonl`. No venv, weight file or `.onnx` artifact is tracked.

---
*Phase: 01-spike-gate*
*Completed: 2026-07-23*
