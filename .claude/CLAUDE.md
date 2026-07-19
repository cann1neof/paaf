<!-- GSD:project-start source:PROJECT.md -->

## Project

**PAAF — Personalized Agentic Assistant Framework**

An open-source personal voice assistant that its user completely owns, delivered as two things. **The Framework**: a Python package with exactly two core modules — *LLM Management* (which model, which skills, which tools, which persona, which behaviors — exposed as user-facing concepts, not code) and *Voice* (streaming speech-to-text and text-to-speech). **The App**: an embedded assistant process that runs on the user's own Linux machine and imports the framework directly, plus an Electron desktop app that is the control panel — every tweak and setting of the assistant, configured from your computer.

It is for two audiences equally: self-hosters and privacy-minded people who want an assistant they can run and verify, and developers who want to build a *different* assistant on the framework alone.

**Core Value:** **The user owns the assistant's mind.** They pick the model (local, API, or hybrid), write its persona, install its skills, expose its tools, and decide what it does while it thinks — all without writing code, and with nothing hidden from them. If everything else fails, this must work.

### Constraints

- **Dev environment**: macOS laptop, no target hardware yet — Mac is a dev harness only, Linux is the ship target. Budget for hardware is being saved.
- **Time**: 20+ h/week, this is a main focus.
- **Cost**: minimal — local models via Ollama plus API keys for cloud profiles. Hardware purchase deferred.
- **Agent framework**: the public API must never leak the underlying agent framework's types, so it stays swappable. This is both wrapper hygiene and dependency-risk mitigation.
- **Privacy**: no accounts, no telemetry, no mandatory cloud. Offline mode must be *verifiable by the user*, not merely claimed.
- **Licensing**: Apache-2.0 for the framework (maximizes reuse); the app may match or go AGPL for capture-resistance. DCO, no CLA.
- **Solo maintainer**: publish the framework as soon as it stands alone — it is a useful, shareable artifact before voice exists, and shipping early is the burnout mitigation.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## The Three Findings That Change The Plan

### 1. The churn argument has REVERSED. LangChain is now the *stable* one.

- **LangChain shipped 1.0 (Oct 2025) with an explicit policy: no breaking changes to the public API until 2.0.** It has held that for ~9 months. (I chased down a scary forum thread claiming `create_agent` was deleted in a 1.1.0 minor — it was a stale virtualenv, not a removal. The stability promise is intact.)
- **Pydantic AI shipped a breaking 2.0 on 2026-06-23 — three weeks ago.** It removed `MCPServerStdio`/`MCPServerSSE`/`MCPServerStreamableHTTP`, and moved `instrument=`, `mcp_servers=`, `prepare_tools=`, `history_processors=` off the `Agent()` constructor into a new "capabilities" primitive. And it **shortened its own no-breaking-change window from six months to three**, on the stated rationale that "the field moves fast enough that committing further out means committing to decisions that fit today."

### 2. Kokoro is disqualified. It has no Hebrew **and no Russian**.

### 3. Hebrew collapses both the TTS *and* the STT decision tree to exactly one option each.

| Engine | Hebrew? | Verdict |
|---|---|---|
| **STT** — Parakeet TDT 0.6b v3 | ❌ (25 *European* langs) | Disqualified |
| **STT** — Canary-1b-v2 | ❌ (25 European langs) | Disqualified |
| **STT** — distil-whisper | ❌ (English only) | Disqualified |
| **STT** — **Whisper large-v3 / turbo** | ✅ **(99 langs incl. `he`)** | **The only survivor** |
| **TTS** — Kokoro-82M | ❌ (no `he`, no `ru`) | Disqualified |
| **TTS** — XTTS-v2 | ❌ (17 langs, no `he`) + non-commercial license | Disqualified |
| **TTS** — Piper | ❌ (per-language models = the rejected approach) | Disqualified as primary |
| **TTS** — **Chatterbox Multilingual V3** | ✅ **(23 langs incl. `he`, `ru`, `es`, `en`)** | **The only survivor** |

## Recommended Stack

### Core Technologies

| Technology | Version (verified 2026-07-13) | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | **3.12** | Runtime | Every core dep requires ≥3.10. 3.12 is the sweet spot: 3.13 still has wheel-availability risk across the torch/audio-ML chain. Pin it. |
| **LangChain** | **1.3.13** (2026-07-10) | Provider loading, tools, callbacks | Stability policy through 2.0; unmatched provider breadth; **callbacks are the best-fit mechanism in any framework for draining runs into your own SQLite**. MIT. |
| **LangGraph** | **1.2.9** (2026-07-10) | Agent runtime / loop | Where LangChain's agent dev actually lives. `interrupt()` + checkpointer implements your **`confirm` permission tier** nearly for free. MIT. |
| **langchain-mcp-adapters** | **0.3.0** (2026-06-10) | MCP client | Official (langchain-ai org), MIT. ⚠️ Still `0.x` — the weakest link in the LangChain case. See risks. |
| **Chatterbox Multilingual V3** (`chatterbox-tts`) | **0.1.7** (2026-03-26) | **TTS** | **The only open multilingual TTS covering en+ru+he+es in ONE model.** MIT. 500M. Cross-language voice cloning = one voice identity across all 4 languages, which is exactly your "no voice switching" rule. |
| **faster-whisper** | **1.2.1** (2025-10-31) | **STT** | Whisper large-v3-turbo on CTranslate2. Whisper is the **only** family with Hebrew. MIT. |
| **Silero VAD** (`silero-vad`) | **6.2.1** (2026-02-24) | VAD / end-of-speech | MIT, 9.5k★, actively maintained (pushed 2026-07-03). Beats WebRTC VAD decisively on noise robustness. |
| **openWakeWord** | **0.6.0** (2024-02-11) | Wake word | Best community-trainable Python option — but ⚠️ **semi-dormant**. See risks. Apache-2.0. |
| **Ollama** (`ollama` py client) | **0.6.2** (2026-04-29) | Local LLM serving | The one your users can actually install. MIT. |
| **FastAPI** | **0.139.0** (2026-07-01) | Config API (REST + WS) | Native async, WebSocket, Pydantic-native. Confirmed as assumed. |
| **Pydantic** | **2.13.4** (2026-05-06) | Config schema/validation | Confirmed as assumed. YAML → validated config tree. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uvicorn` | 0.51.0 | ASGI server | Serve FastAPI. LAN-bind only. |
| `sounddevice` | 0.5.5 (2026-01-23) | Async audio I/O | **Use this, not PyAudio** — PyAudio's last release was 2023-11 and it's a fragile PortAudio binding. `sounddevice` gives you a clean callback/stream API. |
| `zeroconf` | 0.150.0 (2026-06-22) | mDNS announcement | Device discovery for the Electron app. Pure-Python, async API. |
| `aiosqlite` | 0.22.1 (2025-12-23) | SQLite trace store | Async wrapper over stdlib `sqlite3`. Keep the trace store **schema-first raw SQL** — do not drag in an ORM for an append-mostly event log. |
| `langchain-ollama` | 1.1.0 | Ollama provider | Local model profiles. |
| `langchain-anthropic` | 1.4.8 | Anthropic provider | Cloud model profiles. |
| `httpx` | latest | Async HTTP | OpenAI-compatible arbitrary endpoints; HA tool package. |
| `whisper.cpp` / `mlx-whisper` (0.4.3) | — | **Mac dev-harness STT** | ⚠️ **CTranslate2 (faster-whisper) has no Metal/Apple-GPU backend — it is CPU-only on your Mac.** For a tolerable dev loop use whisper.cpp (Metal+CoreML) or `mlx-whisper`. Your pluggable STT interface absorbs this. |
| `sherpa-onnx` | — (13.5k★, pushed 2026-07-13) | **Escape hatch** | One ONNX runtime for STT+TTS+VAD+keyword-spotting, CPU-first, Apache-2.0, extremely active. **This is your Plan B if the Chatterbox compute cost proves fatal on target hardware.** |

### Desktop App

| Tool | Version | Notes |
|------|---------|-------|
| Electron + TypeScript + React | current | As specified. No state beyond device tokens. |
| **Vite** | current | Build tool. Use `electron-vite`. |
| **electron-builder** | current | Packaging/distribution. |
| TanStack Query | current | Server-state cache against the device REST API — the device is the source of truth, so you want a *cache*, not a store. Avoids Redux entirely. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **uv** | Package/venv management | The 2026 default. Fast, lockfile-based. Use `hatchling` as the build backend. |
| **pytest** 9.1.1 + `pytest-asyncio` | Test | Golden tests for Module 1 with a fake model — no hardware, CI-safe (matches your `02-core-software.md` plan). |
| **ruff** | Lint + format | Replaces black/flake8/isort. |
| **mypy** or **ty** | Type checking | Enforces the "public API never leaks framework types" rule *mechanically* — see below. |

## Decision 1: The Agent Framework

### Scored against YOUR feature list (not generic praise)

| Requirement | LangChain 1.3 + LangGraph 1.2 | Pydantic AI 2.9 | Strands 1.47 / OpenAI Agents 0.18 |
|---|---|---|---|
| Provider-agnostic model loading (Ollama / OpenAI-compat / Anthropic / arbitrary) | ✅ **Built-in.** `init_chat_model("ollama:qwen3")` is a *string → model* factory — maps 1:1 onto a YAML model profile. Widest provider set. | ✅ Built-in. Core ships OpenAI/Anthropic/Google; **Bedrock/Groq/Mistral are now opt-in extras in v2**. | ✅ Built-in (Strands). ⚠️ OpenAI Agents is OpenAI-centric. |
| **Ordered fallback chains** | ✅ **Built-in, twice.** `ModelFallbackMiddleware` (agent-level, v1) + `.with_fallbacks()` (runnable-level). | ✅ **Built-in, and more elegant.** `FallbackModel(default, *fallbacks, fallback_on=...)` — `fallback_on` takes exception *and response* predicates, so "local overloaded" is expressible. | ⚠️ Hand-rolled / partial. |
| Tool registry + clean user decorator | ✅ `@tool` | ✅ `@agent.tool` / `Toolset` | ✅ `@tool` |
| **MCP client** | ⚠️ **Separate `0.x` package** (`langchain-mcp-adapters` 0.3.0). Official + MIT + active, but 0.x for a *core user-facing feature*. | ✅ **In core.** `pydantic_ai.mcp.MCPToolset`. **Best in class.** (But v2 just renamed the API.) | ✅ In core (both). |
| **Full observability → OUR SQLite, NO cloud** | ✅ **Best fit, by a clear margin.** `AsyncCallbackHandler` is purpose-built: `on_llm_start` (prompts), `on_llm_new_token`, `on_tool_start/end` (args **and** results), token usage, timings — all in-process, typed, **zero LangSmith**. | ✅ Possible, **more indirection.** Emits **OTel spans**; you write a custom in-process `SpanExporter` and parse `gen_ai.*` semantic-convention attributes. No Logfire cloud required. Structured `all_messages()` + `usage()` help. | ⚠️ OTel-based, similar to Pydantic AI. |
| Streaming tokens (mandatory, feeds TTS) | ✅ `astream` / `astream_events` | ✅ `run_stream` / `agent.iter()` | ✅ |
| Async-native | ⚠️ Async is **complete but retrofitted** (sync-first lineage, `ainvoke`/`astream` everywhere). | ✅ **Async-native by design.** Cleanest fit for your async audio pipeline. | ✅ |
| **`confirm` permission tier** (ask out loud before executing) | ✅ **LangGraph `interrupt()` + checkpointer.** Battle-tested human-in-the-loop pause/resume. This is a *free* implementation of a headline feature. | ✅ Deferred/approval tools exist. Less mileage. | ⚠️ Varies. |
| **API stability history** | ✅ **1.0 → no breaking changes until 2.0. Held ~9 months.** | ❌ **Broke at 2.0 three weeks ago (2026-06-23), AND shortened its stability window 6mo → 3mo.** | ⚠️ Strands at `1.47` (fast minors). OpenAI Agents still `0.18.x` — pre-1.0. |
| Maintenance health | 141,678★, pushed today. LangGraph 37k★. | 18,487★, pushed today. Healthy, smaller. | Strands 6.5k★ (AWS). OpenAI Agents 27.9k★. |

### Recommendation: **LangChain 1.3 + LangGraph 1.2** — confidence **MEDIUM** (it is close; spike it)

- LangChain callbacks fail to cleanly surface **MCP tool call args + results** (they route through the adapter package, which is `0.x`).
- Token counts come back `None` for Ollama (this is a known rough edge across frameworks — **verify against your actual local provider**).
- `langchain-mcp-adapters` proves flaky under real MCP servers.

### The constraint that makes this decision cheap

- All LangChain imports confined to a single `paaf/_engine/` package. Nothing else in the codebase may import `langchain*`.
- Add a lint rule (ruff `flake8-tidy-imports` `banned-api`) that **fails CI** if `langchain` is imported outside `paaf/_engine/`.
- Public API returns only your dataclasses/Pydantic models (`ModelProfile`, `ToolSpec`, `TraceEvent`, …).
- **A thin in-house loop over provider SDKs.** You'd be hand-rolling tool-call mechanics, streaming, retries, MCP, and fallbacks — that is the 80% `PROJECT.md` explicitly decided not to rebuild.
- **OpenAI Agents SDK** — still `0.18.x` (pre-1.0) and OpenAI-gravitational. Wrong for a provider-neutral, local-first product.
- **Semantic Kernel** (1.44.0) — healthy, but Microsoft/enterprise-oriented and .NET-first in spirit. No advantage here.
- **Strands Agents** (1.47.0, Apache-2.0, AWS) — genuinely decent and worth a look, but a smaller ecosystem with no feature that beats the top two for this use case.

## Decision 2: TTS — and the honest Hebrew answer

### The scored table

| Engine | Languages | en/ru/he/es in ONE model? | License | Size | Streaming | CPU-viable? | Verdict |
|---|---|---|---|---|---|---|---|
| **Chatterbox Multilingual V3** | 23 incl. **he, ru, es, en** | ✅ **YES — the only one** | **MIT** | 500M | ⚠️ sentence-chunked | ❌ GPU strongly preferred | ✅ **RECOMMENDED** |
| Chatterbox-Turbo | **English only** | ❌ | MIT | 350M | ✅ built for low latency | ✅ better | Optional English-only fast profile |
| Kokoro-82M | en (+ja/zh/es/fr/hi/it/pt via misaki) | ❌ **no `he`, no `ru`** | Apache-2.0 | 82M | ✅ | ✅ excellent | ❌ **DISQUALIFIED** |
| XTTS-v2 | 17 (has ru/es, **no he**) | ❌ | ❌ **CPML — non-commercial** | ~750M | ⚠️ | ❌ | ❌ **DISQUALIFIED (license + no Hebrew)** |
| Coqui TTS | — | ❌ | MPL-2.0 | — | — | — | Original repo **dead** (last push 2024-08). Fork `idiap/coqui-ai-TTS` 0.27.5 is alive but inherits XTTS's gaps. |
| Piper (`piper1-gpl` 1.4.2) | per-language models | ❌ **by construction** | ❌ **GPL-3.0** | ~20M | ✅ | ✅ excellent | ❌ Rejected approach + `rhasspy/piper` is **ARCHIVED** |

### Recommendation: **Chatterbox Multilingual V3** — confidence **MEDIUM-LOW on quality, HIGH on "it's the only option"**

### But here is the honest part, and you must read it

### The Hebrew fallback ladder — state this plainly in your docs

| Fallback | What it costs you |
|---|---|
| **A. Cloud TTS profile for Hebrew** (Azure / Google / ElevenLabs — all have strong Hebrew) | Breaks the offline promise **for Hebrew output only**. Because your TTS engine interface is pluggable, this is a *config choice*, not an architecture change — and offline-mode enforcement would simply refuse it. This is the most honest option: the user *chooses* the tradeoff, with full visibility. **This is the design your architecture already supports.** |
| **B. Ship Hebrew as explicitly "experimental / degraded"** | Honesty preserved, quality poor. Acceptable for a v1. |
| **C. Disable Hebrew TTS; STT still understands it** | The assistant *understands* Hebrew and replies in English. Ugly, but coherent — and notably, this is what many real bilingual households do anyway. |
| **D. Per-language engine switching** | **Explicitly rejected by the project.** Don't reopen it — it breaks on code-switched sentences anyway, which is the exact failure it was rejected for. |

### Streaming

## Decision 3: STT

### Recommendation: **faster-whisper 1.2.1** running **Whisper large-v3-turbo** — confidence **HIGH**

- Use **`large-v3-turbo`** (MIT) as default — the distilled decoder is dramatically faster with modest multilingual loss. Keep `large-v3` (Apache-2.0) as a quality profile.
- **Apple Silicon reality: CTranslate2 has NO Metal/GPU backend. faster-whisper is CPU-only on your Mac.** For a tolerable dev loop, use **whisper.cpp** (Metal + CoreML, 51.7k★, pushed 2026-07-11) or **`mlx-whisper` 0.4.3**. Your pluggable STT interface is what makes this a non-event — this is a good early proof that the interface earns its keep.
- Linux target: faster-whisper on CUDA, or CPU with `int8` quantization.

### ⚠️ Honest correction to `PROJECT.md`

## Decision 4: Wake Word

### Recommendation: **openWakeWord 0.6.0** — confidence **MEDIUM** (works, but flag the risk)

- ✅ Apache-2.0, community-trainable custom wake words (your "cheap premium touch" is real).
- ⚠️ **Maintenance concern, verified:** PyPI release frozen at **0.6.0 since 2024-02-11**. Last commit **2025-12-30**. 123 open issues. Solo maintainer (`dscripka`). It is **not abandoned** — Oct 2025 saw a Python 3.10+ bump and a tflite→`ai-edge-litert` migration — but it is clearly in low-energy maintenance mode.
- Given your project's own **"Willow proved solo-maintainer risk is real"** lesson: **keep the wake-word engine behind a swappable interface** (which your design already does) and don't build anything load-bearing on openWakeWord internals.
- **Alternatives:** `sherpa-onnx` keyword-spotting (Apache-2.0, 13.5k★, pushed *today*) is the strongest escape hatch. Porcupine is excellent but **proprietary** — wrong for this project's values. microWakeWord is ESP32/microcontroller-targeted, not a fit for a Linux Python app.

## Decision 5: VAD / Barge-in

### Recommendation: **Silero VAD 6.2.1** — confidence **HIGH**

## Decision 6: Local LLM Serving

### Recommendation: **Ollama** (`ollama` 0.6.2 client) — confidence **HIGH** for Ollama, **MEDIUM** for the model family

- **Ollama is right for the product**, not because it's the fastest, but because **your users can install it**. Self-hosters already run it. It exposes an OpenAI-compatible endpoint, so it costs you nothing in provider abstraction. 176k★.
- **Model selection criterion is TOOL-CALLING QUALITY, not chat quality.** This is the thing people get wrong. A home assistant that can't reliably emit a well-formed tool call is useless no matter how well it writes.
- **Model family:** the **Qwen3 family sized to available VRAM** remains the sane default (strong tool-calling). Live check of the Ollama library today shows `qwen3`, `qwen3.5`, `gemma3`, `gemma4` all present. **[UNVERIFIED — MEDIUM]**: I could not confirm the *current* community consensus default (web search hit its session limit); the Ollama "popular" sort is lifetime-cumulative and therefore a lagging indicator. **Re-check `r/LocalLLaMA` at implementation time and benchmark tool-call reliability yourself — do not take the roadmap's word or mine.**
- **llama.cpp**: more control, worse ergonomics; it's what Ollama runs on. Don't adopt directly unless you need something Ollama won't expose.
- **vLLM**: server-grade throughput for concurrent users. **Overkill for a single-user home assistant** — wrong tool.
- **LM Studio**: GUI-first, not a service. Wrong for a headless Linux daemon.

## Installation

# Package/venv management (2026 default)

# Core framework — agent engine

# Core framework — voice

# Embedded app

# Mac dev harness only (CTranslate2 has no Metal backend)

# Dev

# Desktop app

## What NOT to Use, and Why

| Rejected | Why |
|---|---|
| **Kokoro** | **No Hebrew, no Russian.** Fails 2 of 4 required languages. Overturns `project-docs/02`. |
| **XTTS-v2 / Coqui** | No Hebrew **and** the model is **CPML (non-commercial)** — a licensing landmine inside an Apache-2.0 framework. Upstream repo dead since 2024-08. |
| **Piper (as primary)** | Per-language models = the explicitly rejected approach. Also `rhasspy/piper` is **ARCHIVED** and the successor is **GPL-3.0**. |
| **Parakeet / Canary / distil-whisper** | **No Hebrew.** Non-starters, regardless of their (real) speed advantages. |
| **WebRTC VAD** | Superseded by Silero on every axis. |
| **PyAudio** | Stale (last release 2023-11). Use `sounddevice`. |
| **Porcupine (wake word)** | Proprietary. Contradicts the project's founding commitment. |
| **vLLM / LM Studio** | Wrong shape for a single-user headless home daemon. |
| **OpenAI Agents SDK** | Pre-1.0 (`0.18.x`) and OpenAI-gravitational. |
| **An in-house agent loop** | Rebuilds the 80% `PROJECT.md` decided not to rebuild. |
| **Redux in the Electron app** | The device is the source of truth. You need a server-state *cache* (TanStack Query), not a client store. |
| **An ORM for the trace store** | It's an append-mostly event log. Raw SQL + `aiosqlite`. |

## Phase-0 Spike: What To Measure

| # | Spike | Measure exactly this | If it fails |
|---|---|---|---|
| **1** | **🔴 Chatterbox code-switching** | Feed 20 real mixed-language sentences (en+ru+he+es, mixed *within* the sentence). Vary `language_id`. Does mixed script render intelligibly, or does it garble/skip the non-tagged language? | **This is the project's highest-risk unknown.** If it fails, your "founding property" is unimplementable as designed — go to the Hebrew fallback ladder and reconsider the whole language promise *before* building. |
| **2** | **🔴 Chatterbox latency & hardware** | Time-to-first-audio for ONE short sentence on: (a) M-series Mac MPS, (b) CPU-only, (c) a consumer GPU. | If CPU is nowhere near ~1.5–2s, **your hardware budget just changed.** Do this before buying the mini-PC. Fall back to `sherpa-onnx`. |
| **3** | **🔴 Hebrew TTS quality** | Native-ear judgement (you have one). Is Chatterbox Hebrew *usable*, or embarrassing? | Trigger the fallback ladder. Decide A/B/C **now**, not at launch. |
| **4** | 🟠 Whisper code-switched STT | WER on the same 20 mixed sentences. Does it lock to one language? | Correct the `PROJECT.md` "STT is a non-issue" claim before you ship it in a README. |
| **5** | 🟠 LangChain callback → SQLite | Can `AsyncCallbackHandler` capture prompts + model choice + **MCP** tool args/results + token counts + timings, with **zero** LangSmith? **Do token counts come back non-`None` for Ollama?** | If MCP traces are opaque → **switch to Pydantic AI**. This is the falsification test for Decision 1. Cheap to run; run it early. |
| **6** | 🟠 LangGraph `interrupt()` → `confirm` tier | Can a tool pause, surface a confirmation to the WebSocket channel, and resume? | If awkward, the `confirm` tier gets hand-rolled — costly but survivable. |
| **7** | 🟡 Barge-in + AEC | Does Silero VAD false-trigger on the assistant's own speaker output? | You need acoustic echo cancellation. Budget for it — it's easy to forget and painful to retrofit. |

## Confidence Assessment

| Claim | Confidence | Basis |
|---|---|---|
| All versions, licenses, release dates | **HIGH** | Pulled live from PyPI / GitHub / HF APIs on 2026-07-13 |
| Language coverage (who has Hebrew) | **HIGH** | HuggingFace model-card metadata, read directly |
| Chatterbox is the only viable multilingual TTS | **HIGH** | Follows deductively from verified language lists |
| **Chatterbox Hebrew *quality*** | **LOW** | ⚠️ Cannot be established by reading. **Spike #3.** |
| **Chatterbox intra-sentence code-switching** | **LOW** | ⚠️ Not a documented feature of *any* engine. **Spike #1.** |
| Whisper is the only viable STT | **HIGH** | Verified language lists |
| Whisper code-switching is imperfect | **MEDIUM** | Architectural reasoning (per-window language token) + literature. **Spike #4.** |
| LangChain stability policy reversal | **HIGH** | Official 1.0 policy + verified that the `create_agent` removal scare was a stale venv |
| Pydantic AI v2 broke + shortened window | **HIGH** | Pydantic's own v2 article, 2026-06-23 |
| LangChain recommendation | **MEDIUM** | Close call. Deliberately falsifiable via **Spike #5**. |
| openWakeWord semi-dormancy | **HIGH** | Commit log + PyPI dates, read directly |
| Current Ollama model default | **MEDIUM** ⚠️ | **[UNVERIFIED]** — web search hit session limit. Re-check at implementation time. |
| Piper archived / now GPL-3.0 | **HIGH** | GitHub API: `rhasspy/piper` `archived=true`; `piper1-gpl` = GPL-3.0 |

## Sources

- PyPI JSON API — versions, licenses, release dates, `requires_python` (queried 2026-07-13)
- GitHub API — stars, last-push, archived status, licenses, commit logs (queried 2026-07-13)
- HuggingFace Hub API — model-card language metadata, licenses, downloads (queried 2026-07-13)
- [Chatterbox README (resemble-ai/chatterbox)](https://github.com/resemble-ai/chatterbox) — V3, 23-language list, `language_id` API, PerTh watermarking
- [Pydantic AI v2: capabilities, a leaner core, and the Harness](https://pydantic.dev/articles/pydantic-ai-v2) — v2 breaking changes, 6mo→3mo stability window
- [LangChain and LangGraph reach v1.0](https://blog.langchain.com/langchain-langgraph-1dot0/) + [Release policy](https://docs.langchain.com/oss/python/release-policy) — no breaking changes until 2.0
- [LangChain forum: "create_agent no longer exists in 1.1.0"](https://forum.langchain.com/t/create-agent-no-longer-exists-in-langchain-agents-v1-1-0/2350) — resolved as stale venv, **not** a breaking change
- [pydantic_ai.models.fallback (FallbackModel)](https://ai.pydantic.dev/api/models/fallback/) — ordered chains, `fallback_on` predicates
- [LangChain ModelFallbackMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_fallback/ModelFallbackMiddleware) and [RunnableWithFallbacks](https://reference.langchain.com/python/langchain-core/runnables/fallbacks/RunnableWithFallbacks)
- [LangChain Callbacks reference](https://reference.langchain.com/python/langchain_core/callbacks/) — `BaseCallbackHandler` / `AsyncCallbackHandler`
- [SigNoz: Pydantic AI observability via OpenTelemetry](https://signoz.io/docs/pydantic-ai-observability/) — confirms self-hosted/no-cloud OTel path
- [coqui/XTTS-v2 model card](https://huggingface.co/coqui/XTTS-v2) — CPML non-commercial license

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| find-skills | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill. | `.agents/skills/find-skills/SKILL.md` |
| frontend-design | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults. | `.agents/skills/frontend-design/SKILL.md` |
| startup-ideation | Help users generate and evaluate startup ideas. Use when someone is brainstorming business ideas, trying to find a startup concept, evaluating whether an idea is worth pursuing, or looking for unique market opportunities. | `.agents/skills/startup-ideation/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
