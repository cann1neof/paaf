# Phase 1 — 01-RESULTS.md — the raw measured record

**Status:** RAW record only. No conclusions, no recommendations, no framing (D-09). This file
is committed BEFORE `DECISIONS.md` exists so the evidence stays re-readable without its
interpretation (D-08/D-09). `DECISIONS.md` links back to the sections here; it does not
duplicate them.

**Provenance:** every number below is copied from a durable raw source in
`.planning/phases/01-spike-gate/` — the `raw/*.md` write-ups, the `corpus/*.jsonl` data, and
the prior-plan SUMMARYs. Each section names its source file. Nothing here is inferred.

**Two binding caveats travel with their sections and are repeated verbatim wherever the data is:**

> **D-05 (rides with every SPIKE-04 number):** SPIKE-04 measures Whisper on **synthetic
> Chatterbox speech**, not the user's real code-switched speech (D-04). Chatterbox failures and
> Whisper failures are **not separable** in this setup. No repo text may claim PAAF handles the
> user's real code-switched speech on this evidence (SC#4).

> **D-12 (rides with every latency number):** the TTFA and round-trip numbers are **Apple-Silicon
> measurements** on an M-series Mac. Any hardware-class statement they feed is an **inference from
> Apple Silicon, explicitly NOT a measured CUDA result** (D-11/D-12).

---

## 0. Provisioning baseline — the exact configuration every voice number is a property of

*Source: `raw/voice-provision.md` (voice half), `raw/bakeoff-provision.md` + `raw/bakeoff-results.md` §0 (bake-off half).*

### Machine
- Apple M3 Pro, **18 GB** unified memory, macOS 26.5.2, arm64. Dev harness only; Linux is the ship target (CLAUDE constraint).
- `torch.backends.mps.is_built() == True` and `is_available() == True` — MPS is a real backend on this machine, so the device probe was a real test.

### Voice venv (`spike/voice/.venv`, Python 3.12.13, gitignored, dies with `spike/`)
Resolved exact primary versions (all re-verified against PyPI on 2026-07-23; all were still the latest release, so no pin held back a newer version):

| Package | Resolved | Source |
|---|---|---|
| `chatterbox-tts` | **0.1.7** | voice-provision.md Task 1 |
| `dicta-onnx` | **1.0.9** | voice-provision.md Task 0/1 |
| `faster-whisper` | **1.2.1** | voice-provision.md Task 1 |
| `torch` / `torchaudio` | **2.6.0 / 2.6.0** | voice-provision.md |
| `transformers` | **5.2.0** | voice-provision.md A2 |
| `onnxruntime` | **1.21.1** | voice-provision.md A2 |
| `numpy` | **1.26.4** | voice-provision.md A2 |
| `ctranslate2` | **4.8.1** (arm64 cp312 wheel, CPU-only — no Metal backend) | voice-provision.md |
| `soundfile` | **0.14.0** | voice-provision.md |

Full 121-package freeze is recorded verbatim in `raw/voice-provision.md` §"Full resolved freeze".
A2 (dicta-onnx pins vs chatterbox transformers) and A3 (transformers 5.2.0 + diffusers 0.29.0 at
runtime) both **resolved cleanly with no conflict, first attempt**.

### Model weights fetched (announced, PRIV-06 rehearsal; `HF_TOKEN` never set — all public)
*Source: voice-provision.md §"Announced model downloads".*

| Artifact | Source | Size |
|---|---|---|
| Chatterbox Multilingual V3 checkpoint | HF `ResembleAI/chatterbox` | ~3.0 GB |
| `dicta-1.0.onnx` (fp32 diacritizer) | GitHub `thewh1teagle/dicta-onnx@model-files-v1.0` | 1.22 GB |
| Whisper `large-v3` | HF `Systran/faster-whisper-large-v3` (first-party, not the community turbo) | 3.09 GB |

Chatterbox `SUPPORTED_LANGUAGES` n=23; `{en, ru, he, es}` all present.

### Bake-off venv (`spike/bakeoff/.venv`, Python 3.12.13) + Ollama
*Source: bakeoff-results.md §0.*

- Ollama **0.32.1**, detached `ollama serve`, `127.0.0.1:11434` (loopback only).
- **Ollama model ids in play:**
  - `qwen3.5:9b` — the **capability** model, gated by 01-04 at **30/30 well-formed tool calls**; used for the bake-off (SPIKE-05/06/07).
  - `qwen3.5:2b` — the **latency** model; used for the SPIKE-08 round trip's LLM stage.
- LangChain `1.3.14` · langchain-core `1.5.0` · langchain-ollama `1.1.0` · langchain-mcp-adapters `0.3.0`.
- `pydantic-ai-slim` **2.13.0** (held deliberately by 01-04 so a difficulty could not be ambiguous between "framework is awkward" and "our snippet is stale"). `mcp` **1.28.1** on both sides.

### Fixed generation knobs (voice)
*Source: voice-provision.md, 01-05-SUMMARY, ttfa.md.*

- **seed `1234`**, set immediately before **each** `generate()` call (Pitfall 6).
- gen params: `exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=2.0, min_p=0.05, top_p=1.0`.
- device string `"mps"` for renders; TTFA measured on both `"mps"` and `"cpu"`.

### Seeded synthesis reproducibility (GATE 0 Check 5)
*Source: voice-provision.md §Task 2 Check 5.*

- seed 1234 on `mps`, same sentence rendered twice → **bitwise identical: True**; `allclose(atol=1e-6): True`; `max|diff| = 0.0`; shapes `(1, 269760)` both.
- Consequence recorded: D-07's re-run-and-diff promise holds **on a single backend**. Cross-backend (mps vs cpu) is NOT bitwise reproducible — see §5, the same seed emits different audio lengths per backend.

### Usable inference device (GATE 0 Check 4)
- **`mps`** constructed and generated successfully (60.933 s cold at Gate 0). CPU also later confirmed usable (§5).

---

## 1. SPIKE-01 — corpus render inventory

*Source: `corpus/timings.jsonl` (46 rows), `corpus/mapping.json`, 01-05-SUMMARY.*

46 WAVs rendered, all on `mps`, all seed 1234, all in configuration `repaired`, in 8
leak-isolated subprocesses (Pattern 2, N=6/batch). 24 kHz mono, 194.2 s total, 9.32 MB.

| Condition | Clips | Meaning |
|---|---:|---|
| `matrix` — tagged with the sentence's dominant language | **20** | D-06 |
| `embedded` — tagged with the sentence's embedded language | **20** | D-06 |
| `none` — `language_id=None`, no tag | **6** | untagged controls (`c01,c04,c08,c12,c15,c18`), one per D-02 category, derived from the corpus at runtime |
| **Total** | **46** | |

Tag distribution across the 46: `en` 18, `ru` 9, `he` 7, `es` 6, `none` 6.

**Mechanical facts recorded (NOT quality claims):**
- silent clips (peak < 0.01): **0**; truncated (< 0.5 s): **0**; durations 2.52 s – 10.44 s; sample rate uniform 24000 Hz; device uniform `mps` 46/46.
- The Dicta repair was re-proven live in all 46 rows: `configuration=repaired` 46/46, `native_zero_arg_dicta_works=false` 46/46, `dicta_probe_out=שְׁלוֹם עוֹלָם` 46/46.
- `c08__he.wav` is a duration/synthesis outlier: 10.44 s audio from 63.2 s synthesis (possible runaway; recorded, not investigated — investigation requires listening).
- **41 of 46 clips emitted `forcing EOS token`** from `alignment_stream_analyzer`; **7 emitted `Detected 2x repetition of token N`**. These are the *common* case across all four languages, not a Hebrew-specific signal.
- **All 9 Russian-tagged clips were rendered WITHOUT stress labeling** (`russian_text_stresser not available`), recorded per clip in `timings.jsonl`.

The blind view (`corpus/clips_blind/` + `mapping.json`, seed 20260723) is bijective and
byte-identical to the sources (SHA-256 matched 46/46); zero blind names leak a clip id or tag.
**No clip has been listened to; no audio-quality property is recorded in this section.**

---

## 2. SPIKE-02 — native-ear Hebrew verdict + D-20 ru/es spot-check

### TAKEN 2026-07-25 — verbatim record in `raw/hebrew-verdict.md`.

Plan 01-08 (the blind native-ear Hebrew judgment, D-13/D-14, plus the D-20 Russian/Spanish
spot-check) **was executed.** The human listened to all 46 blind-shuffled clips and typed verbatim
impressions into `raw/hebrew-judgments.json` **before** any tag was visible; tags were joined back
only afterward (`shuffle_blind.py join`) into `raw/hebrew-verdict.md`. Blind judgment preserved
(D-14). The verbatim file governs; the extracts below are exact quotes, not paraphrase.

**Hebrew (7 clips) — verbatim:**
- c02: "very very good one mix of languages"
- c05: "nothing noticable or signifant to notice: either good or ok"
- c08: "I heard hebrew!! then i heard english and then I heard this pissing sounds psh phs phs bullshit"
- c09: "goood hebrew!"
- c10: "nothing noticable or signifant to notice: either good or ok"
- c11: "nothing noticable or signifant to notice: either good or ok"
- c14: "nothing noticable or signifant to notice: either good or ok"

**Reading:** 2 explicitly good, 4 unremarkable-acceptable, 1 partial code-switch breakdown (c08 — Hebrew and English intelligible, embedded stretch degrades to non-word babble). No total Hebrew failure. **Chatterbox Hebrew is usable** — above the LOW-confidence prior. Bounds (D-13): one native listener, blind, ~4 s synthetic sentences, no rating scale, no cloud baseline.

**D-20 ru/es spot-check — two catastrophic clips surfaced (verbatim):**
- c20 (ru): "wtf? bullshit it's not hebrew or anything close..." — catastrophic.
- c03 (es): "looks like hebrew doesn't sound... it's like a shp psh hspsh sounds but not real words" — catastrophic, same babble mode as c08.
- c16 (ru): "sounds like russian + englush, but russian got the very hard english accent... don't choose one accent for everything" — accent bleed, not a breakdown.
- **D-20 caveat:** all 9 Russian clips were rendered without stress labeling (permanent PyPI 404 — §6), so a Russian defect cannot be cleanly attributed to Chatterbox's voice vs the missing stress model.

**Status of dependent conclusions:** SPIKE-01 (intelligibility of code-switched audio) and
SPIKE-02 (Hebrew quality) are now closeable. The Hebrew fallback-ladder rung (D-10) leans "none"
(DECISIONS.md), confirmed in Phase 6.

---

## 3. SPIKE-04 — Whisper on the code-switched corpus

*Source: `raw/transcribe.md`, `corpus/transcripts.jsonl` (138 rows = 46 clips × {ml=False, ml=True, translate}).*

> **D-05 (binding, repeated):** this is Whisper on **synthetic Chatterbox** speech, not the
> user's real speech. Chatterbox and Whisper failures are inseparable here. Carried per-row on
> every `transcripts.jsonl` row as `d05_caveat`.

Instrument: `WhisperModel("large-v3", device="cpu", compute_type="int8")` (first-party Systran,
not community turbo). `language=None` always; `vad_filter=False` explicit; `all_language_probs` +
a separate `detect_language()` posterior captured per clip. Structural caveat: the faster-whisper
`Segment` dataclass carries **no `.language` field**, so "per-segment language" is inferred from
`all_language_probs` + output script, never read from a direct label.

**Measured findings (raw):**

1. **Whisper LOCKS onto exactly one language per clip.** `info.language` is a single language for every clip under both conditions.
2. **`multilingual=True` did NOT unlock it.** `all_language_probs` posterior identical under False vs True on **46/46** clips; full transcript identical on **44/46** (the 2 exceptions trivial — a trimmed hallucinated "Here.", a reshuffled garble; neither recovers the second language).
3. **What moved the detected language was the Chatterbox `language_id` tag, not the Whisper flag** — the tag flipped Whisper's detected language on **9 of 20** sentences (e.g. `c04` en→ru, `c08` en→he, `c16` en→ru). (This is a property of the synthetic input — a concrete instance of D-05.)
4. **The embedded language:** transliterated/garbled into Latin when the matrix is Latin, never preserved in native script — `c02` `סופגניות`→"Sifakonat"; `c14` `רחוב דיזנגוף`→"Rehuv'Dai's engulf"; `c03` `sobremesa`→"Sober Misa"; `c07` Russian mid-clause → "…as when you'll tree raza". **Native script preserved only when Whisper locked to the non-Latin language** — `c04__ru` keeps Cyrillic + "but the attachment never went through"; `c12__ru`, `c18__ru` keep Cyrillic + Latin.
5. **Same-script Russian/English pair (hardest D-02 category) collapses:** `c19` `СОК`/`COK`→"Sock"/"Cock"; `c20` (ru tag) → "OnWebRailPyroid torqued…" — near-total loss.
6. **`task=translate` flattens everything to English** when locked to a non-English language: `c09` he→"Remind me to take the ball at 8.45 tomorrow morning"; `c13` es→"Alejandro said that Dmitry arrives on Tuesday morning". Source languages not preserved.
7. **Untagged (`none`) controls:** 5/6 detect `en` (English-dominant corpus); the one with no English (`c12__none`, ru+es) fell to `fr(0.29)` — low-confidence misdetection.
8. Numbers/units drifted on several clips (`c11` `1.5`→"5", `c15` `500`→"50", `c16` `20`→"8") — but per D-05 as likely a Chatterbox synthesis artifact as a Whisper error; not separable.

**Recorded correction to the prior "STT is a non-issue" claim:** that claim is **not supported**
by this evidence (Whisper locks + transliterates/garbles/translates). What this does NOT establish
— and SC#4 forbids claiming — is behavior on the user's **real** code-switched speech (D-05;
real-voice data deferred to Phase 7).

---

## 4. SPIKE-03 — Chatterbox time-to-first-audio (TTFA)

*Source: `raw/ttfa.md`. Harness: `measure_ttfa.py`, a dedicated single-purpose process (Pitfall 5), cold generate discarded.*

> **D-12 (binding, repeated):** Apple-Silicon measurement; any hardware-class statement is an
> inference, NOT a measured CUDA result.

"TTFA" here = wall-clock of one `generate()` returning — Chatterbox exposes **no streaming /
first-chunk API**, so there is no earlier "first audio" moment. Watermarking (Pitfall 11 /
VOICE-12) is unconditional and **inside the timed region**. Fixed sentence
`"Your meeting starts in ten minutes."`, `language_id="en"` (Dicta/Hebrew path off the timed
region), seed 1234.

| Device | model load (s) | cold generate (s) | cold TOTAL (s) | **warm p50 (s)** | warm p95 (s) | warm min–max (s) | audio (s) | warm RTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **mps** | 11.76 | 9.33 | **21.09** | **6.27** | 6.73 | 5.87–6.73 | 3.88 | ~1.62× |
| **cpu** | 10.08 | 23.52 | **33.60** | **21.70** | 22.75 | 21.27–22.75 | 7.20 | ~3.01× |

- **warm < cold on both devices** (SPIKE-03 integrity check). Raw warm samples — mps: `6.27, 6.06, 5.87, 6.66, 6.73`; cpu: `21.70, 21.27, 22.75`.
- **Cross-backend divergence:** identical sentence + seed produced **3.88 s** audio on mps but **7.20 s** on cpu, so raw TTFA seconds are **not** comparable across devices; the fair metric is RTF (synth seconds per audio second): **mps ≈ 1.6×, cpu ≈ 3.0× → CPU ~1.9× slower per second of speech.**
- **Runaway caveat (recorded verbatim):** the first sentence pick `"Set a timer for ten minutes."` tripped `alignment_stream_analyzer` (`forcing EOS, alignment_repetition=True`) and cost **64–89 s per warm generate on mps** (~10× the well-behaved ~6 s). Chatterbox `generate()` latency is **sentence-dependent with a large tail**; a running assistant needs a generation-time cap/watchdog. (Consistent with `c08__he`'s 63 s synth in §1.)

---

## 5. SPIKE-08 — round-trip latency budget (Walking Skeleton)

*Source: `raw/roundtrip.md`. Harness: `roundtrip.py`, one WAV-in → STT → LLM → TTS → WAV-out trip, run solo, cold trip discarded.*

> **D-12 (binding, repeated):** Apple-Silicon measurement; NOT a measured CUDA result.

Co-resident stack: STT = faster-whisper `large-v3` int8 on **cpu** (no Metal backend); LLM =
Ollama **`qwen3.5:2b`** over the REST API (`think=false`, `num_predict=64`); TTS = Chatterbox
`0.1.7` on **mps**, watermark inside the timed region. Input `corpus/clips/c01__en.wav`
("Can you add кефир to the shopping list before we leave?").
- STT heard: `"Can you add kefir to the shopping list before we leave?"` (кефир → "kefir", the SPIKE-04 transliteration, D-05).
- LLM replied: `"Yes, I'll check your current list and update it with kefir right now."`
- TTS spoke: 3.8 s of audio.

| Stage | cold (ms) | warm p50 (ms) | warm p95 (ms) | share of warm total |
|---|---:|---:|---:|---:|
| STT (whisper, cpu) | 12 545 | 16 663 | 17 003 | **34.1 %** |
| LLM (qwen3.5:2b) | 813 | 657 | 690 | **1.4 %** |
| **TTS (chatterbox, mps)** | 25 506 | **31 496** | 32 765 | **64.5 %** |
| `unattributed` (residual) | 0.0 | 0.0 | 0.0 | **0.0 %** |
| **TOTAL (wall)** | 38 864 | **49 084** | 50 086 | 100 % |

- Dominant stage **TTS ~65 %**; STT ~34 %; local LLM **negligible ~1.4 %**. Raw warm walls: `40.86, 49.08, 50.09 s`.
- `unattributed ≈ 0` (residual < 1e-6 s every iteration) — the three stages reconstruct the wall clock, so the budget is not fiction.
- **Warm is SLOWER than cold here** (cold 38.9 s → warm 40.9, 49.1, 50.1 s), the opposite of the isolated TTFA. Both STT and TTS drifted up under sustained co-resident load. Peak RSS 3.65 GB (a floor — excludes the separate ~2.7 GB Ollama daemon process and MPS/unified allocations). No swap detected (heuristic `p95 > 2× p50` did not trip).

---

## 6. Permanent facts (properties of a default install, not fixable by config)

*Source: voice-provision.md GATE 0 Check 3, ttfa.md, roundtrip.md.*

- **`russian_text_stresser` is absent — permanent PyPI 404.** `ModuleNotFoundError: No module named 'russian_text_stresser'`. Russian is synthesized WITHOUT stress labeling in every measurement in this phase (all 9 Russian corpus clips, and any future D-20 ru spot-check). This is what a user gets from a default install; it is not fixable by pip. Import shape is a submodule: `russian_text_stresser.text_stresser`.
- **Chatterbox watermarking is unconditional (Pitfall 11 / VOICE-12).** `resemble-perth==1.0.1` (PerTh) watermarks every render; there is **no flag to disable it**, and its cost is inside every timed region above.
- **`dicta-onnx` ships no weights and chatterbox cannot supply the path** (upstream defect: zero-arg `Dicta()` raises `TypeError: missing 1 required positional argument: 'model_path'`). The 01-03 repair supplies `dicta-1.0.onnx` (fp32) and is re-proven live in every render subprocess.
- **CTranslate2 (faster-whisper) has no Metal backend** — STT is CPU-only on this Mac. arm64 cp312 wheels do exist (no source build), but they are CPU-only.

---

## 7. SPIKE-05 / SPIKE-06 / SPIKE-07 — agent-framework bake-off

*Source: `raw/bakeoff-results.md`. Method (D-15/D-16): one PAAF-typed port (`spike/bakeoff/port.py`, stdlib-only) implemented twice — over LangChain/LangGraph and over Pydantic AI — across the same five-part surface. Both adapters were completed; nothing abandoned under D-19. Interface signatures do NOT survive (D-18); only these findings carry.*

### SPIKE-05 — do Ollama token counts come back non-`None`?
**YES on both frameworks**, on the streaming path, read after aggregation.

| | LangChain | Pydantic AI |
|---|---|---|
| Usage after aggregation | `{input 13, output 370, total 383}` | `{input 13, output 254, total 267}` |
| `is_populated` | **true** | **true** |
| Usage records populated in the trace | **3/3** | **3/3** |
| Streamed chunks carrying usage | **1 of 334** | **0 of 4** (none exposed per-delta) |
| Naive first-chunk read | `null` | `null` |

- LangChain: **1 populated chunk out of 334** (reproduced 1/261 and 1/334) — a handler reading usage off a chunk has a 99.7% chance of reading `None`. Reading position, not framework capability, decides the answer on the LangChain side.
- Pydantic AI exposes no per-delta usage at all; the count is available only from `result.usage` (a **property**, not a method, in 2.13.0) after the stream closes — zero chances to misread.
- Counts are large (254–370 output tokens for a nine-word greeting) because `qwen3.5` is a thinking model; reasoning is counted in `output_tokens` but never appears in streamed text.

### SPIKE-06 — are MCP tool args AND structured results visible through callbacks?
**YES on both frameworks, with zero cloud.**

| | LangChain | Pydantic AI |
|---|---|---|
| Tool **args** seen | `{"room": "kitchen"}` | `{"room": "kitchen"}` |
| Tool **result** type at the hook | `ToolMessage` | `builtins.dict` |
| Structured payload | inside `.artifact['structured_content']` | **is the result** — no wrapper |
| Matches server's frozen fixture | **true** | **true** |

- Assertion carrying the requirement: `structured_content_matches(result, EXPECTED_STRUCTURED)` — byte-for-byte against what the server is known to have sent (three negative controls: changed-value, dropped-field, stringified-list).
- LangChain Pitfall 9 confirmed exactly: `str(output)` on the same live `ToolMessage` returns `structured_content: null`, `artifact_present: false` — the difference between "visible" and "invisible" is one `str()` call.
- LangChain trap: `on_llm_start` fired **zero** times; every prompt arrived via `on_chat_model_start`. A handler implementing only `on_llm_start` (the common tutorial hook) would have recorded nothing.
- Pydantic AI has no analogue of either trap (one `before_model_request`; structured content arrives unwrapped).

### SPIKE-07 — which is easier to hide behind a port?
**No decisive winner — and the raw comparison numbers are:**

| Measure | LangChain | Pydantic AI | Edge |
|---|---:|---:|---|
| Port implementation (code lines, excl. probe) | **245** | **228** | Pydantic AI +7% (noise) |
| Private translation code | **61** | **61** | exact tie |
| Framework symbols imported | **4** | **7** | LangChain |
| Framework types in a public port signature | **0** | **0** | tie (test-enforced) |
| Chances to misread usage | **334** | **0** | Pydantic AI |
| Model load from a named profile | 1 call, `base_url` optional | 2 objects, `base_url` mandatory + `/v1` | LangChain |
| Ollama transport | first-party `langchain-ollama` | OpenAI SDK compatibility shim | LangChain |
| Truncated-answer behaviour | silent | raises and names the cause | Pydantic AI |
| Trap density (dual hooks / chunk usage / artifact) | present | absent by design | Pydantic AI |

- **D-19 named difficulty:** hiding the **model-loading** half was clearly easier with LangChain; hiding the **tracing** half was clearly easier with Pydantic AI. Neither advantage carries the decision alone.
- **The CLAUDE.md falsifier fired NEGATIVE:** CLAUDE.md said "if MCP traces are opaque → switch to Pydantic AI." LangChain's MCP traces are **not opaque** (args parsed dict + full structured artifact, fixture-verified). The stated reason to switch does not exist.
- **D-19 attribution note (raw):** every difficulty recorded against Pydantic AI was API friction from an unfamiliar v2 surface or a provisioning gap (missing `openai` extra, mandatory `/v1` base URL, `usage` as property, `_on_event` registry key) — **none was "the framework resists porting."** It was hidden behind the same port in 7% fewer lines and the identical translation code.
- **Recorded confidence:** MEDIUM. The two `0.x` packages inside the LangChain 1.x tree (`langchain-mcp-adapters` 0.3.0, `langchain-protocol` 0.0.18) remain the strongest open argument against — and `langchain-mcp-adapters` is the package that made SPIKE-06 pass.
- **Release cadence (01-04 measurement):** `pydantic-ai-slim` shipped 7 minors in 9 days; `langchain` shipped 8 patches in 43 days, still `1.3.x`.

### Privacy (asserted at runtime, PRIV-02 / T-01-06-TEL)
`{"langsmith_tracing_enabled": false}` (LangChain); `{"instrumentation_enabled": false, "capabilities_attached": ["Hooks"]}` (Pydantic AI). Only network traffic in either run: `127.0.0.1:11434`. Only subprocess: the local MCP server. Both frameworks support full in-process observability with **zero cloud**.

### D-19 — what was NOT built (so nothing is rejected on absence of evidence)
LangGraph `interrupt()` → `confirm` tier; ordered fallback chains; multi-turn history / retries / structured output / streaming tool calls; `pydantic-ai-slim` 2.16.0 (2.13.0 held); the `wrap_*`/`Instrumentation` hook family; MCP-protocol callbacks; any third-party MCP server. All deferred to Phase 3 / later plans.

---

## 8. Requirement evidence map (what this raw record supports)

| Requirement | Evidence in this file | Backed by real measurement? |
|---|---|---|
| SPIKE-01 (code-switching handled?) | §1 render inventory + §3 Whisper read + §2 native-ear | **Yes** — works often; embedded-segment babble is the breakdown mode (c08/c03). |
| SPIKE-02 (Hebrew quality verbatim) | §2 | **Yes** — verdict taken 2026-07-25, usable. |
| SPIKE-03 (TTFA mps+cpu) | §4 | Yes. |
| SPIKE-04 (Whisper lock/transliterate/translate) | §3 | Yes (with D-05). |
| SPIKE-05 (Ollama token counts non-None) | §7 | Yes. |
| SPIKE-06 (MCP args + results via callbacks) | §7 | Yes. |
| SPIKE-07 (which easier to hide behind a port) | §7 | Yes (verdict: no decisive winner). |
| SPIKE-08 (round-trip per-stage budget) | §5 | Yes. |
| SPIKE-09 (record measured reality) | this file + DECISIONS.md | Yes (this file is the raw half). |

---

*Raw record assembled 2026-07-25 for plan 01-10. Committed before `DECISIONS.md` per D-09.*
