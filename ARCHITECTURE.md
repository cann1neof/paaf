<!-- SPDX-License-Identifier: Apache-2.0 -->

# PAAF Architecture

This document is the map for an outsider: what the pieces are, where things
live, and the rules that keep the pieces swappable. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) to build and test, and
[`DECISIONS.md`](DECISIONS.md) for the commitments the architecture exists
to protect.

## The shape in one paragraph

PAAF is delivered as **a framework** (a Python package set the user owns and
can verify) and, later, **two apps** (an embedded assistant process and an
Electron desktop control panel). The framework is a
[uv](https://docs.astral.sh/uv/) **workspace monorepo** of five
independently-versioned packages under `packages/`. Everything the user
configures — which model, which skills, which tools, which persona, what the
assistant does while it thinks — is a user-facing concept, not code, backed
by a validated config tree and an encrypted secret store, with every run
recorded locally and **nothing ever leaving the device**.

## The five framework packages

| Package | Path | State | Responsibility |
|---------|------|-------|----------------|
| **paaf-core** | `packages/paaf-core` | **real** | Config (one validated YAML tree, atomic writes, revision/conflict, reload tiers), the encrypted `SecretStore`, and the network-endpoint declaration interface that makes offline enforcement architectural. |
| **paaf-trace** | `packages/paaf-trace` | **real** | Local append-mostly SQLite trace store (WAL, single writer off the audio hot path) recording prompts, model, tool calls with args/results, timings, token counts, and `time_to_first_audio`. Nothing in it ever leaves the device. |
| **paaf-llm** | `packages/paaf-llm` | **real** | LLM management (model profiles, tools, persona, behaviors, mesh router, observer supervisor, spoken confirmation gates). The agent framework lives behind the port in `paaf_llm._engine` and never leaks. |
| **paaf-voice** | `packages/paaf-voice` | **real** | Streaming STT/TTS, wake word, VAD, audio I/O hardware drivers, sentence aggregator, Engine Registry, and explicit model management CLI (PRIV-06). Real engine suite lands in Phases 7 & 8. |
| **paaf-session** | `packages/paaf-session` | **real** | The turn orchestrator (wake → capture → transcribe → think → speak, barge-in). Owns what requires knowing that time is passing and audio is playing. |

All five framework packages carry full implementations with **431 workspace tests passing** (including **70/70 voice package tests**).

### The two apps are deferred (D-07)

The **embedded app** (a single Linux-service process wiring the session to
real audio devices, exposing a LAN-only REST + WebSocket API, mDNS
announcement, offline enforcement) and the **desktop app** (Electron + React
control panel, holding no state beyond device tokens) are deferred. The workspace root is a *virtual* project (`package = false`) that
ships nothing itself (D-07). App licensing defaults to Apache-2.0.

## Import boundaries — enforced by CI, not by intention

The framework's swappability rests on a few import rules. They are turned
into **build failures** by [import-linter](https://import-linter.readthedocs.io/)
(config in [`.importlinter`](.importlinter), run as `uv run lint-imports`,
gated in CI as FOUND-04). Three contracts:

1. **voice ↔ llm independence** — `paaf_voice` and `paaf_llm` may not import
   each other, in either direction, even indirectly. This is what keeps the
   two modules independently swappable and lets `paaf-llm` be
   `pip install`-ed without pulling in any audio dependency (FOUND-02).
2. **langchain confined to the adapter** — no framework package may import
   `langchain` / `langgraph` / `langchain_core` / `langchain_mcp_adapters`.
   Whitelisted edge
   (`paaf_llm._engine.* -> langchain*`) via `ignore_imports`. This mechanically
   enforces CLAUDE.md's rule that **the public API never leaks framework
   types**, so the agent framework stays replaceable.
3. **no network client in the framework** — no framework package may import
   an outbound HTTP/socket client (`httpx`, `requests`, `aiohttp`, `socket`).
   This supports TRACE-05 / PRIV-02 architecturally: nothing anywhere in the
   framework graph can phone home.

Each contract has a paired **negative control** under `tests/negcontrol/`
that deliberately violates it and proves the check goes red — a check that
cannot fail is not a check.

## Core subsystems (in `paaf-core`)

- **Config** (`paaf_core/config/`) — one YAML tree on disk, validated against
  a typed Pydantic schema on every read and write; writes are atomic
  (temp-file, fsync, rename); a monotonic revision rejects concurrent edits
  with a conflict; keys are classified into **reload tiers** — hot, warm,
  cold, restart-only — and the tier is discoverable (`reload_tiers.py`).
- **Secrets** (`paaf_core/secrets/`) — a pluggable `SecretStore` Protocol
  (set/get/delete/list_keys — names only) with an `EncryptedFileSecretStore`
  backend: Fernet payload + scrypt KDF, the **master key derived from a
  passphrase at boot** (never at rest; only a per-store salt on disk). API
  keys live here, never in the YAML tree, never logged (CORE-04). Audited
  crypto only — no hand-rolled ciphers. See `DECISIONS.md` for the
  passphrase-at-boot decision and its unattended-restart tradeoff.
- **Network endpoints** (`paaf_core/net/`) — every component declares its
  network endpoints through a common interface, so **offline enforcement is
  architectural** (a single place to refuse a non-LAN endpoint) rather than a
  scattered set of ad-hoc checks (CORE-05).

## Trace subsystem (in `paaf-trace`)

A local SQLite store in WAL mode with a **single writer task** fed by a
bounded queue, kept **off the audio hot path** (TRACE-01). It records every
run's prompts, selected model, tool calls with arguments and results,
timings, and token counts (TRACE-02), with `time_to_first_audio` as a
first-class metric (TRACE-03). **Nothing in the trace store ever leaves the
device** (TRACE-05) — this is also why the framework carries no network
client (boundary #3 above). It is an append-mostly event log, so it uses
raw SQL via `aiosqlite`, deliberately **not** an ORM.

## Agent Mesh subsystem (in `paaf-llm`)

Routing in PAAF is model-driven: the currently-awake model chooses, itself, by calling a handoff tool (`transfer_to_<peer>`). There is no rule table anywhere and none can be written in configuration (MESH-01). Three separate mesh concepts exist for distinct purposes:
* **The fallback chain** (`fallback_chain`) provides *resilience* when a provider degrades or times out.
* **The peer graph** (`peers`) enables *handoff on the merits* between complementary domain agents.
* **The home agent** (`default_agent`) acts as the *terminator* when the turn's hop budget is exhausted.

**Two-layer peer enforcement.** Only declared peers are offered to the awake model as handoff tools, and a deterministic runtime guard (`mesh.resolve_handoff`) rejects any handoff target outside the calling agent's declared peers.

**The observer.** The observer is a reserved profile name (`observer`) within the ordinary profile namespace, configurable down to its own system prompt. Its powers are governed by capability removal via its tool grant (`observer_grants`, defaulting to retry-only) rather than a mode flag.

**Spoken Confirmation Gate.** Sensitive operations require explicit vocal user confirmation before execution.

## Voice subsystem (in `paaf-voice`)

The `paaf-voice` package encapsulates speech-to-text, text-to-speech, wake word detection, voice activity detection, and audio hardware drivers behind formal protocol boundaries (`STT`, `TTS`, `WakeWordEngine`, `VADEngine`, `AudioSource`, `AudioSink`).

### Engine Registry (`paaf_voice.engines`)
Engines register themselves with the engine registry via decorators (`@register_stt_engine`, `@register_tts_engine`, `@register_wakeword_engine`, `@register_vad_engine`), making them dynamically discoverable and configurable by name.

### Dual STT Engines
PAAF provides dual STT engine support to scale from low-power edge devices to high-performance workstations:
- **`FasterWhisperSTT`**: Powered by `faster-whisper` and `CTranslate2`. Designed for Mac (Apple Silicon MPS), CUDA GPUs, and high-performance desktop x86 CPUs.
- **`WhisperCppSTT`**: Powered by `pywhispercpp` and `whisper.cpp` GGML quantized models. Optimized for Raspberry Pi 4/5 and low-resource ARM SBCs (~150-300MB RAM footprint).

### Multilingual TTS
- **`ChatterboxTTS`**: Powered by `Dicta-ONNX` / Chatterbox. Supports EN, RU, HE, ES multi-script speech synthesis in a single, unified target voice identity.

### Real Wake Word & VAD
- **`OpenWakeWordEngine`**: Real-time ONNX wake word detection supporting standard models (e.g. `hey_jarvis`) and custom ONNX wake word triggers.
- **`SileroVADEngine`**: Continuous speech sensing utilizing Silero VAD with dual thresholding (0.50 idle threshold / 0.65 playback threshold) to prevent self-triggering during audio output.

### Live Audio Hardware I/O
- **`SoundDeviceAudioSource` & `SoundDeviceAudioSink`**: PortAudio wrappers using `sounddevice` with `soxr` dynamic resampling, precise playhead tracking, and a reference loopback tap for acoustic echo cancellation (AEC).

### Explicit Model Management CLI (PRIV-06)
In adherence to PAAF's privacy directives, **zero background auto-downloads** are permitted. Models must be explicitly requested and cached via the CLI:
- `paaf voice download-models --engine <engine> --model <model>`
- `paaf voice list-models`
- `paaf voice list-devices`

### Engine Warmup Gate (VOICE-10)
All engines implement an asynchronous `warmup()` interface. At boot, engines pre-load weight files into RAM/VRAM and run a 20ms dummy silence inference pass to eliminate cold-start latency on the first voice turn.

## Where things live

```
paaf/
├── LICENSE                     Apache-2.0 (framework)
├── NOTICE                      copyright / attribution / license scope
├── CONTRIBUTING.md             DCO sign-off, conventional commits, semver, test-run
├── ARCHITECTURE.md             this file
├── DECISIONS.md                the durable public record + anti-features + commitments
├── .importlinter               the three FOUND-04 import contracts
├── pyproject.toml              virtual workspace root (offline test defaults)
├── .github/workflows/
│   ├── ci.yml                  lint-imports + offline suite + governance rot-guard
│   └── dco.yml                 DCO sign-off check on PRs
├── tests/
│   ├── test_governance.py      doc-presence + SPDX-header rot-guard
│   └── negcontrol/             deliberate import-boundary violations
└── packages/
    ├── paaf-core/              config, secrets, net  (real)
    ├── paaf-trace/             SQLite trace store    (real)
    ├── paaf-llm/               Module 1 — LLM mgmt   (real)
    ├── paaf-voice/             Module 2 — voice      (real — registry, dual STT, TTS, VAD, wake word, sounddevice I/O)
    │   ├── src/paaf_voice/engines/    Engine Registry, FasterWhisper, WhisperCpp, Chatterbox, OpenWakeWord, SileroVAD
    │   ├── src/paaf_voice/audio/      SoundDeviceAudioSource & SoundDeviceAudioSink
    │   └── src/paaf_voice/cli/        Model & device management CLI commands (PRIV-06)
    └── paaf-session/           turn orchestrator     (real — voice state machine)
```

## Component Diagram

```mermaid
graph TD
    Voice["paaf-voice<br/>(Real Engines & Hardware I/O)"] --> Session["paaf-session<br/>(Turn Orchestrator)"]
    Session --> LLM["paaf-llm<br/>(Engine & Agent Mesh)"]
    LLM --> Core["paaf-core<br/>(Config & Secrets)"]
    LLM --> Trace["paaf-trace<br/>(Local SQLite Store)"]
    Session --> Trace
```

## Data Flow

1. **Audio Capture**: `paaf-voice` `SoundDeviceAudioSource` yields an async stream of `AudioFrame` PCM objects.
2. **Wake Word & VAD**: `OpenWakeWordEngine` listens for wake phrases; `SileroVADEngine.process_frame()` filters speech activity using dual idle/playback thresholds.
3. **STT Transcription**: `STT.transcribe_stream()` (`FasterWhisperSTT` or `WhisperCppSTT`) transcribes audio frames into `STTResult`.
4. **Agent Mesh Processing**: `paaf-llm` routes prompt payloads through model profiles, executing tools governed by `PermissionEngine` and `SpokenConfirmationEngine`.
5. **Voice Synthesis & Playback**: `SentenceAggregator` collects streaming LLM tokens into sentence units, `TTSSanitizer` strips markdown formatting, `ChatterboxTTS.synthesize()` generates audio frames, and `SoundDeviceAudioSink` streams frames to hardware with playhead tracking and AEC reference taps.
6. **Local Telemetry**: `paaf-trace` asynchronously queues and persists prompt payloads, tool execution logs, and TTFA latency metrics to a local SQLite WAL store.

## Key Abstractions

- `paaf_core.config.PaafConfig` (`packages/paaf-core/src/paaf_core/config/schema.py`) — Pydantic-validated `paaf.yaml` configuration schema with atomic writes and reload tier classification.
- `paaf_core.secrets.EncryptedFileSecretStore` (`packages/paaf-core/src/paaf_core/secrets/store.py`) — Encrypted file secret store using Fernet encryption and scrypt key derivation.
- `paaf_llm.mesh.MeshRouter` (`packages/paaf-llm/src/paaf_llm/mesh.py`) — Model-driven handoff router enforcing peer graph boundaries and fallback chains.
- `paaf_llm.confirmation.SpokenConfirmationEngine` (`packages/paaf-llm/src/paaf_llm/confirmation.py`) — Spoken confirmation gate for sensitive tool execution authorization.
- `paaf_voice.engines.EngineRegistry` (`packages/paaf-voice/src/paaf_voice/engines/registry.py`) — Registry for STT, TTS, WakeWord, and VAD engine implementations.
- `paaf_voice.engines.FasterWhisperSTT` (`packages/paaf-voice/src/paaf_voice/engines/faster_whisper.py`) — CTranslate2 / faster-whisper STT engine for Mac/x86 (MPS/CUDA).
- `paaf_voice.engines.WhisperCppSTT` (`packages/paaf-voice/src/paaf_voice/engines/whisper_cpp.py`) — whisper.cpp GGML STT engine optimized for Raspberry Pi / ARM SBCs.
- `paaf_voice.engines.ChatterboxTTS` (`packages/paaf-voice/src/paaf_voice/engines/chatterbox.py`) — Multilingual (EN, RU, HE, ES) Chatterbox TTS engine.
- `paaf_voice.engines.OpenWakeWordEngine` (`packages/paaf-voice/src/paaf_voice/engines/openwakeword.py`) — Real-time ONNX wake word detection engine.
- `paaf_voice.engines.SileroVADEngine` (`packages/paaf-voice/src/paaf_voice/engines/silero_vad.py`) — Silero VAD engine with dual idle/playback thresholding.
- `paaf_voice.audio.SoundDeviceAudioSource` / `SoundDeviceAudioSink` (`packages/paaf-voice/src/paaf_voice/audio/sounddevice_io.py`) — PortAudio live audio hardware drivers with dynamic resampling and AEC reference tap.
- `paaf_voice.aggregator.SentenceAggregator` (`packages/paaf-voice/src/paaf_voice/aggregator.py`) — Multilingual streaming LLM token aggregator with dual character thresholding.
- `paaf_trace.store.TraceStore` (`packages/paaf-trace/src/paaf_trace/store.py`) — Local SQLite WAL trace event store.
