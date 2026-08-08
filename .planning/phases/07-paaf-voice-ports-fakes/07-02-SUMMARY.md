---
phase: "07"
plan: "02"
subsystem: "voice"
tags:
  - "engine-fakes"
  - "stt"
  - "tts"
  - "wakeword"
  - "vad"
requires:
  - "07-01-PLAN.md"
provides:
  - "paaf_voice.testing.FakeSTT"
  - "paaf_voice.testing.FakeTTS"
  - "paaf_voice.testing.FakeWakeWord"
  - "paaf_voice.testing.FakeVAD"
affects:
  - "packages/paaf-voice"
tech-stack:
  added: []
  patterns:
    - "Test doubles for streaming STT/TTS and frame-based WakeWord/VAD engines"
key-files:
  created: []
  modified:
    - "packages/paaf-voice/src/paaf_voice/testing/fakes.py"
    - "packages/paaf-voice/src/paaf_voice/testing/__init__.py"
    - "packages/paaf-voice/tests/test_fakes.py"
key-decisions:
  - "Fake engines isolate state per instance to prevent cross-test leakage"
requirements-completed:
  - "VOICE-01"
  - "VOICE-02"
duration: "5 min"
completed: "2026-08-08"
coverage:
  - deliverable: "Fake engine test doubles (FakeSTT, FakeTTS, FakeWakeWord, FakeVAD)"
    verification:
      - kind: "command"
        ref: "uv run pytest packages/paaf-voice/tests/test_fakes.py"
        status: "pass"
    human_judgment: false
---

# Phase 07 Plan 02: Engine Test Doubles Summary

Implemented test doubles for all four voice processing engine protocols (`FakeSTT`, `FakeTTS`, `FakeWakeWord`, `FakeVAD`) in `paaf_voice.testing`.

## Key Accomplishments

1. **Fake Engine Implementations**:
   - `FakeSTT`: Consumes audio frame streams and yields configurable canned or default STT results. Tracks stream invocation count.
   - `FakeTTS`: Records synthesized texts in `synthesized_texts` list and yields character-proportional PCM audio frame sequences.
   - `FakeWakeWord`: Supports fixed keyword configuration, manual `trigger()`, and auto-reset after detection.
   - `FakeVAD`: Supports deterministic `speech_timeline` sequence or default speech boolean flag.
   - Implemented `warmup()` lifecycle method across all four fake engine classes.

2. **Protocol Compliance & Verification**:
   - Verified `@runtime_checkable` `Protocol` compliance (`isinstance` checks pass).
   - Expanded unit tests in `packages/paaf-voice/tests/test_fakes.py`.

## Verification

- `uv run pytest packages/paaf-voice/tests/test_fakes.py` (9 passed)

## Self-Check: PASSED
