# SPIKE-08 — Round-trip latency budget (the Walking Skeleton)

Harness: `spike/voice/roundtrip.py`. One real **WAV-in → STT → LLM → TTS → WAV-out** trip.
This is the Phase-1 **Walking Skeleton**: the thinnest end-to-end proof that Chatterbox
STT/LLM/TTS are **wired and co-resident** on this machine. It ran — so the stack is wired.

## The stack that was co-resident (Pitfall 10 — the binding constraint)

| Stage | Engine | Device | Notes |
|---|---|---|---|
| STT | faster-whisper `large-v3`, int8 | **cpu** | CTranslate2 has no Metal backend (01-03) |
| LLM | Ollama **`qwen3.5:2b`** (01-04's LATENCY model, not the 9b capability model) | Ollama daemon @ `127.0.0.1:11434` | reached over the REST API; `think=false`, `num_predict=64` to bound the reply |
| TTS | Chatterbox `0.1.7` | **mps** | seed 1234; same gen params as the corpus render; watermark **inside** the timed region (Pitfall 11) |

**Input:** `corpus/clips/c01__en.wav` (reused from 01-05) — "Can you add кефир to the shopping
list before we leave?"

- **STT heard:** `"Can you add kefir to the shopping list before we leave?"` (Whisper
  transliterated кефир → "kefir" — the SPIKE-04 behaviour, D-05).
- **LLM replied:** `"Yes, I'll check your current list and update it with kefir right now."`
- **TTS spoke:** 3.8 s of audio out.

## Per-stage budget

> **D-12 caveat (in the caption, because it directs a purchase):** every number below is an
> **Apple-Silicon** measurement on an 18 GB M-series Mac. The hardware-class recommendation is
> an **INFERENCE from Apple Silicon, explicitly NOT a measured CUDA result.** Iteration 0 is
> the cold trip and is **discarded** from the warm p50/p95.

| Stage | cold (ms) | warm p50 (ms) | warm p95 (ms) | share of warm total |
|---|---:|---:|---:|---:|
| STT (whisper, cpu) | 12 545 | 16 663 | 17 003 | **34.1 %** |
| LLM (qwen3.5:2b) | 813 | 657 | 690 | **1.4 %** |
| **TTS (chatterbox, mps)** | 25 506 | **31 496** | 32 765 | **64.5 %** |
| `unattributed` (residual) | 0.0 | **0.0** | 0.0 | **0.0 %** |
| **TOTAL (wall)** | 38 864 | **49 084** | 50 086 | 100 % |

- **Dominant stage: TTS (~65 %).** STT is the other third; the local LLM is **negligible
  (~1.4 %)** at this reply length. If you want the round trip faster, Chatterbox is the lever.
- **`unattributed` ≈ 0** (residual < 1e-6 s on every iteration). The three stages reconstruct
  the wall clock, so the accounting is honest — a large residual would have meant the budget
  was fiction (`roundtrip.stages_reconstruct_wall` / `residual_is_small` both true).
- Raw warm walls: `40.86 s, 49.08 s, 50.09 s`.

## Integrity of the numbers (Pitfall 10)

- **Ran solo.** No other model-loading plan executed concurrently; the TTFA measurement (also
  in this plan) finished before this trip started. Co-resident Chatterbox + Whisper + Ollama
  sit near the RAM ceiling and swap would make every number fiction.
- **No swap detected**, but there IS upward drift. This process's peak RSS was **3.65 GB**
  (Whisper + Chatterbox + Dicta; the Ollama daemon holds `qwen3.5:2b` in a **separate** ~2.7 GB
  process **not** counted in that figure, and MPS/unified allocations are also not fully
  reflected in RSS — so 3.65 GB is a floor, not the true footprint). The heuristic swap flag
  (`warm p95 > 2× p50`) did **not** trip.
- **But warm is SLOWER than cold here** (cold 38.9 s → warm 40.9, 49.1, 50.1 s), the *opposite*
  of the isolated TTFA where warm beats cold. Both STT and TTS drifted up under **sustained
  co-resident load** — memory-pressure / thermal / MPS-CPU contention on an 18 GB machine. This
  is exactly the variance a buyer needs to see and is **not** averaged away: the tail is real,
  and it is the single strongest argument that 18 GB is the binding constraint (Pitfall 10).

## What this says about the hardware purchase

- **A local round trip on this Mac is ~40–50 s wall**, TTS-dominated, LLM-trivial. That is far
  from conversational; the number exists to size a purchase, not to claim the Mac ships.
- **The Mac is a dev harness (CLAUDE constraint), not the target.** faster-whisper is CPU-only
  here (no Metal); on the Linux target with CUDA the STT and TTS stages would move to GPU — but
  **that is the D-12 inference, unmeasured.** Do not quote 40–50 s as the shipped latency, and
  do not quote a CUDA number we did not measure.
- **Chatterbox is the cost centre and its latency has a large sentence-dependent tail** (see
  `ttfa.md` runaway caveat). Any hardware decision must budget for the tail plus a
  generation-time watchdog, not just the p50.

## Provenance

`spike/voice/roundtrip.py --n-warm 3`, run solo 2026-07-25. Working JSON
(`spike/voice/.roundtrip.json`) is gitignored scratch; this file is the durable record.
