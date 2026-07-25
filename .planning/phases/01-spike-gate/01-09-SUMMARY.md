---
phase: 01-spike-gate
plan: 09
subsystem: voice
tags: [chatterbox, faster-whisper, ollama, latency, ttfa, walking-skeleton, mps, cpu, spike-03, spike-08]

# Dependency graph
requires:
  - "01-03: voice venv, GATE 0 GREEN, repair_dicta(), mps measured usable, cpu baseline still missing"
  - "01-04: Ollama 0.32.1 daemon on 127.0.0.1:11434, qwen3.5:2b latency model pulled"
  - "01-05: corpus/clips/ (c01__en.wav reused as round-trip input), GEN_PARAMS, seed 1234"
  - "01-07: faster-whisper large-v3 STT harness pattern (cpu/int8, no Metal backend)"
provides:
  - "spike/voice/measure_ttfa.py — dedicated single-purpose TTFA process, warm-vs-cold on mps AND cpu strings, records audio duration + RTF, captures an mps failure verbatim (D-11/D-12)"
  - "spike/voice/roundtrip.py — WAV-in -> faster-whisper -> Ollama qwen3.5:2b -> Chatterbox -> WAV-out Walking Skeleton with per-stage boundaries + explicit t_unattributed residual"
  - "spike/voice/test_ttfa_harness.py + test_roundtrip_accounting.py — fast engine-free accounting tests with negative controls + slow real-engine tests gated on the voice venv"
  - ".planning/phases/01-spike-gate/raw/ttfa.md — warm TTFA (mps 6.27s p50 / cpu 21.70s p50), cross-backend divergence, runaway caveat"
  - ".planning/phases/01-spike-gate/raw/roundtrip.md — per-stage budget (TTS 65%, STT 34%, LLM 1.4%, unattributed ~0), D-12 caveat in caption"
  - "The two hardware-directing numbers: warm TTFA and a ~49s round-trip budget, both with their Apple-Silicon caveat"
affects: [01-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dedicated single-purpose latency process (Pitfall 5): TTFA is measured in a process that only loads the model and times one sentence, never as a by-product of a batch render"
    - "Residual-forced accounting: t_unattributed = wall - sum(stages) is carried explicitly so a large residual proves the budget is wrong rather than being silently absorbed into a stage"
    - "Fair cross-device metric: raw seconds are not comparable across backends that emit different audio lengths for the same seed — RTF (synth per audio-second) is"
    - "REST-over-stdlib for a cross-venv engine: the LLM stage hits the Ollama HTTP API via urllib, so the round trip needs no dependency the voice venv lacks"
    - "Negative-control accounting predicates: warm==cold and a large residual must both be flagged False, so the integrity checks are not vacuous"

key-files:
  created:
    - spike/voice/measure_ttfa.py
    - spike/voice/roundtrip.py
    - spike/voice/test_ttfa_harness.py
    - spike/voice/test_roundtrip_accounting.py
    - .planning/phases/01-spike-gate/raw/ttfa.md
    - .planning/phases/01-spike-gate/raw/roundtrip.md
  modified:
    - .gitignore

key-decisions:
  - "TTFA sentence swapped after the first pick triggered alignment-repetition runaway (64-89s/generate); the runaway is recorded as a caveat because Chatterbox latency is sentence-dependent with a large tail"
  - "The LLM stage talks to the Ollama REST API via stdlib urllib rather than the ollama package, which lives in 01-04's bake-off venv, not this voice venv — no new dependency, and the framework speaks HTTP to Ollama anyway"
  - "Report RTF, not raw seconds, across mps/cpu: the same seed produced 3.88s audio on mps and 7.20s on cpu, so raw TTFA is not comparable and RTF (~1.6x vs ~3.0x) is the honest cross-device number"
  - "Warm-is-slower-than-cold in the co-resident round trip is reported, not smoothed: it is the strongest evidence that 18 GB is the binding constraint (Pitfall 10)"

patterns-established:
  - "Measure-solo-then-record: TTFA finished and its process exited before the round trip started, so the co-residence measured was Whisper+Chatterbox+Ollama and nothing else"
  - "Working JSON is gitignored scratch; the durable evidence is raw/*.md"

requirements-completed: [SPIKE-03, SPIKE-08]

coverage:
  - id: D1
    description: "Chatterbox warm TTFA for one short sentence is measured on Mac MPS AND Mac CPU (D-11), warm (cold model-load + first synth discarded), with warm < cold on both"
    requirement: "SPIKE-03"
    verification:
      - kind: unit
        ref: "test_ttfa_harness.py::test_real_mps_measurement_warm_beats_cold (slow, voice venv), ::test_negative_control_warm_equal_cold_is_not_a_pass (fast)"
        status: pass
      - kind: integration
        ref: "raw/ttfa.md: mps warm p50 6.27s < cold-total 21.09s; cpu warm p50 21.70s < cold-total 33.60s; both ok=true"
        status: pass
    human_judgment: false
  - id: D2
    description: "A real WAV-in -> STT -> LLM -> TTS -> WAV-out round trip produces a per-stage latency budget with an explicit unattributed residual (Pitfall 10)"
    requirement: "SPIKE-08"
    verification:
      - kind: unit
        ref: "test_roundtrip_accounting.py::test_real_roundtrip_stages_sum_to_wall (slow), ::test_negative_control_large_residual_is_not_small + ::test_negative_control_wrong_residual_fails_reconstruction (fast)"
        status: pass
      - kind: integration
        ref: "raw/roundtrip.md budget table: STT 34.1%, LLM 1.4%, TTS 64.5%, unattributed ~0%; warm p50 wall 49.08s; residual < 1e-6 s"
        status: pass
    human_judgment: false
  - id: D3
    description: "The hardware-class inference is recorded as an inference from Apple Silicon, explicitly NOT a measured CUDA result (D-12)"
    requirement: "SPIKE-08"
    verification:
      - kind: integration
        ref: "grep -qiE 'D-12|Apple Silicon|not a measured CUDA|inference' raw/roundtrip.md; caveat in the table caption and in ttfa.md header"
        status: pass
    human_judgment: true
    rationale: "Whether the caveat faithfully qualifies the purchase recommendation is a human reading the prose against the claim, not a machine assertion."
  - id: D4
    description: "The round trip is the phase's Walking Skeleton — the thinnest end-to-end proof the stack is wired and co-resident on this machine"
    requirement: "SPIKE-08"
    verification:
      - kind: integration
        ref: "roundtrip.py asserted warm (non-empty transcript, reply, and audio); it ran, so the stack is wired: c01__en.wav -> 'kefir' transcript -> LLM reply -> 3.8s audio out"
        status: pass
    human_judgment: false

# Metrics
duration: 37min
completed: 2026-07-25
status: complete
---

# Phase 1 Plan 09: TTFA + Round-Trip Latency Summary

**The two hardware-directing numbers now exist, warm and solo, with their Apple-Silicon
caveat attached. Chatterbox warm TTFA for one short (~4 s) sentence is 6.27 s on `mps` and
21.70 s on `cpu` (warm < cold on both); the same seed emits different audio lengths per
backend, so the fair cross-device figure is RTF — ~1.6× on mps, ~3.0× on cpu. The Walking
Skeleton round trip is wired end-to-end (WAV → Whisper → qwen3.5:2b → Chatterbox → WAV) at a
~49 s warm-p50 wall, and it is TTS-dominated (65 %), STT a third (34 %), and the local LLM
trivial (1.4 %), with a ~0 unattributed residual proving the accounting. The D-12 caveat
rides in the table caption: this is an inference from Apple Silicon, NOT a measured CUDA
result.**

## The two numbers, plainly

| Measurement | Value | Where |
|---|---|---|
| **TTFA warm p50 — mps** | **6.27 s** (cold-total 21.09 s) | `raw/ttfa.md` |
| **TTFA warm p50 — cpu** | **21.70 s** (cold-total 33.60 s) | `raw/ttfa.md` |
| **Round-trip warm p50 (wall)** | **49.08 s** | `raw/roundtrip.md` |
| **Dominant round-trip stage** | **TTS (Chatterbox), 64.5 %** | `raw/roundtrip.md` |

- **Warm < cold holds on both devices** — the SPIKE-03 integrity check.
- **Cross-backend divergence:** identical sentence + seed produced **3.88 s** audio on mps but
  **7.20 s** on cpu, so raw TTFA seconds are not comparable across devices. RTF is: **cpu is
  ~1.9× slower per second of speech.** This closes 01-03/01-05's carried gap — the CPU baseline
  that was never exercised (46/46 corpus clips ran on mps) now exists.
- **Per-stage budget (warm p50):** STT 16.66 s (34.1 %), LLM 0.66 s (1.4 %), **TTS 31.50 s
  (64.5 %)**, unattributed ~0 s. If you want the round trip faster, Chatterbox is the lever.

## Integrity protections (as the plan required)

- **Solo run (Pitfall 10).** The TTFA process exited before the round trip started, so the
  co-residence measured was exactly Whisper + Chatterbox + Ollama.
- **Warm-only, cold discarded.** First generate / first trip dropped from every statistic.
- **Explicit residual.** `t_unattributed = wall − Σ stages` carried per iteration; it came back
  < 1e-6 s, so the stages reconstruct the wall and the budget is not fiction.
- **No swap detected**, but **warm drifts SLOWER than cold** in the co-resident trip (38.9 →
  50.1 s) — reported, not smoothed, because it is the clearest evidence that 18 GB is the
  binding constraint. Process peak RSS was 3.65 GB (a floor: excludes the separate Ollama
  daemon and MPS/unified allocations).
- **D-12 caveat travels** in the round-trip table caption and the TTFA header: an Apple-Silicon
  inference, explicitly not a CUDA measurement — material because it directs a purchase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] The first TTFA sentence drove Chatterbox into alignment-repetition runaway**

- **Found during:** Task 2, first mps measurement.
- **Issue:** `"Set a timer for ten minutes."` tripped `alignment_stream_analyzer`
  (`forcing EOS, alignment_repetition=True`), sampling to ~178 steps at **64–89 s per warm
  generate** — vs ~6 s for a well-behaved sentence and vs the ~9 s corpus median (01-05). A
  TTFA that reports a stuck utterance misdirects the hardware decision.
- **Fix:** Smoke-tested four clean candidates, chose `"Your meeting starts in ten minutes."`
  (RTF ~2×, ~4 s audio, no runaway). Recorded the runaway verbatim in `ttfa.md` as a binding
  caveat — Chatterbox latency is **sentence-dependent with a ~10× tail**, and the app needs a
  generation-time watchdog. Also added audio-duration + RTF capture to the harness, without
  which the TTFA number is uninterpretable.
- **Files:** `spike/voice/measure_ttfa.py`. **Commit:** `56d1eeb`.

**2. [Rule 3 — Blocking] The `ollama` package is not in the voice venv**

- **Found during:** Task 2, round-trip wiring.
- **Issue:** 01-04 installed `ollama-py` into the **bake-off** venv, not the voice venv, so
  `import ollama` in the round trip raised `ModuleNotFoundError`. The round trip needs all
  three engines in one process, and only Whisper + Chatterbox live in the voice venv.
- **Fix:** The LLM stage now talks to the Ollama **REST API** (`/api/chat`, `think:false`,
  bounded `num_predict`) via **stdlib `urllib`** — no new dependency, works in any venv, and
  the framework speaks HTTP to Ollama anyway. Not a package install (Rule-3 exclusion honoured:
  no similarly-named substitute was reached for).
- **Files:** `spike/voice/roundtrip.py`. **Commit:** `56d1eeb`.

### Not a deviation, recorded

- **`mps` and `cpu` both `ok=true`** — no device failure to record this run. The verbatim-
  exception path (D-11/D-12) exists and is tested, but was not exercised because both devices
  worked.

## Test Results

| Suite | Venv | Tests | Result |
|---|---|---:|---|
| `test_ttfa_harness.py` + `test_roundtrip_accounting.py` (incl. slow real-engine) | voice | **13** | pass (160.9 s) |
| Same, fast only (`-m "not slow"`) | base | **11** (2 skipped/deselected) | pass |
| Full quarantine `spike/ -m "not slow"` | base | **130** | pass (0.41 s) |

New this plan: 5 fast engine-free accounting tests + 1 slow real-engine test per harness, each
with a **negative control** (warm==cold and large-residual must both read False), so the
integrity checks cannot pass vacuously.

## Known Stubs

None. Every declared artifact exists, is committed, and carries real measured data.

## Threat Flags

None. The plan's threat register (T-01-09-INT measurement validity, T-01-09-CLAIM hardware
claim) was mitigated as designed: solo execution, warm-only with cold discarded, an explicit
residual that proves the accounting, no swap detected (and the drift reported honestly), and
the D-12 caveat carried in the caption. No new network surface — the LLM stage hits the same
loopback Ollama daemon 01-04 already stood up; no egress.

## User Setup Required

None. Ollama daemon (01-04) and all model weights (01-03/01-04) were already present.

## Next Phase Readiness

**Ready.** Both hardware-directing numbers exist with their caveats, and the full voice stack
is proven wired end-to-end on this machine.

- **For 01-10 (SPIKE-09, "record measured reality"):** the findings to carry into DECISIONS.md
  are (a) warm TTFA mps 6.27 s / cpu 21.70 s, warm<cold, with the **RTF cross-device caveat**
  and the **D-12 Apple-Silicon-not-CUDA caveat**; (b) round trip ~49 s warm, TTS-dominated,
  LLM trivial; (c) the **sentence-dependent runaway tail** in Chatterbox and the co-resident
  **warm-slower-than-cold drift** as the concrete face of the 18 GB constraint. 01-05's
  deviation 5 still flags that **SPIKE-01's check-off has no owner** and proposes 01-10 own it.
- **Carried concerns:** Chatterbox is the latency cost centre with a large tail (needs a
  generation-time watchdog in the app); 18 GB is the binding constraint under co-residence; the
  shipped-hardware latency is the **unmeasured D-12 inference** (CUDA on the Linux target), not
  the 40–50 s measured here.

## Self-Check: PASSED

Files verified present on disk:

- `spike/voice/measure_ttfa.py` — FOUND
- `spike/voice/roundtrip.py` — FOUND
- `spike/voice/test_ttfa_harness.py` — FOUND
- `spike/voice/test_roundtrip_accounting.py` — FOUND
- `.planning/phases/01-spike-gate/raw/ttfa.md` — FOUND (mps + cpu warm TTFA)
- `.planning/phases/01-spike-gate/raw/roundtrip.md` — FOUND (budget + unattributed + D-12 caveat)

Commits verified in `git log`: `c5f0a3a` (harnesses + tests), `56d1eeb` (measurements + raw +
gitignore) — both FOUND.

Plan verification commands re-run at self-check time:

- Task 1: `ast.parse` both harnesses + `'mps'`/`'cpu'` in measure_ttfa + `'unattributed'` in
  roundtrip → `ok`.
- Task 2: `raw/ttfa.md` + `raw/roundtrip.md` exist; `mps`/`cpu` in ttfa.md; `unattributed` and
  `D-12|Apple Silicon|not a measured CUDA|inference` in roundtrip.md → exit 0.
- Tests: voice venv **13 passed** (incl. both slow real-engine tests); base venv full
  quarantine `-m "not slow"` **130 passed**.

No unintended deletions: both task commits are insertions only over new files plus a 7-line
`.gitignore` addition. The transient `.ttfa*.json` / `.roundtrip.json` scratch is gitignored,
not tracked.

---
*Phase: 01-spike-gate*
*Completed: 2026-07-25*
