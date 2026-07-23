# Phase 1: Spike Gate - Research

**Researched:** 2026-07-20
**Domain:** Multilingual TTS/STT measurement on Apple Silicon; agent-framework port bake-off
**Confidence:** HIGH on API surface and stack facts (read from published package source); LOW on the quality outcomes the phase exists to measure (by design)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Test Corpus (SPIKE-01, 02, 03, 04, 08)**
- **D-01:** One shared text corpus of ~20 mixed-script en/ru/he/es sentences serves SPIKE-01, 02, 04 and 08. It is the phase's single measuring instrument.
- **D-02:** Corpus is built as a **deliberate failure grid**, not transcribed real speech. It must systematically cover: single foreign noun in an English frame; mid-clause switch; Hebrew RTL adjacent to Latin digits; proper nouns; numbers/units; and a same-script Russian/English pair.
- **D-03:** The grid must **vary which language is the matrix across sentences**, so all four languages are exercised in both matrix and embedded roles corpus-wide. This is an explicit grid constraint, not an accident of authoring.
- **D-04:** Whisper (SPIKE-04) is fed **Chatterbox TTS output**, not user-recorded speech. User asked whether the model needed fitting — confirmed there is no training or fine-tuning anywhere in this project (PROJECT.md: "we consume open models, we don't make them"); audio is test input only.
- **D-05:** ⚠️ **Binding caveat on D-04.** SPIKE-04 therefore measures *"Whisper on synthetic mixed speech,"* not "Whisper on the user's speech." Under SC#4, no repo text — README included — may claim PAAF handles the user's real code-switched speech on this evidence. Chatterbox failures and Whisper failures are not separable in this setup. This caveat must travel with the SPIKE-04 result into `DECISIONS.md`.
- **D-06:** `language_id` is varied **matrix-plus-embedded**: each sentence rendered twice (once tagged with its dominant language, once with its embedded language), ~40 clips total. Known blind spot: the two untested tags per sentence, partly mitigated by D-03.
- **D-07:** Corpus persists as a **committed text fixture plus the generated WAVs and transcripts**. Declared data, not code — this satisfies SC#5 while letting Phase 7 SC#1 mechanically re-run and diff. Sizing is ~3–5 MB; git-lfs is unnecessary.

**Evidence Handling & Judgment (SPIKE-09)**
- **D-08:** **No pre-registered pass/fail thresholds.** Measure first, judge after, with full information. Motivated-reasoning risk was raised and consciously accepted.
- **D-09:** **Raw record is split from interpretation.** Raw output — transcripts, timings, per-clip notes, verbatim reactions — lands in a results file committed before any conclusion is written. `DECISIONS.md` interprets and links back to it. This is what gives D-08 its teeth: evidence stays re-readable without the framing.
- **D-10:** ⚠️ **Phase 1 does NOT select a Hebrew fallback-ladder rung.** It exits with data only. **Obligation created:** Phase 6 planning cannot begin without selecting rung A, B, C, or "none" from Phase 1's data. Phase 6 designs the voice ports including the per-language *engine* override escape hatch, making it the last responsible moment. Without this, Phase 7 SC#2 inherits an unmade decision. (Rung D — per-language voice switching — remains permanently rejected per PROJECT.md.)
- **D-11:** SPIKE-03 measures **Mac MPS and Mac CPU only**. No cloud GPU is rented.
- **D-12:** ⚠️ **Binding caveat on D-11.** The hardware-class recommendation must be recorded as an **inference from Apple Silicon measurements**, explicitly not a measured CUDA result. Required by SC#4, and material because this recommendation directs an actual hardware purchase.

**Hebrew Quality Judgment (SPIKE-02)**
- **D-13:** **Verbatim impressions only** — no rating scale, no cloud-TTS baseline comparison. Matches SC#1's literal wording. Known cost: impressions are hard to compare against anything in Phase 7.
- **D-14:** Impressions are captured **per clip, blind to `language_id`**. Clips are shuffled and unlabeled; tags are joined back afterward from a filename mapping. Requires a small shuffle/mapping script. This removes tag expectation from the judgment SPIKE-01 exists to make.

**Framework Bake-Off (SPIKE-05, 06, 07)**
- **D-15:** The artifact is **one PAAF-typed port interface, implemented twice** — once over LangChain/LangGraph, once over Pydantic AI. This is what makes "easier to hide behind a port" measurable, and it rehearses the shape Phase 3 builds for real.
- **D-16:** The port covers **model loading from a named profile, streaming tokens, one tool-call round trip, callback-driven tracing, and an MCP server**. Consequently **SPIKE-05 (Ollama token counts non-`None`) and SPIKE-06 (MCP tool args/results visible through callbacks) run *through* the port, not beside it.** Plan this as ONE artifact — do not build the trace/MCP probes separately.
- **D-17:** Comparison evidence is concrete: adapter line count, how many framework types leak toward the boundary, and what each framework fights you on.
- **D-18:** **Findings only carry forward — the port interface does not.** Neither the code nor the interface signatures survive; Phase 3 designs its port fresh, informed by the findings. Strictest reading of SC#5. Accepted cost: Phase 3 redoes design work.
- **D-19:** Stopping rule is **stop at first clear verdict**, even with the second adapter incomplete. **Guard:** the verdict must name what specifically was easier, and record which parts of the unfinished adapter were never built — otherwise the rejected framework is rejected partly on absence of evidence.

### Claude's Discretion

- **D-20:** Listening-pass language coverage — user answered "i don't care." **Call made: Hebrew judged deeply, Russian and Spanish spot-checked.** Rationale: the audio is already rendered so marginal cost is listening time; it matches the lean pattern chosen throughout this discussion; and it closes an SC#4 gap, since the README will claim four languages while SPIKE-02 as written scopes quality judgment to Hebrew alone. A catastrophic Russian or Spanish problem should not stay hidden until Phase 7. Planner may adjust depth, but must not drop ru/es entirely without recording the resulting claim restriction.

### Deferred Ideas (OUT OF SCOPE)

- **Record own voice for a real-speech STT evaluation.** User will research this later. Natural home is Phase 7.
- **Cloud-GPU / CUDA latency measurement before the hardware purchase.** Declined for Phase 1 (D-11).
- **Cloud-TTS Hebrew baseline comparison.** Declined as a judgment method (D-13); becomes relevant if Phase 6 picks rung A.
- **Pre-registered thresholds for later measurement phases.** Rejected here (D-08); worth reconsidering at Phase 12.

**Gray areas left to the planner's judgment:**
- Where throwaway spike code physically lives so SC#5 is enforceable by inspection
- Spike run order, and whether a catastrophic red-spike result should halt remaining spikes
- How SPIKE-08's per-stage latency budget is structured and reported
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SPIKE-01 | Chatterbox intra-sentence code-switching, ≥20 mixed sentences, varying `language_id` | Exact `generate(text, language_id, ...)` signature verified from wheel source; **tokenizer mechanism found that structurally explains the expected failure** (§Pitfall 2). All 4 language codes confirmed present. |
| SPIKE-02 | Hebrew quality judged by native ear, recorded verbatim | ⚠️ **`dicta-onnx` is an undeclared optional dep; without it Hebrew silently degrades to unvocalized text and the spike measures a broken config** (§Pitfall 1). Blind-shuffle harness per D-14 needs a seed (§Pitfall 5). |
| SPIKE-03 | Chatterbox time-to-first-audio, Mac MPS + CPU | **No streaming API exists** — TTFA for one short sentence == full synthesis time, which is the correct proxy given SESS-02 (§Pitfall 3). ⚠️ MPS is documented-unreliable; "MPS unusable" is a legitimate recorded outcome (§Pitfall 4). |
| SPIKE-04 | Whisper accuracy on same sentences; does it lock to one language / transliterate / translate? | **`faster-whisper` has an explicit `multilingual=True` flag ("perform language detection on every segment") — this is the instrument for the lock-on question** (§Pitfall 7). `TranscriptionInfo.all_language_probs` + `detect_language()` give the evidence. `Segment` carries no language field — a real limitation. |
| SPIKE-05 | Ollama token counts non-`None` through LangChain callbacks | **Largely pre-answered from source:** `langchain-ollama` 1.1.0 maps `prompt_eval_count`/`eval_count` → `usage_metadata`. The "None" folklore is a *streaming aggregation* artifact (§Pitfall 8). Ollama is NOT installed (§Environment). |
| SPIKE-06 | MCP tool args/results through `langchain-mcp-adapters` callbacks | MCP tools become plain `StructuredTool` with `response_format="content_and_artifact"` → standard `on_tool_start/end` fire, but **structured content lands in `artifact`, not `output`** (§Pitfall 9). `langchain_mcp_adapters.callbacks` is a *different* thing (MCP protocol callbacks) — do not confuse. |
| SPIKE-07 | Bake-off: which is easier to hide behind a port | Both APIs verified from published wheels. **Pydantic AI v2.13.0 API is confirmed different from all pre-v2 documentation** — `capabilities=`, `MCPToolset`, FastMCP transports (§Standard Stack, §Code Examples). |
| SPIKE-08 | WAV-in → WAV-out round trip, per-stage budget | Per-stage attribution design in §Pitfall 10. 18 GB RAM is the binding constraint when Chatterbox + Whisper + Ollama are co-resident (§Environment). |
| SPIKE-09 | Record measured reality in `DECISIONS.md`; constrain public claims | D-05 and D-12 caveats must travel with results. §Pitfall 6 (nondeterminism) affects what "measured" can mean for Phase 7 SC#1. |
</phase_requirements>

---

## Summary

This phase's technical risk is **not** that the measurements will be hard to take. It is that **three separate silent-degradation paths will cause the spike to measure a broken configuration and record a false negative** against engines that were never given a fair run. All three were found by reading the published `chatterbox-tts` 0.1.7 wheel source directly, and one is independently corroborated by third-party testing.

The most important is Hebrew. `ChatterboxMultilingualTTS` routes Hebrew text through `add_hebrew_diacritics()`, which imports `dicta_onnx` — **a package that is not among chatterbox-tts's declared dependencies**. When absent, the function logs a `warning` and returns the text unchanged. Hebrew is normally written without niqqud, so the model then receives consonant-only text with no vowel information. Independent testing of Chatterbox Multilingual reports exactly this outcome: output "unintelligible without nekudot" when the Dicta ONNX model failed to load. **SPIKE-02 — the native-ear Hebrew verdict that SC#1 makes load-bearing — would record "Chatterbox Hebrew is unusable" while actually measuring a missing pip install.** The same pattern applies to Russian via `russian_text_stresser`, which is worse: that package **does not exist on PyPI at all**, so Russian stress labeling is permanently unavailable to any pip-based install and will always silently skip.

The second finding reframes SPIKE-03. `generate()` is fully blocking and returns a complete waveform; there is **no streaming or chunked API anywhere in the package**. "Time-to-first-audio" is therefore not measurable as a stream event — but this is fine, because the project's own architecture (SESS-02, sentence-chunked TTS) makes TTFA equal to *full synthesis time of the first sentence*. SPIKE-03's wording ("one short sentence") already matches. Separately, MPS on Chatterbox is documented-unreliable (`Placeholder storage has not been allocated on MPS device!`, float64 unsupported on MPS, plus a reported 222–800 MB-per-few-generations memory leak on Apple Silicon). The plan must treat "MPS does not work" as a **valid recorded measurement**, not a blocker, and must batch the ~40-clip corpus render across subprocesses so the leak cannot corrupt timing.

The third area is the framework bake-off, where the user asked for maximum rigor. Both APIs were read from their published wheels rather than docs. **Pydantic AI 2.13.0 confirms the v2 break**: `MCPServerStdio`/`MCPServerSSE`/`MCPServerStreamableHTTP` are gone, replaced by a single `MCPToolset` built on **FastMCP**, and `Agent()` now takes `capabilities=[...]` and `toolsets=[...]`. Any pre-v2 snippet will fail on first run. On the LangChain side two spike-specific gotchas surfaced: `on_chat_model_start` — not `on_llm_start` — is what fires for chat models (a handler implementing only the latter records nothing), and MCP tool *structured* results arrive in the `artifact` half of a `content_and_artifact` tuple rather than in the tool output string. SPIKE-05 is largely pre-answered by source: `langchain-ollama` 1.1.0 does populate `usage_metadata`; the well-known `None` is a streaming artifact visible on intermediate chunks only.

**Primary recommendation:** Make the plan's first task an **engine-readiness gate** that installs `dicta-onnx`, asserts no `dicta_onnx not available` warning fires, and renders one Hebrew probe clip — before any corpus is generated or any ear judgment is made. Then render the corpus in leak-isolated subprocess batches with a fixed torch seed, treating MPS failure as data. Build the bake-off as one PAAF-typed port (D-15/D-16) using `faster-whisper` (not mlx-whisper) for SPIKE-04, because only faster-whisper exposes the per-segment language detection that the "does it lock onto one language" question requires.

---

## Architectural Responsibility Map

Phase 1 builds no product architecture (CONTEXT.md: "This phase decides nothing about architecture"). The map below assigns *measurement* responsibilities so the planner can see which tier each spike exercises and where a failure is attributable.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Corpus authoring (D-01..D-03) | Declared data fixture | — | Committed text; no runtime tier. Survives phase per D-07. |
| TTS synthesis + language tagging (SPIKE-01/02/03) | Local model process (torch/MPS/CPU) | HF Hub (one-time 3.2 GB download) | All inference in-process; only the model fetch touches network. |
| Hebrew/Russian text normalization | Local model process (optional deps) | — | ⚠️ Silently skipped when deps absent — the phase's top risk. Owned by `chatterbox.models.tokenizers`, not by our code. |
| STT transcription + language ID (SPIKE-04) | Local model process (CTranslate2, CPU-only on Mac) | HF Hub (model fetch) | No Metal backend; CPU is acceptable for ~40 short clips. |
| Blind judgment harness (D-14) | Local script + human ear | — | Shuffle/mapping is code; the verdict is a human artifact recorded verbatim. |
| Model loading from named profile (D-16) | PAAF-typed port | Framework adapter | The port is the unit under test; the adapter is the thing being judged. |
| Token streaming (D-16) | PAAF-typed port | Framework adapter | Streaming shape is where framework types leak hardest (D-17). |
| Tool-call round trip + MCP (D-16, SPIKE-06) | PAAF-typed port | Framework adapter → MCP server subprocess | MCP server is an external process; keep it dependency-light. |
| Trace capture (SPIKE-05/06) | Framework callback/hook layer | PAAF trace dataclass | The *point* of the bake-off: how much fidelity survives the port boundary. |
| Local LLM serving | Ollama daemon (**not installed**) | — | External service; see §Environment Availability. |
| Latency attribution (SPIKE-08) | Measurement harness | All three engines | Single machine; per-stage wall-clock with explicit warmup separation. |

---

## Project Constraints (from CLAUDE.md)

Directives extracted from `.claude/CLAUDE.md`. These carry the same authority as locked CONTEXT.md decisions.

| Constraint | Source | Bearing on Phase 1 |
|------------|--------|--------------------|
| **GSD Workflow Enforcement** — no direct repo edits outside a GSD workflow | §GSD Workflow Enforcement | Phase 1 work proceeds under `/gsd-execute-phase`. |
| **Python 3.12 pinned** — "3.13 still has wheel-availability risk across the torch/audio-ML chain" | §Recommended Stack | ✅ Verified compatible: `torch-2.6.0-cp312-none-macosx_11_0_arm64.whl` exists. Do **not** use 3.13 (chatterbox's numpy constraint flips at 3.13). |
| **`uv` for package/venv management**, `hatchling` build backend | §Development Tools | uv is **not installed** — see §Environment. Phase 1 needs the venv, not the build backend. |
| **Public API must never leak the agent framework's types** | §Constraints | This is the *criterion* SPIKE-07 measures (D-15/D-17). |
| **All LangChain imports confined to a single `paaf/_engine/` package** | §Decision 1 | Phase 1 is throwaway and pre-Phase-2; it must **not** anticipate that structure (CONTEXT.md code_context). Quarantine spike code instead. |
| **Privacy: no accounts, no telemetry, no mandatory cloud** | §Constraints | ⚠️ Pydantic AI's `Instrumentation` capability is OTel-based — **do not enable Logfire**. LangChain: ensure `LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` are unset. |
| **`sounddevice`, not PyAudio** | §Supporting Libraries | Phase 1 is WAV-file-in/WAV-file-out (D-04, SPIKE-08) — **no live audio I/O needed at all**. Use `soundfile`; skip `sounddevice`. |
| **Chatterbox PerTh watermarking is a known property to document** | §Sources, VOICE-12 | Confirmed unconditional in source (§Pitfall 11). Phase 1 should record it; VOICE-12 documents it. |
| **Model selection criterion is TOOL-CALLING QUALITY, not chat quality** | §Decision 6 | Directly governs the Ollama model chosen for SPIKE-05/06/07. |
| **Re-check the Ollama default model at implementation time — do not take the roadmap's word or mine** | §Decision 6 | Explicit instruction; carried into §Open Questions. |
| **Nothing load-bearing on any single engine's internals** | §Decision 4 lesson | Reinforces D-18: findings carry, code does not. |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `chatterbox-tts` | **0.1.7** (2026-03-26) | TTS under test (SPIKE-01/02/03) | Only open multilingual TTS covering en+ru+he+es in one model. MIT. `[VERIFIED: PyPI JSON API 2026-07-20]` |
| `dicta-onnx` | **1.0.9** (2025-05-31) | ⚠️ **Hebrew diacritization — undeclared dep of chatterbox** | Without it SPIKE-02 measures a broken config. Requires Python ≥3.11. `[VERIFIED: PyPI + chatterbox source import path]` |
| `faster-whisper` | **1.2.1** (2025-10-31) | STT under test (SPIKE-04) | Only engine exposing `multilingual=True` per-segment language detection — the SPIKE-04 instrument. MIT. `[VERIFIED: wheel source]` |
| `torch` | **2.6.0** (hard pin by chatterbox) | Inference runtime | `==2.6.0` pinned for py<3.14. cp312 arm64 wheel confirmed. `[VERIFIED: PyPI]` |
| `torchaudio` | **2.6.0** (hard pin) | Audio tensor I/O | cp312 arm64 wheel confirmed. `[VERIFIED: PyPI]` |
| `langchain` + `langgraph` | **1.3.14** (2026-07-16) / **1.2.9** (2026-07-10) | Bake-off side A | ⚠️ langchain drifted 1.3.13 → **1.3.14** since CLAUDE.md. `[VERIFIED: PyPI]` |
| `langchain-core` | **1.4.9** | Callback base classes | Source of the `on_chat_model_start` finding. `[VERIFIED: wheel source]` |
| `langchain-ollama` | **1.1.0** (2026-04-07) | Ollama provider | Maps `prompt_eval_count`/`eval_count` → `usage_metadata`. `[VERIFIED: wheel source]` |
| `langchain-mcp-adapters` | **0.3.0** (2026-06-10) | MCP for side A | Still 0.x — the falsification target of SPIKE-06. `[VERIFIED: PyPI + wheel source]` |
| `pydantic-ai-slim[mcp]` | **2.13.0** (2026-07-18) | Bake-off side B | ⚠️ **v2 API — all pre-v2 snippets are wrong.** Pulls `fastmcp-slim[client]>=3.3.0`. `[VERIFIED: wheel source]` |
| `soundfile` | **0.14.0** | WAV read/write | No live audio needed in Phase 1. `[VERIFIED: PyPI]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mlx-whisper` | 0.4.3 | Metal-accelerated STT | **Only** if faster-whisper CPU proves too slow for SPIKE-08's LLM+STT+TTS round trip. Lacks per-segment language detection → not suitable for SPIKE-04. `[VERIFIED: wheel source]` |
| `ollama` (py client) | 0.6.2 | Direct Ollama probe | Useful to confirm raw `prompt_eval_count` before blaming the framework (§Pitfall 8). |
| `ctranslate2` | 4.8.1 | faster-whisper backend | ✅ **Ships macOS arm64 cp312 wheels** — corrects an implication in CLAUDE.md (§State of the Art). `[VERIFIED: PyPI]` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `faster-whisper` for SPIKE-04 | `mlx-whisper` | Faster on Metal, but exposes **no `multilingual` per-segment flag** — cannot answer "does it lock onto one language" cleanly. Use faster-whisper for SPIKE-04; consider mlx-whisper only for SPIKE-08 latency. |
| `faster-whisper` model `large-v3-turbo` | `large-v3` | Turbo resolves to `mobiuslabsgmbh/faster-whisper-large-v3-turbo` (community, not Systran). `large-v3` → `Systran/faster-whisper-large-v3` (first-party). For a *measurement* phase, prefer `large-v3` to avoid attributing a community conversion's flaws to Whisper. `[VERIFIED: faster_whisper/utils.py _MODELS]` |
| Full `pydantic-ai` | `pydantic-ai-slim[mcp]` | `-slim` avoids pulling every provider SDK. Same version, same API. |
| A hand-written MCP server | An off-the-shelf stdio MCP server | Node 24 + npx are present; a trivial local stdio server is the cheapest dependency-light target for both adapters. |

**Installation** (Python 3.12 venv; note the ordering constraint):

```bash
uv venv --python 3.12 && source .venv/bin/activate
# TTS + the two undeclared language deps
uv pip install chatterbox-tts==0.1.7 dicta-onnx==1.0.9
# STT
uv pip install faster-whisper==1.2.1 soundfile
# Bake-off side A
uv pip install "langchain==1.3.14" "langgraph==1.2.9" "langchain-ollama==1.1.0" "langchain-mcp-adapters==0.3.0"
# Bake-off side B
uv pip install "pydantic-ai-slim[mcp]==2.13.0"
```

⚠️ **Install the bake-off frameworks in a SEPARATE venv from Chatterbox.** `chatterbox-tts` hard-pins `torch==2.6.0`, `transformers==5.2.0`, `diffusers==0.29.0`, `numpy<2.0.0`, `safetensors==0.5.3` and `gradio==6.8.0`; `dicta-onnx` hard-pins `onnxruntime==1.21.1` and needs `tokenizers>=0.21.1`. Resolving all of that against the LangChain/Pydantic-AI trees in one environment is a resolver fight with no upside — the two halves of this phase never import each other. `[VERIFIED: PyPI requires_dist for each]`

---

## Package Legitimacy Audit

Run via `gsd-tools query package-legitimacy check --ecosystem pypi ...` on 2026-07-20.

| Package | Registry | Latest release | Source Repo | Verdict | Disposition |
|---------|----------|----------------|-------------|---------|-------------|
| `chatterbox-tts` | PyPI | 2026-03-26 | github.com/resemble-ai/chatterbox | SUS* | Approved |
| `faster-whisper` | PyPI | 2025-10-31 | github.com/SYSTRAN/faster-whisper | SUS* | Approved |
| `mlx-whisper` | PyPI | 2025-08-29 | github.com/ml-explore/mlx-examples | SUS* | Approved |
| `dicta-onnx` | PyPI | 2025-05-31 | github.com/thewh1teagle/dicta-onnx | SUS* | Approved — see note |
| `langchain` | PyPI | 2026-07-16 | github.com/langchain-ai/langchain | SUS* | Approved |
| `langgraph` | PyPI | 2026-07-10 | github.com/langchain-ai/langgraph | SUS* | Approved |
| `langchain-ollama` | PyPI | 2026-04-07 | github.com/langchain-ai/langchain | SUS* | Approved |
| `langchain-mcp-adapters` | PyPI | 2026-06-10 | *(no repo in metadata)* | SUS* | Approved — repo is `langchain-ai/langchain-mcp-adapters`; metadata omits it |
| `pydantic-ai-slim` | PyPI | 2026-07-18 | github.com/pydantic/pydantic-ai | SUS* | Approved |
| `ollama` | PyPI | 2026-04-29 | *(no repo in metadata)* | SUS* | Approved — official client, `ollama/ollama-python` |
| `soundfile` | PyPI | 2026-06-06 | github.com/bastibe/python-soundfile | SUS* | Approved |

**\* On the uniform SUS verdict — read this before acting on it.** Every package returned `SUS`, and in all 11 cases the reason set is dominated by `unknown-downloads`. That signal is a **limitation of the PyPI JSON API, which does not expose download counts**, not a property of these packages. Three additionally returned `too-new` (`langchain`, `langgraph`, `pydantic-ai-slim`) because their *most recent release* is days old — the projects themselves are years old. Two returned `no-repository` because their PyPI metadata omits a repo URL, though both have well-known public repos. **No package returned `SLOP`; none is missing from the registry; none has a suspicious install script** (PyPI packages have no npm-style `postinstall`). Treating this uniform SUS as a real risk signal would gate every install in the phase behind a human checkpoint for no information gain.

**Packages removed due to [SLOP] verdict:** none.
**Packages genuinely warranting a checkpoint:** `dicta-onnx` — the one package here that is *not* named in the project's prior research, is maintained by an individual (`thewh1teagle`), and was discovered during this research session. It is nonetheless the exact import path hard-coded in `chatterbox/models/tokenizers/tokenizer.py:123` (`from dicta_onnx import Dicta`), which is strong corroboration that it is the intended package. **Recommend one `checkpoint:human-verify` before installing `dicta-onnx`**, and no others.

---

## Architecture Patterns

### System Architecture Diagram

```
                        ┌───────────────────────────────┐
                        │  corpus.jsonl  (D-01..D-03)   │
                        │  ~20 sentences, failure grid  │
                        │  committed text fixture       │
                        └───────────────┬───────────────┘
                                        │ id, text, matrix_lang, embedded_lang
                                        ▼
      ┌─────────────────────────────────────────────────────────────┐
      │ GATE 0 — ENGINE READINESS  (must pass before anything else) │
      │  • assert dicta_onnx imports and Dicta() constructs         │
      │  • render 1 Hebrew probe; assert NO "not available" warning │
      │  • record russian_text_stresser ABSENT (permanent, PyPI 404)│
      │  • probe device: mps usable? → else record + fall to cpu    │
      └──────────────────────────┬──────────────────────────────────┘
                                 │ device ∈ {mps, cpu}, deps verified
                                 ▼
   ┌────────────────────────────────────────────────────────────────┐
   │ RENDER  (SPIKE-01) — subprocess batch, N clips per process     │
   │  for each sentence × {matrix_tag, embedded_tag}   (D-06)       │
   │    torch.manual_seed(FIXED)          ← reproducibility         │
   │    t0; wav = tts.generate(text, language_id=tag); t1           │
   │    write clips/{id}__{tag}.wav ; append timing row             │
   │  ── subprocess boundary contains the MPS memory leak ──        │
   └───────────┬──────────────────────────────┬─────────────────────┘
               │ ~40 WAVs + timings           │ timings only
               │                              ▼
               │                  ┌──────────────────────────┐
               │                  │ SPIKE-03  TTFA           │
               │                  │  mps run  vs  cpu run    │
               │                  │  warm only (drop run #1) │
               │                  └───────────┬──────────────┘
               ├──────────────────┐           │
               ▼                  ▼           │
   ┌────────────────────┐  ┌──────────────────────────────┐
   │ SPIKE-02/D-14      │  │ SPIKE-04  faster-whisper     │
   │ shuffle → opaque   │  │  transcribe(multilingual=T)  │
   │ names, blind ear   │  │  + detect_language()         │
   │ he deep, ru/es spot│  │  → text, lang, probs/segment │
   │ (D-20)             │  └───────────┬──────────────────┘
   │ verbatim notes     │              │
   └─────────┬──────────┘              │
             │  join tags back via mapping.json (after judging)
             └──────────────┬──────────┘
                            ▼
              ┌───────────────────────────────┐
              │ RESULTS.md  (raw, D-09)       │  ← committed FIRST
              │ transcripts, timings, notes   │
              └───────────────┬───────────────┘
                              │ interpreted, never inlined
                              ▼
              ┌───────────────────────────────┐
              │ DECISIONS.md  (SPIKE-09)      │
              │ + D-05 caveat  + D-12 caveat  │
              │ constrains every later claim  │
              └───────────────────────────────┘

  ═══════════ INDEPENDENT TRACK (separate venv) ═══════════

     PAAF-typed port  (D-15)          ┌──────────────────────┐
     load_profile / stream /          │ Ollama daemon        │
     call_tool / trace / mcp    ──────│ (NOT INSTALLED yet)  │
              │                       └──────────────────────┘
      ┌───────┴────────┐                        │
      ▼                ▼                        │
 ┌──────────┐   ┌──────────────┐                │
 │ adapter  │   │ adapter      │                │
 │ LangChain│   │ Pydantic AI  │◄───────────────┘
 │ +LangGraph│  │ v2.13        │
 └────┬─────┘   └──────┬───────┘
      │ AsyncCallback  │ Hooks() capability
      │ Handler        │
      └───────┬────────┘
              ▼                        ┌─────────────────────┐
      trace records ──────────────────►│ stdio MCP server    │
      SPIKE-05 tokens non-None?        │ (npx, dependency-   │
      SPIKE-06 MCP args+results?       │  light test target) │
              │                        └─────────────────────┘
              ▼
      SPIKE-07 verdict (D-17: LOC, leaked types, friction)
      + D-19 guard: name what was NOT built
```

### Recommended Project Structure

SC#5 says no Phase 1 code survives. CONTEXT.md leaves the location to the planner and asks that SC#5 be **enforceable by inspection**. Quarantine everything under one top-level directory whose name states its own disposability, and split code from the data that *does* survive (D-07):

```
spike/                          # ← deleted wholesale at end of Phase 1; SC#5 checkable with one `ls`
├── README.md                   # "Throwaway. Nothing here ships. Deleted after Phase 1."
├── voice/
│   ├── gate_readiness.py       # GATE 0 — dicta_onnx + device probe
│   ├── render_corpus.py        # SPIKE-01 render, subprocess-batched
│   ├── measure_ttfa.py         # SPIKE-03 mps vs cpu
│   ├── transcribe.py           # SPIKE-04 faster-whisper
│   ├── shuffle_blind.py        # D-14 blind harness
│   └── roundtrip.py            # SPIKE-08 per-stage budget
└── bakeoff/
    ├── port.py                 # the PAAF-typed port (D-15) — signatures do NOT survive (D-18)
    ├── adapter_langchain.py
    ├── adapter_pydantic_ai.py
    └── mcp_server/             # dependency-light stdio target

.planning/phases/01-spike-gate/
├── corpus/corpus.jsonl         # ← SURVIVES (D-07): declared data, not code
├── corpus/clips/*.wav          # ← SURVIVES (~3–5 MB, no git-lfs)
├── corpus/mapping.json         # ← SURVIVES: filename → language_id, for D-14 join-back
├── 01-RESULTS.md               # ← SURVIVES (D-09): raw record, committed BEFORE conclusions
└── (DECISIONS.md at repo root) # ← SURVIVES (SPIKE-09)
```

**Why data lives under `.planning/phases/01-spike-gate/` and not under `spike/`:** so that "delete `spike/`" is an unambiguous, safe operation that satisfies SC#5 without endangering the fixtures Phase 7 SC#1 needs to re-run and diff.

### Pattern 1: Readiness gate before measurement

**What:** A task that fails loudly if any silent-degradation path is active, run before any data is collected.
**When to use:** Whenever a library degrades to a `logger.warning` instead of raising — which is exactly what Chatterbox does for `he`, `ru`, `ja`, and `zh`.
**Why it belongs in the plan as its own task:** Every downstream measurement in this phase inherits its validity from this gate. If it runs as a side-effect of the render step, a failed gate produces a corpus that *looks* fine.

```python
# Source: derived from chatterbox/models/tokenizers/tokenizer.py:117-133 (wheel source, verified)
import logging, warnings

def assert_hebrew_ready() -> None:
    """Fail loudly if Hebrew would be synthesized without diacritics."""
    from dicta_onnx import Dicta            # raises ImportError if missing
    d = Dicta()
    out = d.add_diacritics("שלום עולם")
    assert out != "שלום עולם", "Dicta loaded but returned text unchanged"

    # Belt and braces: catch the silent path at the chatterbox layer too.
    records = []
    handler = logging.Handler(); handler.emit = records.append
    logging.getLogger("chatterbox").addHandler(handler)
    logging.getLogger().addHandler(handler)
    # ... render one probe clip here ...
    bad = [r for r in records if "not available" in r.getMessage()
                              or "failed" in r.getMessage().lower()]
    assert not bad, f"silent degradation active: {[r.getMessage() for r in bad]}"
```

### Pattern 2: Leak-isolated batch rendering

**What:** Render the ~40-clip corpus in subprocesses of N clips each, rather than one long-lived process.
**When to use:** Any Apple Silicon Chatterbox run longer than a handful of generations.
**Why:** A reported 222–800 MB accumulation per few generations means a single-process 40-clip run on an 18 GB machine risks swapping — which silently corrupts every SPIKE-03 timing taken after the pressure starts.

### Anti-Patterns to Avoid

- **Implementing only `on_llm_start` in the LangChain trace handler.** Chat models fire `on_chat_model_start`. A handler with only `on_llm_start` records nothing and SPIKE-05 falsely reads as "prompts not visible." Implement both.
- **Reading `usage_metadata` off a single streamed chunk.** It is populated on the final chunk only. Aggregate chunks (`acc = acc + chunk`) or read `on_llm_end`.
- **Judging Hebrew before Gate 0 passes.** Wastes the one irreplaceable resource in this phase — a first, unprimed native-ear impression (D-13/D-14).
- **Treating "MPS crashed" as a phase blocker.** Per D-11/D-12 it is a *measurement*, and a decision-relevant one for the hardware purchase.
- **Letting the bake-off port's signatures leak into Phase 3.** D-18 is explicit: findings carry, interfaces do not.
- **Enabling Logfire / LangSmith to inspect traces.** Violates the project's no-telemetry commitment; both frameworks work fully offline for this purpose.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hebrew vowel insertion | A niqqud heuristic or a lookup table | `dicta-onnx` | It is the exact model Chatterbox was trained to expect; anything else measures a different pipeline than the one that ships. |
| Per-segment language detection | Script-range heuristics over transcript text | `faster-whisper` `multilingual=True` + `detect_language()` | Script detection cannot distinguish "locked to Russian and transliterated" from "correctly detected Russian" — the exact SPIKE-04 question. Whisper's own language posterior can. |
| MCP client plumbing | Raw JSON-RPC over stdio | `langchain-mcp-adapters` / `pydantic_ai.mcp.MCPToolset` | SPIKE-06 is a test *of the adapter's* observability. Hand-rolling would measure the wrong thing. |
| Token accounting | Counting tokens with a local tokenizer | `usage_metadata` from `langchain-ollama` | SPIKE-05 asks whether the framework surfaces counts — substituting your own answers a different question. |
| WAV I/O and resampling | `wave` + manual conversion | `soundfile`, `librosa` (already a chatterbox dep) | Sample-rate mistakes silently degrade Whisper accuracy and would be misread as STT failure. |
| Audio format conversion | Shelling out to ffmpeg | `soundfile` | ffmpeg is **not installed**; `faster-whisper` 1.2.1 uses PyAV, not ffmpeg-cli, so there is no need to add it. |

**Key insight:** Nearly every hand-rolled substitute in this phase would silently answer a *different question* than the spike was written to ask. In a measurement phase, a wrong instrument is more costly than a missing one, because it produces a confident number that later phases will treat as settled.

---

## Common Pitfalls

### Pitfall 1: Hebrew is synthesized without diacritics and the spike blames the model ⚠️ HIGHEST SEVERITY

**What goes wrong:** SPIKE-02 records a native-ear verdict of "unintelligible" and the project triggers the Hebrew fallback ladder (D-10) — against a configuration that was never correctly assembled.
**Why it happens:** `chatterbox/models/tokenizers/tokenizer.py:117-133` calls `add_hebrew_diacritics()`, which does `from dicta_onnx import Dicta` inside a `try/except ImportError` that **logs a warning and returns the text unchanged**. `dicta-onnx` is **not** in chatterbox-tts's `requires_dist`. Hebrew orthography omits vowels, so the model receives consonant skeletons.
**How to avoid:** `uv pip install dicta-onnx==1.0.9` (needs Python ≥3.11 — 3.12 is fine) and run Pattern 1's assertion before any judgment.
**Warning signs:** Log line `dicta_onnx not available - Hebrew text processing skipped`; Hebrew audio that sounds like fluent-but-wrong vowels rather than noise.
`[VERIFIED: chatterbox_tts-0.1.7 wheel source]` + `[CITED: github.com/danielrosehill/Hebrew-TTS-Providers — independent testing reports Chatterbox Hebrew "unintelligible without nekudot" when Dicta failed to load]`

### Pitfall 2: Russian stress labeling can never work from a pip install

**What goes wrong:** D-20's Russian spot-check finds degraded prosody and it is misattributed to the model or to code-switching.
**Why it happens:** `add_russian_stress()` imports `russian_text_stresser` — **which returns 404 on PyPI under every name variant tested** (`russian-text-stresser`, `russian_text_stresser`). Same silent `except ImportError` → warning → passthrough.
**How to avoid:** You cannot fix this with pip. **Record it as a measured property of the default install**, which is legitimate — it *is* what a user gets. Do not silently absorb it: note in RESULTS.md that Russian was measured without stress labeling, and consider it when D-20's spot-check result is written up.
**Warning signs:** `russian_text_stresser not available - Russian stress labeling skipped`.
`[VERIFIED: chatterbox source + PyPI 404 on all name variants, 2026-07-20]`

### Pitfall 3: Looking for a streaming API that does not exist

**What goes wrong:** SPIKE-03 planning assumes a first-chunk callback and stalls.
**Why it happens:** `ChatterboxMultilingualTTS.generate()` is fully blocking: it runs `t3.inference(...)` to completion, then `s3gen.inference(...)`, then watermarking, then returns one tensor. A package-wide grep for streaming methods finds only `alignment_stream_analyzer` — an internal attention utility, not an output stream.
**How to avoid:** Define TTFA for this phase as **wall-clock from `generate()` call to return, for one short sentence**. This is not a compromise: the project's own SESS-02 design speaks the first *complete sentence*, so first-sentence synthesis time *is* production TTFA. State this definition explicitly in RESULTS.md so Phase 12's published number is comparable.
`[VERIFIED: chatterbox_tts-0.1.7 wheel source — no stream/chunk generator anywhere in package]`

### Pitfall 4: MPS fails, and the phase treats it as a blocker instead of a result

**What goes wrong:** The plan stalls trying to make MPS work, or worse, quietly reports CPU numbers as MPS numbers.
**Why it happens:** Chatterbox on MPS is documented-unreliable: `Placeholder storage has not been allocated on MPS device!`, `float64 not supported by MPS`, and multiple community forks that detect Apple Silicon and force CPU "for maximum stability." Note also that `from_pretrained` compares `device == "mps"` as a **string** despite the `torch.device` type hint — passing `torch.device("mps")` skips the availability check entirely.
**How to avoid:** Pass the **string** `"mps"`. Wrap the MPS run in a try/except that records the exact exception text as data. Per D-11/D-12, "MPS unusable on chatterbox-tts 0.1.7" is a legitimate SPIKE-03 finding and is directly relevant to the hardware-class inference.
`[VERIFIED: source string-comparison bug]` + `[CITED: github.com/resemble-ai/chatterbox issue #218; devnen/Chatterbox-TTS-Server issue #93]`

### Pitfall 5: A memory leak silently corrupts the timing series

**What goes wrong:** Later clips in the ~40-clip render are slower than earlier ones, and the trend is read as a property of the text rather than of memory pressure.
**Why it happens:** Reported accumulation of ~222–800 MB per few generations on Apple Silicon, with tensors not released by GC. On an 18 GB shared-memory machine this reaches swap well within 40 clips.
**How to avoid:** Render in subprocesses of N clips (N≈5–8), fresh process each batch. Take SPIKE-03 TTFA numbers in a **dedicated single-purpose process**, not as a by-product of the corpus render.
`[CITED: github.com/resemble-ai/chatterbox issue #218]`

### Pitfall 6: Nondeterministic synthesis breaks Phase 7's "re-run and diff"

**What goes wrong:** D-07 promises Phase 7 SC#1 can mechanically re-run and diff against Phase 1. With sampling defaults (`temperature=0.8`, `min_p=0.05`, `top_p=1.0`), two runs of the same sentence produce different audio, so the diff is meaningless.
**How to avoid:** Call `torch.manual_seed(FIXED)` immediately before **each** `generate()` (not once per process — batching and subprocess boundaries would otherwise shift the stream), and record the seed and every generation parameter in RESULTS.md. Even then, expect MPS/CPU backends to diverge; note this so Phase 7 compares CPU-to-CPU.
`[VERIFIED: generate() defaults in wheel source]`

### Pitfall 7: Asking Whisper the lock-on question without the instrument that answers it

**What goes wrong:** SPIKE-04 transcribes with defaults, sees one language in `TranscriptionInfo.language`, and concludes "it locks on" — when the default behavior *is* to detect once and apply globally.
**Why it happens:** `transcribe()` defaults to `multilingual=False`. The flag's own docstring reads *"Perform language detection on every segment."*
**How to avoid:** Run **both** conditions per clip — `multilingual=False` (production-default behavior) and `multilingual=True` (best-case) — and record `all_language_probs` plus a separate `model.detect_language()` call. ⚠️ Note the real limitation: the `Segment` dataclass carries **no `language` field**, so even with `multilingual=True` you infer per-segment language from `all_language_probs` and output script, not from a direct label. Record that as a caveat.
**Also:** `vad_filter` defaults to **`True`** in 1.2.1 — on short synthetic clips this can trim audio and be misread as transcription failure. Test with it off. And `task="translate"` (default `"transcribe"`) always targets English — it is the instrument for the "translates the rest" half of SPIKE-04, not something to leave at default.
`[VERIFIED: faster_whisper/transcribe.py wheel source]`

### Pitfall 8: Concluding "Ollama token counts are None" from a streaming chunk

**What goes wrong:** SPIKE-05 returns a false negative and the LangChain recommendation is overturned on a measurement error — precisely the falsification test CLAUDE.md flagged as decision-critical.
**Why it happens:** `_get_usage_metadata_from_generation_info()` returns `None` unless **both** `prompt_eval_count` and `eval_count` are present. Ollama sends these only on the final `done: True` chunk. Every intermediate streamed chunk therefore carries `usage_metadata=None`.
**How to avoid:** Aggregate the chunk stream (`acc = acc + chunk`) and read `acc.usage_metadata`, or read from `on_llm_end`'s `LLMResult` (`response.generations[0][0].message.usage_metadata`). Confirm against the raw Ollama client first, so a null result can be attributed to the framework rather than to the model or daemon.
**Note:** `langchain-ollama` 1.1.0's own class docstring shows a populated `usage_metadata={'input_tokens': 10, 'output_tokens': 3615, 'total_tokens': 3625}`. Source strongly suggests SPIKE-05's answer is **yes, visible** — the spike's job is to confirm it end-to-end through the port.
`[VERIFIED: langchain_ollama/chat_models.py:102-114, 520 — wheel source]`

### Pitfall 9: MCP structured results are invisible because they are in `artifact`, not `output`

**What goes wrong:** SPIKE-06 — the explicit falsification test for the whole agent-framework choice — reports "MCP results not visible through callbacks," and the project switches frameworks on a handler bug.
**Why it happens:** `convert_mcp_tool_to_langchain_tool()` returns a `StructuredTool(..., response_format="content_and_artifact")`. The coroutine returns a **tuple** `(content, artifact)` where `artifact` is an `MCPToolArtifact` holding `structured_content`. A handler that records only the stringified tool output sees the content half and misses the structured half.
**How to avoid:** In `on_tool_end`, record the full output object including the artifact; in `on_tool_start`, record `input_str`/`inputs` for args. Because MCP tools are ordinary `StructuredTool`s, the standard callbacks **do** fire — the risk is fidelity, not absence.
**Do not confuse:** `langchain_mcp_adapters.callbacks` is a *separate* concept — MCP-protocol callbacks (`LoggingMessageCallback`, `ProgressCallback`, `ElicitationCallback`) with a `CallbackContext(server_name, tool_name)`. Useful supplementary evidence for SPIKE-06, but not the LangChain tracing callbacks the requirement names.
`[VERIFIED: langchain_mcp_adapters/tools.py:357-538, callbacks.py — wheel source]`

### Pitfall 10: SPIKE-08's per-stage budget is dominated by unmeasured warmup

**What goes wrong:** The published budget says TTS costs ~30 s, because run #1 included a 3.2 GB model load.
**How to avoid:** Structure the round trip as: **load & warm all three engines → assert warm → then time N iterations, discarding the first.** Report cold-start separately (it is real, and VOICE-10 exists because of it). Attribute per stage with explicit boundaries: `t_stt = stt_end - stt_start`, etc., plus a `t_unattributed` residual so the stages are forced to sum to the wall clock — a residual that is not near zero means the harness is wrong.
⚠️ **18 GB RAM is the binding constraint here:** Chatterbox (~3.2 GB weights) + Whisper large-v3 (~3 GB) + an Ollama tool-calling model (4–8 GB) co-resident is tight. If it swaps, every stage number is fiction. Consider a small Ollama model for SPIKE-08 (latency shape) distinct from the tool-calling model used for SPIKE-05/06/07 (capability), and say so in RESULTS.md.

### Pitfall 11: Watermarking is unconditional and sits on the latency path

**What goes wrong:** Not a failure so much as an un-recorded fact. `generate()` always calls `self.watermarker.apply_watermark(wav, sample_rate=self.sr)` — there is **no flag to disable it**. It is inside the timed region, so every TTFA number includes it.
**How to avoid:** Note it in RESULTS.md. This is also the Phase 1 evidence for VOICE-12 ("Chatterbox watermarking behavior is documented explicitly as a known property of the default engine").
`[VERIFIED: chatterbox/mtl_tts.py:155, 316 — wheel source]`

### Pitfall 12: Using pre-v2 Pydantic AI syntax

**What goes wrong:** The Pydantic AI adapter fails on first import, is scored as "harder," and D-19's stopping rule ends the bake-off on a typo.
**Why it happens:** Every pre-2026-06-23 tutorial, and much of the model's own training data, uses `MCPServerStdio` / `mcp_servers=` / `instrument=`. **All are gone in 2.13.0.**
**How to avoid:** Use only the verified v2 surface in §Code Examples. Under D-19 the guard is explicit: if the Pydantic AI adapter is abandoned incomplete, record *why* — "API friction from an unfamiliar v2 surface" is a materially different finding from "the framework resists porting."
`[VERIFIED: pydantic_ai_slim-2.13.0 wheel source — `mcp.py __all__` contains no `MCPServer*` classes]`

---

## Code Examples

### Chatterbox multilingual synthesis (SPIKE-01/02/03)

```python
# Source: chatterbox_tts-0.1.7 wheel — chatterbox/mtl_tts.py (read directly, 2026-07-20)
import time, torch, soundfile as sf
from chatterbox import ChatterboxMultilingualTTS, SUPPORTED_LANGUAGES

# 'he', 'ru', 'es', 'en' are all present in SUPPORTED_LANGUAGES (23 total). VERIFIED.
assert {"en", "ru", "he", "es"} <= set(SUPPORTED_LANGUAGES)

# NOTE: pass the STRING "mps" — from_pretrained does `device == "mps"`, a string
# comparison, despite the `torch.device` type hint. torch.device("mps") skips the
# availability check and the CPU fallback.
tts = ChatterboxMultilingualTTS.from_pretrained(device="mps")   # or "cpu"

torch.manual_seed(1234)          # per-call, for D-07 reproducibility (Pitfall 6)
t0 = time.perf_counter()
wav = tts.generate(              # language_id is the 2nd POSITIONAL arg and required
    "שלום, meeting at 15:00",
    language_id="he",            # validated against SUPPORTED_LANGUAGES; ValueError if unknown
    # audio_prompt_path=None  -> uses the built-in voice from conds.pt
    exaggeration=0.5, cfg_weight=0.5, temperature=0.8,
    repetition_penalty=2.0, min_p=0.05, top_p=1.0,
)
ttfa = time.perf_counter() - t0  # blocking call: this IS time-to-first-audio (Pitfall 3)

sf.write("clip.wav", wav.squeeze(0).numpy(), tts.sr)   # tts.sr == S3GEN_SR
```

**Untagged control condition:** `generate()` guards with `if language_id and ...`, so `language_id=None` is accepted and skips both the language-token prepend and the per-language normalization. This gives SPIKE-01 a free third condition — "no tag at all" — beyond D-06's matrix/embedded pair. Cheap and worth taking.

### Whisper transcription with language introspection (SPIKE-04)

```python
# Source: faster_whisper 1.2.1 wheel — faster_whisper/transcribe.py (read directly)
from faster_whisper import WhisperModel

# "large-v3"       -> Systran/faster-whisper-large-v3            (first-party)
# "large-v3-turbo" -> mobiuslabsgmbh/faster-whisper-large-v3-turbo (community)
# CTranslate2 has NO Metal backend: this is CPU on Apple Silicon. arm64 wheels DO exist.
model = WhisperModel("large-v3", device="cpu", compute_type="int8")

segments, info = model.transcribe(
    "clip.wav",
    language=None,          # None => auto-detect (SPIKE-04 must never pin the language)
    multilingual=True,      # "Perform language detection on every segment."  ← the instrument
    vad_filter=False,       # default is True in 1.2.1 and can trim short synthetic clips
    task="transcribe",      # switch to "translate" (English-only target) for the translate probe
)

print(info.language, info.language_probability)
print(info.all_language_probs[:5])           # full posterior over languages
for s in segments:                            # NOTE: Segment has NO .language field
    print(s.id, round(s.start, 2), round(s.end, 2), s.text)

# Independent per-clip language posterior:
lang, prob, all_probs = model.detect_language("clip.wav")
```

### LangChain adapter — tracing that actually fires (SPIKE-05/06)

```python
# Source: langchain_core 1.4.9 + langchain_ollama 1.1.0 wheels (read directly)
from uuid import UUID
from typing import Any
from langchain_core.callbacks import AsyncCallbackHandler

class SpikeTrace(AsyncCallbackHandler):
    def __init__(self): self.events = []

    # ⚠️ CHAT models fire on_chat_model_start, NOT on_llm_start. Implement BOTH.
    async def on_chat_model_start(self, serialized: dict, messages, *, run_id: UUID,
                                  parent_run_id: UUID | None = None, tags=None,
                                  metadata=None, **kw: Any) -> None:
        self.events.append(("chat_model_start", str(run_id), messages))

    async def on_llm_start(self, serialized: dict, prompts: list[str], *, run_id: UUID,
                           parent_run_id: UUID | None = None, tags=None,
                           metadata=None, **kw: Any) -> None:
        self.events.append(("llm_start", str(run_id), prompts))

    async def on_llm_new_token(self, token: str, *, chunk=None, run_id: UUID,
                               parent_run_id: UUID | None = None, tags=None, **kw) -> None:
        self.events.append(("token", token))

    async def on_llm_end(self, response, *, run_id: UUID, **kw) -> None:
        # SPIKE-05 lives here: usage is on the FINAL result, not on intermediate chunks.
        msg = response.generations[0][0].message
        self.events.append(("usage", getattr(msg, "usage_metadata", None),
                                     getattr(response, "llm_output", None)))

    async def on_tool_start(self, serialized: dict, input_str: str, *, run_id: UUID,
                            inputs: dict | None = None, **kw) -> None:
        self.events.append(("tool_start", serialized.get("name"), input_str, inputs))

    async def on_tool_end(self, output, *, run_id: UUID, **kw) -> None:
        # SPIKE-06: MCP tools use response_format="content_and_artifact".
        # Structured content is in the ARTIFACT half — record the whole object.
        self.events.append(("tool_end", output, getattr(output, "artifact", None)))
```

```python
# Model loading from a named profile (D-16) + MCP tools (SPIKE-06)
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient

model = init_chat_model("ollama:qwen3")    # string -> model; maps onto a YAML profile

client = MultiServerMCPClient({
    "probe": {"command": "npx", "args": ["-y", "<some-stdio-mcp-server>"],
              "transport": "stdio"},
})
tools = await client.get_tools()   # each becomes a StructuredTool (content_and_artifact)
```

### Pydantic AI **v2** adapter — verified 2.13.0 surface (SPIKE-07)

```python
# Source: pydantic_ai_slim-2.13.0 wheel (read directly, 2026-07-20).
# ⚠️ MCPServerStdio / MCPServerSSE / MCPServerStreamableHTTP DO NOT EXIST in v2.
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.capabilities import Hooks

# MCPToolset is built on FastMCP and infers the transport from what you pass:
#   a URL string          -> HTTP / SSE
#   a script path         -> stdio
#   a FastMCP instance    -> in-process (ideal for a hermetic spike)
#   a fastmcp.Client      -> full control
toolset = MCPToolset("spike/bakeoff/mcp_server/server.py")     # stdio

hooks = Hooks()

@hooks.on.before_model_request
async def _before(ctx, request_context):
    ...   # prompts / model choice
    return request_context

@hooks.on.after_model_request
async def _after(ctx, response):
    ...   # token usage lands here
    return response

@hooks.on.before_tool_execute
async def _tool_in(ctx, args):
    ...   # SPIKE-06 equivalent: tool args
    return args

@hooks.on.after_tool_execute
async def _tool_out(ctx, result):
    ...   # SPIKE-06 equivalent: tool results
    return result

# v2 constructor: `capabilities=` and `toolsets=`. There is no `mcp_servers=`,
# no `instrument=`, no `prepare_tools=`, no `history_processors=`.
agent = Agent(
    "ollama:qwen3",
    toolsets=[toolset],
    capabilities=[hooks],
)
```

**Full v2 hook set available on `hooks.on`** (for the D-17 fidelity comparison against LangChain's callback set): `before_run`, `after_run`, `run`, `run_error`, `before_node_run`, `after_node_run`, `node_run`, `node_run_error`, `run_event_stream`, `event`, `before_model_request`, `after_model_request`, `model_request`, `model_request_error`, `before_tool_validate`, `after_tool_validate`, `tool_validate`, `tool_validate_error`, `before_tool_execute`, `after_tool_execute`, `tool_execute`, `tool_execute_error`, `before_output_validate`, `after_output_validate`, `output_validate`, `output_validate_error`, `before_output_process`, `after_output_process`, `output_process`, `output_process_error`, `prepare_tools`, `prepare_output_tools`, `deferred_tool_calls`. `[VERIFIED: capabilities/hooks.py wheel source]`

⚠️ **Do not enable `pydantic_ai.capabilities.Instrumentation`** unless the spike explicitly wants the OTel path — it is the Logfire integration point and the project forbids telemetry. Hooks alone give in-process tracing with no exporter.

---

## State of the Art

Corrections and drift against `.claude/CLAUDE.md` (versions there were verified 2026-07-13; today is 2026-07-20).

| CLAUDE.md said | Current reality | Impact |
|----------------|-----------------|--------|
| LangChain **1.3.13** (2026-07-10) | **1.3.14** (2026-07-16) | Minor drift; stability policy intact. |
| Pydantic AI **2.9** in the comparison table | **2.13.0** (2026-07-18, two days ago) | Four minors in a month — under the shortened 3-month window. Reinforces the stability concern, and means SPIKE-07 should pin an exact version and record it. |
| "CTranslate2 (faster-whisper) has no Metal/Apple-GPU backend — **it is CPU-only on your Mac**" | ✅ Correct on Metal — **but arm64 macOS wheels DO ship** (`ctranslate2-4.8.1-cp312-cp312-macosx_11_0_arm64.whl`) | faster-whisper **installs and runs** on the Mac. It is slow, not blocked. Since SPIKE-04 needs its `multilingual` flag and only handles ~40 short clips, **use faster-whisper for SPIKE-04** and reserve mlx-whisper for SPIKE-08 if needed. |
| "`language_id` API" (from README) | ✅ Confirmed exactly: `generate(text, language_id, ...)`, 2nd positional, validated, `.lower()`-normalized | No change; now verified from source rather than README. |
| Spike #3 "Hebrew TTS quality" as a straight quality question | Must be **gated on `dicta-onnx`** first | The single highest-value correction in this research. |
| Chatterbox "⚠️ sentence-chunked" streaming | **No streaming API at all** in 0.1.7 | Sentence chunking is something *PAAF* will implement (SESS-02), not something Chatterbox provides. Reframes SPIKE-03. |
| Chatterbox "❌ GPU strongly preferred" | Accurate, **and MPS specifically is unreliable** | "MPS unusable" becomes a legitimate D-11 measurement. |

**Deprecated/outdated:**
- **Pydantic AI pre-v2 MCP API** (`MCPServerStdio`, `MCPServerSSE`, `MCPServerStreamableHTTP`, `mcp_servers=`, `instrument=`): removed in v2 (2026-06-23). Replaced by `MCPToolset` + `capabilities=` + `toolsets=`. `[VERIFIED: wheel source]`
- **`russian_text_stresser`**: never published to PyPI; the code path referencing it is effectively dead for pip installs. `[VERIFIED: PyPI 404]`

---

## Environment Availability

Probed on the actual dev machine, 2026-07-20.

**Machine:** Apple **M3 Pro**, **18 GB** unified memory, macOS 26.5.2, arm64, 276 GB free disk.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Everything (CLAUDE.md pin) | ✗ | **only system Python 3.9.6** | Install via `uv python install 3.12` |
| `uv` | Venv/package management (CLAUDE.md) | ✗ | — | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Ollama daemon** | SPIKE-05, 06, 07, 08 | ✗ | — | **None — blocking.** Install + `ollama pull` a tool-calling model. |
| Node.js / npx | stdio MCP server target (SPIKE-06) | ✓ | v24.16.0 | — |
| git | Everything | ✓ | — | — |
| git-lfs | D-07 corpus (~3–5 MB) | ✗ | — | **Not needed** — D-07 explicitly says lfs is unnecessary. |
| ffmpeg | Audio conversion | ✗ | — | **Not needed** — faster-whisper 1.2.1 uses PyAV; `soundfile` covers WAV I/O. |
| Disk for models | Chatterbox 3.2 GB + Whisper ~3 GB | ✓ | 276 GB free | — |
| RAM for co-resident engines | SPIKE-08 round trip | ⚠️ | **18 GB** | Use a small Ollama model for SPIKE-08; see Pitfall 10. |
| MPS backend | SPIKE-03 (D-11) | ⚠️ hardware yes, **library support unreliable** | — | CPU; record MPS failure as data (Pitfall 4). |

**Missing dependencies with no fallback (must be plan tasks):**
- **Ollama is not installed.** Four of nine requirements (SPIKE-05, 06, 07, 08) depend on it. The plan needs an explicit install + model-pull task, and per CLAUDE.md the model must be chosen for **tool-calling reliability**, re-checked at implementation time.
- **Python 3.12 is not present** — the machine has only system Python 3.9.6, which fails `chatterbox-tts` (`>=3.10`), `dicta-onnx` (`>=3.11`), and `langchain` (`>=3.10`).
- **`uv` is not installed** despite being the project's chosen tool.

**Missing with viable fallback / not actually needed:** ffmpeg, git-lfs, `sounddevice` (Phase 1 is file-based, per D-04 and SPIKE-08's WAV-in→WAV-out framing).

---

## Validation Architecture

`workflow.nyquist_validation` is `true`. This phase produces measurements rather than shipped behavior, so "tests" here mean **harness self-checks that protect the validity of the measurements** — they verify the instrument, not the product. Per SC#5 they are deleted with the rest of `spike/`.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.x + `pytest-asyncio` (CLAUDE.md §Development Tools) |
| Config file | **none — Wave 0** (greenfield repo, no build config) |
| Quick run command | `uv run pytest spike/ -x -q` |
| Full suite command | `uv run pytest spike/ -q` |

⚠️ **Do not create a root `pyproject.toml`/`pytest.ini` in Phase 1.** FOUND-01 (Phase 2) establishes the uv workspace, and CONTEXT.md is explicit that Phase 1 "must not anticipate that structure." Keep any pytest config inside `spike/` so it is removed with the directory.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SPIKE-01 | Corpus satisfies the D-02/D-03 grid (all 6 categories present; each of en/ru/he/es appears as both matrix and embedded) | unit | `pytest spike/voice/test_corpus_grid.py -x` | ❌ Wave 0 |
| SPIKE-01 | `SUPPORTED_LANGUAGES` contains en/ru/he/es; unknown tag raises `ValueError` | unit | `pytest spike/voice/test_lang_ids.py -x` | ❌ Wave 0 |
| SPIKE-02 | **Gate 0:** `dicta_onnx` imports, `Dicta()` mutates Hebrew text, no degradation warning fires | unit | `pytest spike/voice/test_readiness.py -x` | ❌ Wave 0 |
| SPIKE-02 | `russian_text_stresser` absence is detected and recorded, not silently absorbed | unit | `pytest spike/voice/test_readiness.py -x` | ❌ Wave 0 |
| SPIKE-02/D-14 | Blind shuffle is reversible: mapping.json round-trips every clip to its `language_id` | unit | `pytest spike/voice/test_blind_mapping.py -x` | ❌ Wave 0 |
| SPIKE-03 | Timing harness excludes model load (warm run asserted faster than cold by a wide margin) | integration | `pytest spike/voice/test_ttfa_harness.py -x` | ❌ Wave 0 |
| SPIKE-04 | Transcribe harness runs both `multilingual` conditions and captures `all_language_probs` | integration | `pytest spike/voice/test_transcribe_harness.py -x` | ❌ Wave 0 |
| SPIKE-05 | Trace handler implements **both** `on_chat_model_start` and `on_llm_start`; usage read post-aggregation | unit (fake model) | `pytest spike/bakeoff/test_trace_handler.py -x` | ❌ Wave 0 |
| SPIKE-06 | `on_tool_end` capture retains the `artifact` half of `content_and_artifact` | unit (fake tool) | `pytest spike/bakeoff/test_artifact_capture.py -x` | ❌ Wave 0 |
| SPIKE-07 | Both adapters satisfy the same port protocol (structural conformance) | unit | `pytest spike/bakeoff/test_port_conformance.py -x` | ❌ Wave 0 |
| SPIKE-08 | Per-stage timings sum to wall clock within tolerance (`t_unattributed` ≈ 0) | integration | `pytest spike/voice/test_roundtrip_accounting.py -x` | ❌ Wave 0 |
| SPIKE-09 | RESULTS.md exists and is committed **before** DECISIONS.md conclusions (D-09 ordering) | manual | git log inspection | — |

**Manual-only, with justification:**
- **SPIKE-02's verdict** — a native-ear judgment recorded verbatim (D-13). Irreducibly human; automation would defeat the requirement.
- **D-20 ru/es spot-checks** — same reason.
- **SC#4 claim audit** — reading repo prose against measurements is a judgment task.

### Sampling Rate

- **Per task commit:** `uv run pytest spike/ -x -q` (fast; no model inference — all model-touching tests marked `@pytest.mark.slow`)
- **Per wave merge:** `uv run pytest spike/ -q` including `slow`
- **Phase gate:** Gate 0 green **before** any corpus render; full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `spike/pytest.ini` (or `[tool.pytest.ini_options]` **inside `spike/`**, not at repo root) — with a `slow` marker
- [ ] `spike/conftest.py` — shared fixtures: tmp corpus, fake model, fake tool, device parametrization
- [ ] Framework install: `uv pip install pytest pytest-asyncio`
- [ ] Python 3.12 toolchain: `uv python install 3.12` (blocking — see §Environment)
- [ ] All 11 test files above

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`. Phase 1 ships nothing, exposes no network surface, and has no users — so most ASVS categories are genuinely inapplicable. The real risks here are **supply-chain** and **privacy-commitment** rather than application security.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No auth surface; no accounts anywhere (PRIV-01). |
| V3 Session Management | no | No sessions. |
| V4 Access Control | no | Single-user local scripts. |
| V5 Input Validation | partial | Corpus is author-controlled data. `language_id` **is** validated by Chatterbox against `SUPPORTED_LANGUAGES`. MCP tool results are untrusted input — but Phase 1 only observes them; TOOL-07 owns the real defense. |
| V6 Cryptography | no | No secrets, no crypto. Do **not** set `HF_TOKEN` — all models used are public. |
| V10 Malicious Code | **yes** | Supply chain: see §Package Legitimacy Audit. `dicta-onnx` is the one newly-introduced, individually-maintained package. |
| V12 Files & Resources | partial | `snapshot_download` writes ~3.2 GB into the HF cache. Model downloads must be explicit and consented (PRIV-06) — do not let a spike script be the first thing that silently pulls gigabytes. |
| V14 Configuration | **yes** | Telemetry-off posture must be actively asserted, not assumed. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Slopsquatted / typosquatted PyPI package | Tampering | Legitimacy gate run (above); `dicta-onnx` corroborated against the import path hard-coded in chatterbox source. |
| Unpinned transitive pull of a compromised release | Tampering | Pin exact versions in the install commands; record resolved versions in RESULTS.md. |
| **Silent telemetry egress via Logfire / LangSmith** | Information Disclosure | Explicitly unset `LOGFIRE_TOKEN`, `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGCHAIN_TRACING_V2` in the spike runner. Do not enable `Instrumentation`. Violating this contradicts PRIV-02 ("no telemetry, ever"). |
| MCP server executes arbitrary local code | Elevation of Privilege | The stdio MCP target runs as a subprocess with the user's privileges. Use a trivial, locally-authored or well-known server; do not point the spike at an arbitrary third-party server. |
| Prompt injection via MCP tool results | Tampering | **Out of scope for Phase 1** — TOOL-07 makes the permission model the documented defense. Phase 1 only observes whether results are *visible*. |
| Unconsented model download | Information Disclosure (egress) | Make the 3.2 GB Chatterbox fetch and the Whisper fetch explicit, announced steps — this also rehearses PRIV-06. |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Installing `dicta-onnx` will materially improve Hebrew output quality (not merely remove the warning) | Pitfall 1 | Low — the gate is cheap and correct regardless. If quality is still poor *with* diacritics, that is a much stronger and more trustworthy SPIKE-02 finding. |
| A2 | `dicta-onnx`'s `onnxruntime==1.21.1` and `tokenizers>=0.21.1` pins co-resolve with chatterbox's `transformers==5.2.0` | Installation | Medium — a resolver conflict would need a workaround (separate process, or vendoring the diacritization step). Verify at install time; this is the first thing likely to break. |
| A3 | `transformers==5.2.0` and `diffusers==0.29.0` (a mid-2024 release) actually work together at runtime | Installation | Medium — chatterbox pins both, so upstream presumably tests it, but diffusers 0.29 predates transformers 5.x by a long way. An import error here blocks all voice spikes. |
| A4 | The reported Apple Silicon memory leak affects `ChatterboxMultilingualTTS`, not only `ChatterboxTTS` | Pitfall 5 | Low — subprocess batching is cheap insurance either way. |
| A5 | An Ollama model can be found that does tool-calling reliably enough for SPIKE-06/07 on 18 GB | Environment | Medium — CLAUDE.md flags this as UNVERIFIED and instructs re-checking. A weak tool-caller would make MCP tracing hard to observe for reasons unrelated to the framework. |
| A6 | `torch.manual_seed()` is sufficient for reproducible Chatterbox output on a given backend | Pitfall 6 | Medium — some MPS/CPU kernels are nondeterministic regardless. If reproducibility fails, D-07's "Phase 7 re-runs and diffs" promise needs weakening to a qualitative comparison. Worth an early explicit check. |
| A7 | ~20 sentences × 2 tags ≈ 40 clips lands within D-07's 3–5 MB estimate | D-07 | Low — at 24 kHz mono, 40 clips of a few seconds is comfortably under 5 MB. |
| A8 | A dependency-light stdio MCP server is readily available via npx | Standard Stack | Low — writing a trivial one is a small task if not. |

---

## Open Questions (RESOLVED)

> All five were resolved during planning and threaded into the plans: Q1→01-04 (Ollama model gate), Q2→01-03 (seed-reproducibility check), Q3 no-halt→wave structure + 01-08/01-10, Q4→01-09 (budget-table shape), Q5→01-05 (`language_id=None` control). Retained below for provenance.

1. **Which Ollama model for the bake-off?**
   - What we know: criterion is **tool-calling reliability**, not chat quality (CLAUDE.md §Decision 6). Qwen3 family sized to available memory is the standing default.
   - What's unclear: CLAUDE.md explicitly marks the current community default as `[UNVERIFIED — MEDIUM]` and instructs re-checking at implementation time. 18 GB shared memory bounds the size.
   - Recommendation: pick one at execution time, verify tool-calling on a trivial two-tool case **before** starting SPIKE-06, and record the model and its version in RESULTS.md. Consider a smaller model for SPIKE-08's latency shape than for SPIKE-05/06/07's capability.

2. **Does Chatterbox generation reproduce under a fixed seed on this hardware?**
   - What we know: sampling defaults make it stochastic; `torch.manual_seed()` is the standard lever.
   - What's unclear: whether MPS/CPU kernels honor it fully.
   - Recommendation: test with two identical seeded runs during Gate 0. If they differ, say so in RESULTS.md and soften D-07's re-run-and-diff promise to qualitative comparison — better to discover this now than in Phase 7.

3. **Should a catastrophic red-spike result halt the remaining spikes?** (CONTEXT.md gray area)
   - What we know: SPIKE-01/02 are the founding-promise risks; SPIKE-05/06/07 are independent of them and run in a separate venv.
   - Recommendation: **no halt.** The tracks share no dependency, and D-10 already forbids Phase 1 from *deciding* anything about the fallback ladder — so there is no decision a bad Hebrew result could short-circuit. Halting would only reduce the evidence available to Phase 6. Order the voice track first so the highest-risk unknown resolves earliest.

4. **How should the SPIKE-08 budget be reported?** (CONTEXT.md gray area)
   - Recommendation: a table of `stage | cold ms | warm p50 ms | warm p95 ms | share of total`, with an explicit `unattributed` row, plus the hardware and model configuration inline. Include the D-12 caveat directly in the table caption, since this table is what the hardware-purchase inference rests on.

5. **Is the `he` language token meaningful when text is untagged?**
   - What we know: `language_id=None` skips both normalization and the token prepend — a free control condition.
   - Recommendation: add it as a third condition for a subset of sentences. It cleanly separates "the tag did nothing" from "the tag did the wrong thing," which is the crux of SPIKE-01.

---

## Sources

### Primary (HIGH confidence — read directly from published artifacts, 2026-07-20)

- `chatterbox_tts-0.1.7-py3-none-any.whl` — `mtl_tts.py` (`generate` signature, `from_pretrained`, watermarking, no streaming), `models/tokenizers/tokenizer.py` (`SUPPORTED_LANGUAGES`, language-token prepend, `add_hebrew_diacritics`, `add_russian_stress` silent-degradation paths)
- `pydantic_ai_slim-2.13.0-py3-none-any.whl` — `mcp.py` (`__all__`, `MCPToolset`, `MCPToolsetClient`, `_build_transport`), `capabilities/__init__.py` (`__all__`), `capabilities/hooks.py` (full hook set), `agent/__init__.py` (v2 constructor)
- `langchain_mcp_adapters-0.3.0-py3-none-any.whl` — `tools.py` (`convert_mcp_tool_to_langchain_tool`, `StructuredTool(response_format="content_and_artifact")`), `callbacks.py`
- `langchain_core-1.4.9` — `callbacks/base.py` (exact hook signatures, `on_chat_model_start` vs `on_llm_start`)
- `langchain_ollama-1.1.0` — `chat_models.py:102-114` (`_get_usage_metadata_from_generation_info`), docstring example at :520
- `faster_whisper-1.2.1` — `transcribe.py` (`transcribe()` signature, `multilingual` flag, `Segment`/`TranscriptionInfo` dataclasses, `detect_language`), `utils.py` (`_MODELS` repo mapping)
- `mlx_whisper-0.4.3` — `transcribe.py`, `decoding.py`
- PyPI JSON API — versions, licenses, `requires_python`, `requires_dist`, upload dates, wheel platform tags for all packages listed
- HuggingFace Hub API — `ResembleAI/chatterbox` file sizes (3.2 GB total), license, 23-language metadata
- Local environment probe — M3 Pro / 18 GB / macOS 26.5.2; Python 3.9.6 only; uv, Ollama, ffmpeg, git-lfs absent; Node v24.16.0 present

### Secondary (MEDIUM confidence — community reports corroborating source findings)

- [Critical Memory Leak (Apple Silicon) · Issue #218 · resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox/issues/218) — 222–800 MB accumulation
- [Fails to generate with Turbo model on Apple Silicon, Float64 not supported · Issue #93 · devnen/Chatterbox-TTS-Server](https://github.com/devnen/Chatterbox-TTS-Server/issues/93)
- [Jimmi42/chatterbox-tts-apple-silicon-code](https://huggingface.co/Jimmi42/chatterbox-tts-apple-silicon-code) — MPS tensor allocation errors; CPU fallback for stability
- [danielrosehill/Hebrew-TTS-Providers](https://github.com/danielrosehill/Hebrew-TTS-Providers) — independent report: Chatterbox Hebrew "unintelligible without nekudot" when Dicta ONNX failed to load; voice cloning did not carry through to Hebrew
- [ChatterboxMultilingualTTS · DeepWiki](https://deepwiki.com/resemble-ai/chatterbox/3.2-chatterboxmultilingualtts) — confirms dicta_onnx role for nikud
- [Chatterbox Multilingual · Resemble AI](https://www.resemble.ai/learn/models/chatterbox-multilingual) — 23-language claim, MIT, watermarking

### Tertiary (LOW confidence — noted, not relied upon)

- General community commentary on Ollama model tool-calling reliability — deliberately not used; CLAUDE.md instructs re-checking at implementation time (§Open Questions #1)

---

## Metadata

**Confidence breakdown:**
- **Standard stack / versions:** HIGH — every version, license, dependency pin and platform wheel read live from the PyPI JSON API on 2026-07-20.
- **API surface (Chatterbox, Whisper, LangChain, Pydantic AI v2):** HIGH — read from the published wheels themselves, not from documentation. This is the strongest available verification and it caught the Pydantic AI v2 break, the `on_chat_model_start` gotcha, and the `content_and_artifact` nuance.
- **Silent-degradation pitfalls (Hebrew/Russian):** HIGH — source-verified code path, independently corroborated by third-party testing for Hebrew; PyPI 404 confirmed for the Russian package.
- **MPS instability and memory leak:** MEDIUM — multiple independent community reports plus a source-verified string-comparison bug, but not reproduced on this machine.
- **Environment availability:** HIGH — probed directly.
- **The quality outcomes the phase exists to measure** (Hebrew intelligibility, code-switching behavior, actual latency): **LOW by design** — this is precisely what Phase 1 exists to convert into evidence. Nothing in this document should be read as pre-judging them.

**Research date:** 2026-07-20
**Valid until:** 2026-08-03 (14 days). Shortened from the usual 30 because `pydantic-ai` shipped four minor releases in a month under a 3-month stability window, and `langchain` drifted a patch version within the 7 days since CLAUDE.md was written. Re-verify both versions at execution time.
