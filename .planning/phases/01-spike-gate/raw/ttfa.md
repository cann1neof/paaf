# SPIKE-03 — Chatterbox Time-To-First-Audio (TTFA), Mac MPS + CPU

> **D-12 caveat (rides with every number here):** these are **Apple-Silicon** measurements
> on an M-series Mac with 18 GB unified memory. The hardware-class recommendation they feed
> is an **INFERENCE from Apple Silicon, explicitly NOT a measured CUDA result.** It directs
> an actual purchase, so the caveat is not decoration.

Harness: `spike/voice/measure_ttfa.py` — a **dedicated single-purpose process** (Pitfall 5),
not a by-product of the corpus render. It loads Chatterbox once, discards the first (cold)
generate, and reports the steady-state warm timings.

**What "TTFA" means here (Pitfall 3):** Chatterbox exposes **no streaming / first-chunk
API** — `generate()` returns the whole waveform. So time-to-first-audio for one short
utterance *is* the wall-clock of one `generate()` call returning. There is no earlier "first
audio" moment to measure on this engine.

**Watermarking (Pitfall 11 / VOICE-12):** Chatterbox watermarks unconditionally, there is no
flag to disable it, and that cost is **inside the timed region** below — exactly as a real
user pays it.

## Fixed inputs

| Knob | Value |
|---|---|
| sentence | `"Your meeting starts in ten minutes."` (one short reply, ~4 s of speech) |
| seed | `1234`, set immediately before **each** `generate()` (Pitfall 6) |
| gen params | `exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=2.0, min_p=0.05, top_p=1.0` |
| language_id | `"en"` — English, so the Dicta/Hebrew diacritization path is **not** on the timed region for this sentence |
| device | the STRING `"mps"` / `"cpu"` (Pitfall 4) |
| torch / chatterbox | `2.6.0` / `0.1.7` |

## Warm TTFA — the headline numbers

| Device | model load (s) | cold generate (s) | **cold TOTAL (s)** | **warm p50 (s)** | warm p95 (s) | warm min–max (s) | audio (s) | warm RTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **mps** | 11.76 | 9.33 | **21.09** | **6.27** | 6.73 | 5.87 – 6.73 | 3.88 | ~1.62× |
| **cpu** | 10.08 | 23.52 | **33.60** | **21.70** | 22.75 | 21.27 – 22.75 | 7.20 | ~3.01× |

- **cold TOTAL** = model load + first generate — the cold start a user feels once per
  process launch. The first generate is **discarded** from the warm statistics (Pitfall 10).
- **warm** = every subsequent generate of the same sentence — the steady-state latency that
  dominates a running assistant. `warm < cold` holds on **both** devices (the SPIKE-03
  integrity check, `measure_ttfa.warm_beats_cold`).
- Raw warm samples — mps: `6.27, 6.06, 5.87, 6.66, 6.73`; cpu: `21.70, 21.27, 22.75`.

### Reading these across devices — use RTF, not raw seconds

The **same sentence and seed** produced **3.88 s** of audio on `mps` but **7.20 s** on `cpu`.
01-03 confirmed seeded synthesis is *bitwise identical on a single backend* but flagged that
CPU-vs-MPS divergence was untested — it is now measured, and **the two backends diverge in
output length**. Raw TTFA seconds are therefore **not** directly comparable across devices.
The fair cross-device metric is the **real-time factor** (synth seconds per audio second):

- **mps ≈ 1.6× RTF**, **cpu ≈ 3.0× RTF** → **CPU is ~1.9× slower per second of speech.**

This closes 01-03/01-05's carried gap: the CPU baseline that was *never exercised* (46/46
corpus clips ran on `mps`) now exists, so D-12's hardware-class inference is no longer
one-sided. Neither device failed — `mps` is usable (as 01-03 found) **and** `cpu` is usable,
just ~2× the per-second cost.

## The runaway caveat — Chatterbox latency is sentence-dependent, and the tail is large

The sentence above was chosen **after** a first pick, `"Set a timer for ten minutes."`, drove
the sampler into **alignment-repetition runaway**: it kept sampling to a forced-EOS at ~178
steps, at **64–89 s per warm generate on mps** (vs ~6 s for the well-behaved sentence).
Recorded verbatim because it is a real property a buyer must know:

- Chatterbox `generate()` latency is **not fixed per short sentence** — a phrase that trips
  `alignment_stream_analyzer` (`forcing EOS, alignment_repetition=True`) can cost **~10×** the
  typical time. 01-05 already saw this shape (`c08__he`: 63 s of synth for 10 s of audio) and
  that 41/46 corpus clips emitted a forced-EOS.
- The p50/p95 in the table describe a **typical** short reply. The realistic worst case is far
  worse, and a running assistant needs a **generation-time cap / watchdog** so a stuck
  utterance cannot hang the voice loop. Flagged for the app phase.

## Provenance

- `measure_ttfa.py --device mps --n-warm 5` and `--device cpu --n-warm 3`, run **solo** (no
  other model-loading plan concurrent — Pitfall 10), 2026-07-25.
- `warm < cold` verified on both devices; `mps` and `cpu` both `ok=true` (no device failure to
  record this run — an unusable device would have been captured verbatim per D-11/D-12).
- Working JSON (`spike/voice/.ttfa_mps.json`, `.ttfa_cpu.json`) is gitignored scratch; this
  file is the durable record.
