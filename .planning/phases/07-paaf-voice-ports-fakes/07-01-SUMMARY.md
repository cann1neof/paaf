---
phase: "07"
plan: "01"
subsystem: "voice"
tags:
  - "voice-ports"
  - "audio-fakes"
  - "dataclasses"
  - "protocols"
requires: []
provides:
  - "paaf_voice.ports.AudioFrame"
  - "paaf_voice.ports.AudioSource"
  - "paaf_voice.ports.AudioSink"
  - "paaf_voice.ports.STT"
  - "paaf_voice.ports.TTS"
  - "paaf_voice.ports.WakeWord"
  - "paaf_voice.ports.VAD"
  - "paaf_voice.testing.FakeAudioSink"
  - "paaf_voice.testing.FakeAudioSource"
affects:
  - "packages/paaf-voice"
tech-stack:
  added: []
  patterns:
    - "Protocol with @runtime_checkable for domain port interfaces"
    - "Frozen dataclasses with slots for immutable audio frames"
    - "Virtual playhead test double pattern for hardware playback"
key-files:
  created:
    - "packages/paaf-voice/src/paaf_voice/ports.py"
    - "packages/paaf-voice/src/paaf_voice/testing/fakes.py"
    - "packages/paaf-voice/src/paaf_voice/testing/__init__.py"
    - "packages/paaf-voice/tests/test_ports.py"
    - "packages/paaf-voice/tests/test_fakes.py"
  modified:
    - "packages/paaf-voice/src/paaf_voice/__init__.py"
key-decisions:
  - "Zero external dependencies for core ports and test doubles (stdlib only)"
  - "Zero-division safety guard on AudioFrame.duration_ms for invalid inputs"
requirements-completed:
  - "VOICE-01"
  - "VOICE-02"
  - "VOICE-11"
duration: "5 min"
completed: "2026-08-08"
coverage:
  - deliverable: "Core voice port protocols (AudioSource, AudioSink, STT, TTS, WakeWord, VAD) and value objects"
    verification:
      - kind: "command"
        ref: "uv run pytest packages/paaf-voice/tests/test_ports.py"
        status: "pass"
    human_judgment: false
  - deliverable: "AudioSink and AudioSource test doubles (FakeAudioSink, FakeAudioSource)"
    verification:
      - kind: "command"
        ref: "uv run pytest packages/paaf-voice/tests/test_fakes.py"
        status: "pass"
    human_judgment: false
---

# Phase 07 Plan 01: Core Port Protocols & Audio Sink/Source Test Doubles Summary

Established foundational domain port interfaces and hardware test doubles for `paaf-voice` with zero external dependencies.

## Key Accomplishments

1. **Port Protocols & Data Models**:
   - Implemented `AudioFrame`, `STTResult`, `WakeWordResult`, and `VADResult` as `@dataclass(frozen=True, slots=True)` immutable value objects.
   - Defined `AudioSource`, `AudioSink`, `STT`, `TTS`, `WakeWord`, and `VAD` using pure Python `@runtime_checkable` `Protocol`s.
   - Implemented zero-division guard on `AudioFrame.duration_ms` to safely handle invalid/malformed frame headers.

2. **Audio Hardware Test Doubles**:
   - Implemented `FakeAudioSink` supporting virtual playhead tracking (`instant`, `1x`, `stepped` modes) and exact byte-aligned Acoustic Echo Cancellation (AEC) reference tap extraction.
   - Implemented `FakeAudioSource` for fixed 20ms frame streaming with automatic trailing frame zero-padding and state control (`start`/`stop`).

## Verification

- `uv run pytest packages/paaf-voice/tests/test_ports.py` (5 passed)
- `uv run pytest packages/paaf-voice/tests/test_fakes.py` (4 passed)
- All 10 unit tests across `paaf-voice` pass cleanly.

## Self-Check: PASSED
