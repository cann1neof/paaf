# Phase 8: Real Engines & Live Audio - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-09
**Phase:** 08-real-engines-live-audio
**Areas discussed:** Pluggable STT/TTS Engine Architecture & Raspberry Pi support, Model Download Consent & CLI, Hardware Audio I/O & AEC Tap, Wake Word & VAD Execution, Engine Warmup Gate

---

## Pluggable STT/TTS Engine Architecture & Raspberry Pi Support

| Option | Description | Selected |
|--------|-------------|----------|
| `faster-whisper` only | Standardize purely on CTranslate2 backend | |
| `whisper.cpp` only | Standardize purely on GGML C++ backend | |
| Dynamic Engine Registry & Dual Support | Implement `paaf_voice.engines` registry supporting both `WhisperCppSTT` (for Raspberry Pi ARM) and `FasterWhisperSTT` (for Mac/x86/CUDA), configured in YAML without code changes | ✓ |

**User's choice:** Dynamic Engine Registry + Dual Engine Support out of the box.
**Notes:** User emphasized Raspberry Pi compatibility as a key target while requiring future-proof engine pluggability so new STT/TTS models can be integrated via simple YAML config settings or a class decorator without touching framework primitives.

---

## Model Download Consent & Explicit CLI (PRIV-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Silent background download | Auto-fetch models on first turn | |
| Explicit CLI & Consent Gate | `paaf voice download-models` and `list-models` CLI commands with `ModelMissingError` safeguards on missing weights | ✓ |

**User's choice:** Explicit CLI commands enforcing PRIV-06.

---

## Live Audio Hardware I/O & AEC Tap

| Option | Description | Selected |
|--------|-------------|----------|
| `sounddevice` AudioSource/Sink | 16kHz framing, PortAudio device selection via `paaf voice list-devices` CLI | ✓ |
| Fine-tuned AEC speaker resampler | Resample reference tap on the hot path | Deferred to v2 |

**User's choice:** Standardize on `sounddevice` with `paaf voice list-devices` CLI. Echo cancellation tap resampler tuning deferred to v2.

---

## Wake Word & VAD Continuous Sensing

| Option | Description | Selected |
|--------|-------------|----------|
| `openWakeWord` + `Silero VAD` | Built-in & custom ONNX wake word models + continuous VAD with dual thresholding during playback | ✓ |

**User's choice:** Approved.

---

## Engine Warmup & System Readiness (VOICE-10)

| Option | Description | Selected |
|--------|-------------|----------|
| Startup Warmup Sequence | Load model weights and run a 20ms silence dummy inference pass across all engines before marking device ready | ✓ |

**User's choice:** Approved.

---

## Agent Discretion

- CLI progress bar styling for model downloads (`rich` / `tqdm`).
- Internal queue buffer sizes for streaming audio channels.

---

## Deferred Ideas

- Fine-grained echo cancellation resampler tuning on `AudioSink.get_reference_tap()` deferred to v2 / real hardware evaluation.
