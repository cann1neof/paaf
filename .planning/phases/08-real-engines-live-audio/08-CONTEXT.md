# Phase 8: Real Engines & Live Audio - Context

**Gathered:** 2026-08-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 connects real machine learning models and live audio hardware to the `paaf-voice` port protocols established in Phase 7 (`STTPort`, `TTSPort`, `WakeWordPort`, `VADPort`, `AudioSource`, `AudioSink`). It delivers real Whisper, real Chatterbox / Dicta-ONNX, real wake word, and real VAD behind a pluggable engine registry that supports both low-resource ARM devices (Raspberry Pi 4/5) and high-performance Mac/x86 setups out of the box, with explicit CLI model management complying with PRIV-06.

</domain>

<decisions>
## Implementation Decisions

### Strategic Pluggable Engine Architecture
- **D-01:** Implement `paaf_voice.engines` registry with decorator-based registration (`@register_stt_engine("name")`, `@register_tts_engine("name")`) — **Reversibility:** costly — ensures users can swap STT/TTS engines in YAML configuration (`engine: "whisper_cpp"` vs `engine: "faster_whisper"`) without rewriting interfaces or core turn loop logic, future-proofing PAAF for upcoming local AI breakthroughs.
- **D-02:** Ship dual real STT engine adapters out of the box — **Reversibility:** costly — `WhisperCppSTT` (`whisper.cpp` GGML quantized models) for Raspberry Pi 4/5 and low-resource ARM SBCs (~150-300MB RAM), and `FasterWhisperSTT` (`faster-whisper` CTranslate2) for Mac (MPS), CUDA, and desktop x86 CPUs.
- **D-03:** Voice YAML configuration tree cleanly binds engine selection (`engine`), model path (`model`), compute precision (`compute_type: "int8"`), and hardware target (`device: "auto"`) — **Reversibility:** reversible — allows zero-code switching between engines.

### Model Download & Explicit Consent CLI (PRIV-06)
- **D-04:** Implement `paaf voice download-models` and `paaf voice list-models` CLI commands — **Reversibility:** costly — enforces requirement PRIV-06 by requiring explicit user consent for multi-hundred megabyte model downloads before first run, with zero background auto-downloads.
- **D-05:** Missing model weights at engine startup trigger a clean `ModelMissingError` — **Reversibility:** reversible — provides actionable CLI instructions specifying which command to execute rather than failing with silent crashes or downloading weights silently.

### Live Audio Hardware I/O & Device Selection
- **D-06:** Standardize on `sounddevice` (PortAudio wrapper) for real `AudioSource` and `AudioSink` implementations — **Reversibility:** costly — provides cross-platform live mic and speaker streaming.
- **D-07:** Implement `paaf voice list-devices` CLI command — **Reversibility:** reversible — enumerates hardware input/output audio indices and names, allowing optional YAML configuration overrides (`input_device`, `output_device`).
- **D-08:** Internal PCM framing operates at 16kHz 16-bit mono in 20ms chunks (320 samples) for input/VAD/STT, with `soxr` dynamic resampling in `AudioSink` for Chatterbox TTS playback — **Reversibility:** reversible — maintains fixed internal timing standards across engines.

### Wake Word & VAD Execution
- **D-09:** `OpenWakeWordEngine` implements `WakeWordPort` with support for built-in models (`hey_jarvis`, `alexa`) and custom ONNX model file paths in YAML (`model: "/path/to/custom.onnx"`) — **Reversibility:** reversible — supports flexible wake word configuration.
- **D-10:** `SileroVADEngine` implements `VADPort` with continuous background sensing — **Reversibility:** reversible — runs continuously even during audio playback, using dual thresholds (`speech_threshold=0.65` during TTS playback vs `0.50` when idle) to prevent acoustic speaker bleed false-triggers.

### Engine Warmup & Readiness Gate (VOICE-10)
- **D-11:** Every real engine implements `warmup()` — **Reversibility:** costly — pre-loads model weights into memory/RAM/VRAM and executes a 20ms silence dummy inference pass at startup before advertising device ready state, eliminating cold-start latency on the first real user turn.

### Agent Discretion
- Exact CLI progress bar styling (`rich` / `tqdm`) for `paaf voice download-models` — the agent has full discretion.
- Internal buffer queue sizes for `sounddevice` streams — the agent has full discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Requirements
- `.planning/ROADMAP.md` § Phase 8 — Real Engines & Live Audio goal, scope, and success criteria
- `.planning/REQUIREMENTS.md` — Requirements VOICE-03, VOICE-04, VOICE-05, VOICE-07, VOICE-08, VOICE-09, VOICE-10, VOICE-12, PRIV-06
- `ARCHITECTURE.md` — Package boundaries (`paaf-voice`), import rules, and interface contracts

### Prior Phase Context
- `.planning/phases/07-paaf-voice-ports-fakes/07-CONTEXT.md` — Established `paaf-voice` ports (`STTPort`, `TTSPort`, `WakeWordPort`, `VADPort`, `AudioSource`, `AudioSink`), test doubles (`paaf_voice.testing`), and `SentenceAggregator`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/paaf-voice/src/paaf_voice/ports.py` — Core `Protocol` definitions for STT, TTS, Wake Word, VAD, AudioSource, and AudioSink
- `packages/paaf-voice/src/paaf_voice/testing/` — Shipped test fakes (`FakeSTT`, `FakeTTS`, `FakeWakeWord`, `FakeVAD`, `FakeAudioSource`, `FakeAudioSink`)
- `packages/paaf-core/src/paaf_core/config/` — Typed atomic configuration schema and YAML parsing framework

### Established Patterns
- Python `typing.Protocol` with `@runtime_checkable` for port interfaces
- Zero background telemetry and explicit CLI user consent for network/download operations
- Unified CLI subcommand structure (`paaf <subcommand>`)

### Integration Points
- `packages/paaf-voice/src/paaf_voice/engines/` — New package directory for real engine implementations and registry
- `packages/paaf-voice/src/paaf_voice/cli/` — CLI subcommands (`paaf voice download-models`, `list-models`, `list-devices`)

</code_context>

<specifics>
## Specific Ideas

- **Raspberry Pi Compatibility:** `whisper.cpp` GGML single-file quantized models (e.g. `ggml-base.bin`) must run out of the box on low-RAM ARM SBCs.
- **Future-Proofing:** Adding a new STT/TTS engine in the future should only require decorating a class implementing `STTPort` / `TTSPort` with `@register_stt_engine` without modifying core PAAF primitives.

</specifics>

<deferred>
## Deferred Ideas

### Fine-tuned AEC Speaker Resampling
- Fine-grained echo cancellation resampler tuning on `AudioSink.get_reference_tap()` deferred to v2 / later real-hardware evaluation when hardware AEC is integrated.

</deferred>

---

*Phase: 08-Real Engines & Live Audio*
*Context gathered: 2026-08-09*
