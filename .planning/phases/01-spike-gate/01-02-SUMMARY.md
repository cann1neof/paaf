---
phase: 01-spike-gate
plan: 02
subsystem: corpus
tags: [corpus, jsonl, code-switching, failure-grid, blind-judgment, stdlib, pytest]

# Dependency graph
requires:
  - "01-01: spike/ quarantine, spike/pytest.ini, spike/.venv, spike/conftest.py schema mirror"
provides:
  - ".planning/phases/01-spike-gate/corpus/corpus.jsonl — 20-sentence mixed-script failure grid, the phase's single measuring instrument (D-01)"
  - "spike/voice/test_corpus_grid.py — 23 tests enforcing D-02 category coverage and D-03 both-roles coverage mechanically"
  - "spike/voice/shuffle_blind.py — seeded blind shuffle + mapping.json + join_back inverse + judgment template (D-14/D-13)"
  - "spike/voice/test_blind_mapping.py — 28 tests proving the shuffle is a bijection and join_back inverts it exactly"
  - "The {clip_id}__{language_id}.wav clip naming convention, defined once in shuffle_blind.clip_filename()"
affects: [01-05, 01-06, 01-07, 01-08, 01-09, 01-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Surviving data lives under .planning/, throwaway code under spike/ (D-07 split made concrete)"
    - "Test-first for data: the grid-conformance check was written and run RED before the corpus existed"
    - "One definition of a filename convention, exported as a function, so producer (01-05) and consumer (this harness) cannot drift"
    - "Blind-judgment hygiene: the mapping is structurally forbidden from living in the directory being judged"

key-files:
  created:
    - .planning/phases/01-spike-gate/corpus/corpus.jsonl
    - spike/voice/test_corpus_grid.py
    - spike/voice/shuffle_blind.py
    - spike/voice/test_blind_mapping.py
  modified: []
  deleted:
    - spike/voice/.gitkeep

key-decisions:
  - "Corpus record ids are c01..c20 — short, stable, and free of the '__' separator so clip filenames parse unambiguously"
  - "The same-script-russian-english-pair category is implemented as homoglyph pairs (Cyrillic РЕСТОРАН vs Latin PECTOPAH), not as Latin transliteration of Russian — transliteration would bypass Chatterbox's Russian code path entirely"
  - "matrix_lang != embedded_lang is enforced: an unmixed record makes D-06's two-tag render produce two identical clips"
  - "Native-script guards added to the grid test — a transliterated corpus passes every D-02/D-03 check while measuring a pipeline that never ran (RESEARCH §Pitfall 1)"
  - "shuffle_blind copies rather than moves: the tagged render is committed evidence (D-07), so a botched listening pass costs a re-shuffle, not a re-render"
  - "mapping.json is refused if its parent resolves to the blind directory — D-14 enforced structurally rather than by convention"
  - "seed is keyword-only with NO default; there is no way to run an unrecorded shuffle"
  - "SPIKE-01 deliberately left unchecked: this plan builds the instrument, 01-05 takes the measurement"

patterns-established:
  - "Data-fixture test-first: write the conformance check, watch it fail on a missing file, then author the data"
  - "Guard rails as ValueErrors in the harness, each with a message naming the decision it protects (D-07, D-13, D-14)"

requirements-completed: []

coverage:
  - id: D1
    description: "corpus.jsonl holds 20 mixed-script en/ru/he/es sentences forming the deliberate failure grid, all six D-02 categories present, every language in both matrix and embedded roles (D-03)"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "spike/voice/test_corpus_grid.py (23 tests) via `uv run --python spike/.venv/bin/python pytest spike/voice/test_corpus_grid.py -q`"
        status: pass
    human_judgment: false
  - id: D2
    description: "Hebrew and Russian records carry native script, not Latin transliteration, and each category record actually exercises the stress it claims (digit adjacent to Hebrew, digit present, English frame, both scripts in the homoglyph records)"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "test_corpus_grid.py::test_hebrew_records_use_hebrew_script, ::test_russian_records_use_cyrillic_script, ::test_hebrew_rtl_records_put_a_digit_next_to_hebrew, ::test_same_script_pair_records_are_russian_english_and_mix_both_scripts"
        status: pass
    human_judgment: false
  - id: D3
    description: "The blind shuffle is seeded and reversible: for a fixed seed every clip id maps to exactly one opaque name and join_back restores clip id + language_id with no collisions and no drops (D-14)"
    requirement: "SPIKE-01"
    verification:
      - kind: unit
        ref: "spike/voice/test_blind_mapping.py (28 tests) via `uv run --python spike/.venv/bin/python pytest spike/voice/test_blind_mapping.py -q`"
        status: pass
    human_judgment: false

# Metrics
duration: 6min
completed: 2026-07-23
status: complete
---

# Phase 1 Plan 02: Corpus & Blind Harness Summary

**Authored the phase's single measuring instrument — 20 mixed-script en/ru/he/es sentences built as a deliberate failure grid under `.planning/` where it survives `spike/` deletion — plus the stdlib-only seeded blind-shuffle harness that hides `language_id` from the native-ear judgment and joins it back afterwards. 51 tests, 0.25s, no model inference.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-07-23T10:24:49Z
- **Completed:** 2026-07-23T10:30:23Z
- **Tasks:** 3
- **Files created:** 4 (1 data fixture, 1 harness module, 2 test modules); 1 placeholder deleted

## Corpus Composition

`.planning/phases/01-spike-gate/corpus/corpus.jsonl` — 20 records, 3,586 bytes, UTF-8 JSONL, ids `c01`–`c20`.

### Category coverage (D-02 — all six present)

| Count | Category | Example id |
|------:|----------|-----------|
| 3 | `single-foreign-noun-in-english-frame` | c01 `Can you add кефир to the shopping list…` |
| 4 | `mid-clause-switch` | c04 `Я уже отправил отчёт, but the attachment never went through.` |
| 4 | `hebrew-rtl-adjacent-to-latin-digits` | c08 `הפגישה נקבעה ל-15:00 in the small conference room.` |
| 3 | `proper-nouns` | c13 `Alejandro dijo que Дмитрий llega el martes…` |
| 3 | `numbers-and-units` | c16 `Поставь таймер на 20 минут and let the dough rest.` |
| 3 | `same-script-russian-english-pair` | c18 `…было написано РЕСТОРАН, but my phone read it as PECTOPAH.` |

### Role coverage (D-03 — every language in both roles)

| Language | as `matrix_lang` | as `embedded_lang` |
|---|---:|---:|
| en | 9 | 9 |
| ru | 5 | 4 |
| he | 3 | 4 |
| es | 3 | 3 |

Under D-06 (each sentence rendered once per tag) this yields exactly **40 clips** for the 01-05 render.

### Category design notes

- **Hebrew RTL / Latin digits** is enforced as *actual adjacency*, not mere co-occurrence: a regex requires a Hebrew codepoint and an ASCII digit separated by at most three joiner characters (space, maqaf/hyphen, geresh/gershayim, colon). The four records use `ל-15:00`, `ב-8:45`, `250 מ״ל`, `1.5 ליטר … 12 שקלים`. A sentence that merely mentions a number elsewhere does not exercise the bidi boundary and is rejected.
- **The same-script pair** is implemented as **homoglyphs**, which is what makes the category interesting: Cyrillic `РЕСТОРАН` / Latin `PECTOPAH`, Cyrillic `СОК` / Latin `COK`, Cyrillic `ТОРТ` / Latin `TOPT`. Each pair is visually identical but lives in a different Unicode block, so script gives a tokenizer or language detector no signal at all. Verified by `unicodedata.name()` that each intended form really is in its intended block.
- **Latin-script Spanish and English co-occur without diacritics in places on purpose** (`sobremesa`, `4 kilos y medio`) — an es/en mix that a script-based detector cannot separate either.

## Blind Harness

`spike/voice/shuffle_blind.py` (396 lines, **stdlib only** — imports in both spike venvs, will never pull torch).

| Entry point | Purpose |
|---|---|
| `clip_filename(clip_id, language_id)` | Single definition of the `{clip_id}__{language_id}.wav` convention, so the 01-05 renderer and this harness cannot drift |
| `parse_clip_name(name)` | Strict inverse; raises on malformed names and unknown tags |
| `shuffle_blind(src, blind_dir, *, seed)` | Copies clips to opaque `blind_NNN` names, writes `mapping.json` |
| `load_mapping(path)` | Reads and re-verifies bijection + declared count before anyone trusts it |
| `judgment_template(mapping, out)` | Blank, tag-free file keyed by blind name for D-13 verbatim impressions |
| `join_back(mapping, judgments)` | Restores `clip_id` + `language_id`, sorted so a sentence's matrix and embedded renders land adjacent |
| `main()` | `shuffle` / `join` CLI, smoke-tested end to end |

**Refusals built in** (each raises with a message naming the decision it protects):

- `mapping.json` whose parent resolves to the blind directory — D-14 defeated in the most banal way possible.
- A language tag outside `{en, ru, he, es}` — a typo'd tag would otherwise be judged as if real.
- Two source files claiming the same `(clip_id, language_id)` — one render silently overwrote another.
- A non-empty blind directory without explicit `overwrite=True` — mixing two renders into one listening pass invalidates the pass.
- A hand-edited/truncated `mapping.json` (declared `count` vs actual).
- Judgments referencing blind names absent from the mapping — the judgment file and the mapping came from different shuffles.
- `seed` is **keyword-only with no default**: there is no way to run an unrecorded shuffle.

Clips are **copied, not moved**, so the tagged render stays intact as committed evidence (D-07).

## Task Commits

1. **Task 1: grid-conformance test, written red** — `466520f` (`test`)
2. **Task 2: author corpus.jsonl** — `c17ddfb` (`feat`)
3. **Task 3: blind-shuffle harness + reversibility test** — `002af67` (`feat`)

**Plan metadata:** see the `docs(01-02)` commit following this SUMMARY.

## Test Results

| Suite | Tests | Result |
|---|---:|---|
| `spike/voice/test_corpus_grid.py` | 23 | pass |
| `spike/voice/test_blind_mapping.py` | 28 | pass |
| Full quarantine suite `spike/` | **61** | pass in 0.25s |

The RED-before-GREEN sequence is visible in the git history: `466520f` (test only, corpus absent) then `c17ddfb` (corpus). At `466520f` the run failed with `Corpus fixture missing: …/corpus/corpus.jsonl`, which is the proof the check is live rather than vacuous.

`test_blind_mapping.py::test_round_trip_over_the_real_corpus_clip_set` derives its ~40 clip names **from the committed corpus itself**, so the harness is exercised against the real instrument rather than only against invented names — while still producing no audio.

## Decisions Made

- **Ids are `c01`–`c20`.** Short, stable, and — importantly — free of the `__` separator, which `clip_filename()` rejects so a filename can always be parsed back unambiguously.
- **`matrix_lang != embedded_lang` is a hard constraint.** A record whose two tags coincide is not code-switched, and D-06's two-tag render would emit two identical clips under different names — noise that would look like a nondeterminism finding.
- **Native-script assertions live in the grid test, not just in the authoring intent.** Chatterbox routes Hebrew through `add_hebrew_diacritics()` and Russian through `russian_text_stresser` (01-RESEARCH §Pitfall 1). Latin transliteration bypasses both, so a transliterated corpus would satisfy every D-02/D-03 check while measuring a pipeline that never ran.
- **The record count band is 18–24.** "~20" (D-01) needs a machine-checkable reading; a corpus that quietly shrank to six records would otherwise still satisfy every category and role check.
- **D-14 is enforced structurally.** Rather than documenting "don't put the mapping next to the clips", `shuffle_blind` raises if you try.
- **`judgment_template()` was added** so the listening pass has a file whose keys already match the mapping. `join_back` accepts a judgments mapping; without a template the format would be undocumented, and a hand-rolled one risks orphaned impressions or silently skipped clips.
- **SPIKE-01 left unchecked in REQUIREMENTS.md.** See deviations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `uv run pytest …` cannot resolve an interpreter (carried forward from 01-01)**

- **Found during:** Task 1 verification
- **Issue:** The plan's three `<automated>` verify commands are all `uv run pytest …` from the repo root. As 01-01 established, there is deliberately no root `pyproject.toml` and no root `.venv`, so `uv run` has nothing to resolve against and fails with `Failed to spawn: pytest`.
- **Fix:** Used the canonical invocation recorded in `spike/README.md` and 01-01-SUMMARY: `uv run --python spike/.venv/bin/python pytest <target> -q`. No new venv, no root artifact, SC#5 intact.
- **Files modified:** none (invocation only)
- **Commit:** n/a — applies to all three task verifications

**2. [Rule 2 - Missing Critical] Grid test asserts more than the plan's two named properties**

- **Found during:** Task 1
- **Issue:** The plan asks for six-category coverage plus the D-03 both-roles constraint. A corpus can satisfy both while being useless: twenty Latin-transliterated sentences, or `hebrew-rtl-adjacent-to-latin-digits` records with no digit anywhere near the Hebrew, or records whose matrix and embedded tags are the same language. Each of those silently weakens SPIKE-01/02/04/08 — the exact failure mode threat `T-01-02-INT` names.
- **Fix:** Added native-script guards (Hebrew/Cyrillic/Latin per role), per-category semantic checks (English frame; digit adjacent to Hebrew via a bidi-boundary regex; digit present; Cyrillic **and** Latin co-present in the homoglyph records), a `matrix_lang != embedded_lang` guard, id uniqueness, and the 18–24 record band.
- **Files modified:** `spike/voice/test_corpus_grid.py`
- **Verification:** 23 tests pass against the authored corpus; each new assertion has at least one record that exercises it.
- **Commit:** `466520f`

**3. [Rule 2 - Missing Critical] Integrity refusals in the shuffle harness**

- **Found during:** Task 3
- **Issue:** The plan specifies shuffle + `mapping.json` + `join_back`. As specified, the harness would happily (a) write the mapping into the directory being judged, defeating D-14 outright; (b) accept a typo'd `language_id`; (c) accept two files claiming the same tag; (d) shuffle a second render into a directory still holding the first, mixing two populations into one listening pass; (e) trust a hand-edited mapping. Each of those yields impressions attached to the wrong tags — worse than no impressions, because it looks like data.
- **Fix:** Added the six refusals tabulated above, each raising `ValueError`/`FileExistsError` with a message naming the decision it protects.
- **Files modified:** `spike/voice/shuffle_blind.py`, `spike/voice/test_blind_mapping.py`
- **Verification:** 9 of the 28 tests target these guards specifically.
- **Commit:** `002af67`

**4. [Rule 3 - Blocking] Removed `spike/voice/.gitkeep`**

- **Found during:** Task 1
- **Issue:** The placeholder existed only because git cannot track an empty directory (01-01 deviation 4). The directory now has real content.
- **Fix:** `git rm spike/voice/.gitkeep`. This is the one deletion in this plan's history and it is intentional.
- **Commit:** `466520f`

### Deliberate non-action

**5. `SPIKE-01` was NOT marked complete in REQUIREMENTS.md**

SPIKE-01 reads *"**Measure** whether Chatterbox Multilingual V3 handles intra-sentence code-switching, using ≥20 real mixed-script sentences (en/ru/he/es) with varying `language_id`."* This plan builds the ≥20 sentences and the varying-`language_id` machinery; it takes no measurement and touches no model. Plan `01-05` carries the same requirement ID and owns the render. Checking the box now would put an unmeasured claim into the traceability matrix that the SC#4 claim audit exists to catch — the same reasoning 01-01 applied to SPIKE-09. `requirements-completed: []` reflects that.

### Documentation discrepancy noted

**6. The plan cites "01-RESEARCH §Pitfall 5 (a shuffle needs a fixed seed)"**

§Pitfall 5 is actually *"A memory leak silently corrupts the timing series"* (subprocess batching for the render). The seed requirement for the blind shuffle comes from 01-VALIDATION.md's SPIKE-02 row, which itself cross-references Pitfall 5. The requirement was honoured regardless — the seed is mandatory and recorded in `mapping.json` — but the citation is noted here so a later reader is not sent to the wrong paragraph. (Pitfall 6's separate `torch.manual_seed(FIXED)` requirement belongs to the 01-05 render, not to this harness.)

---

**Total deviations:** 3 auto-fixed (2 missing-critical, 1 blocking) plus 1 mechanical cleanup, 1 deliberate non-action, 1 documentation note.
**Impact on plan:** No scope creep — nothing outside the plan's four declared files was touched, no model was loaded, no WAV was produced. Every plan acceptance criterion passes.

## Issues Encountered

None blocking. Two things worth recording:

- **`pytest` resolves `import shuffle_blind` via rootdir insertion.** With `spike/pytest.ini` making `spike/` the rootdir and no `__init__.py` in `spike/voice/`, pytest's default `prepend` import mode puts `spike/voice/` on `sys.path`, so the test imports the harness as a top-level module. This works, is stable for the life of the quarantine, and needs no packaging — but it is why the module must keep a collision-free name.
- **`random.Random(seed).shuffle` is the reproducibility mechanism, and the mapping is the durable record.** Python guarantees the core generator's sequence across versions, but the harness does not rely on that alone: `mapping.json` records the realized permutation, so a Phase 7 re-run can diff against the actual order that was judged rather than re-deriving it.

## Known Stubs

None. Every artifact is complete for its stated purpose. `shuffle_blind.py` deliberately performs **no** synthesis — the plan forbids model inference here, and 01-05 owns the render that produces the clips this harness will operate on.

## Deferred — Human Action Required

None for this plan. Nothing here required listening, judging, or authenticating.

For situational awareness, the human-gated work this plan *prepares* is the SPIKE-02 native-ear pass: after 01-05 renders the 40 clips, run
`shuffle_blind.py shuffle <clips> <clips_blind> --seed <N> --template judgments.json`, listen through `blind_000…blind_039` writing verbatim impressions into `judgments.json` (which contains no tags), then `shuffle_blind.py join mapping.json --judgments judgments.json`. D-20 additionally asks for Russian and Spanish spot-checks alongside the deep Hebrew judgment.

## User Setup Required

None — no external service, no credentials, no downloads. This plan added no dependencies whatsoever; everything runs on the stdlib inside the existing `spike/.venv`.

## Next Phase Readiness

**Ready.** The instrument exists and is mechanically defended.

- **01-03 / 01-04** (venv provisioning) are unaffected by this plan and can proceed; `shuffle_blind.py` imports nothing that could break collection in either venv.
- **01-05** (render) should call `shuffle_blind.clip_filename(clip_id, language_id)` to name its outputs rather than formatting the string itself — that is the whole reason the function is exported. It must render each corpus record twice per D-06 (matrix tag and embedded tag), giving 40 clips, and must call `torch.manual_seed(FIXED)` before *each* `generate()` per §Pitfall 6.
- **01-06 / 01-08** consume `corpus.jsonl` directly for transcription and round-trip accounting; the five-key schema is stable and asserted.

**Carried concerns:**

- The corpus is **authored**, not transcribed from speech (D-02 by design), and SPIKE-04 feeds Whisper this text via Chatterbox output — so D-05's binding caveat still travels with every downstream result: this measures *synthetic* mixed speech, and Chatterbox failures are not separable from Whisper failures.
- `en` is over-represented as a matrix language (9 of 20) relative to ru/he/es. That is a direct consequence of D-02 dedicating a whole category to English-framed sentences, and D-03's constraint is satisfied — but a reader of the final numbers should not read en/ru/he/es coverage as balanced.
- Ollama is still not installed and gates SPIKE-05/06/07/08 (unchanged from 01-01).

## Self-Check: PASSED

Files verified present on disk:

- `.planning/phases/01-spike-gate/corpus/corpus.jsonl` — FOUND (20 lines, 3,586 bytes)
- `spike/voice/test_corpus_grid.py` — FOUND (299 lines)
- `spike/voice/shuffle_blind.py` — FOUND (396 lines)
- `spike/voice/test_blind_mapping.py` — FOUND (395 lines)

Commits verified in `git log`:

- `466520f` — FOUND (`test(01-02)`, red grid check)
- `c17ddfb` — FOUND (`feat(01-02)`, corpus)
- `002af67` — FOUND (`feat(01-02)`, blind harness)

Verification commands re-run at self-check time (canonical invocation, see deviation 1):

- `pytest spike/voice/test_corpus_grid.py spike/voice/test_blind_mapping.py -q` → `51 passed in 0.25s`, exit 0
- `pytest spike/ -q` → `61 passed in 0.25s`, exit 0
- Homoglyph script audit via `unicodedata.name()` → `РЕСТОРАН`/`СОК`/`ТОРТ` = CYRILLIC, `PECTOPAH`/`COK`/`TOPT` = LATIN, all present in their records
- CLI end-to-end (`shuffle` → `join` on six throwaway files) → opaque names written, tags restored, exit 0

No unintended deletions: the single deletion in this plan is `spike/voice/.gitkeep`, documented in deviation 4.

---
*Phase: 01-spike-gate*
*Completed: 2026-07-23*
