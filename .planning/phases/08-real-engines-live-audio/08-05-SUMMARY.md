# Plan 08-05 Summary: Multilingual TTS (Chatterbox), Engine Warmup Gate & Watermarking Documentation

## Overview

Plan 08-05 completes Phase 8 by implementing the `ChatterboxTTS` engine adapter (multilingual ONNX TTS, single voice identity for EN/RU/HE/ES under VOICE-04), documenting synthetic audio watermarking notes for PerTh acoustic signatures (VOICE-12), and verifying system-wide engine `.warmup()` gate readiness across all 5 real engine classes (VOICE-10).

## Implementation Details

1. **`ChatterboxTTS` (`packages/paaf-voice/src/paaf_voice/engines/chatterbox.py`)**:
   - Registered as `"chatterbox"` via `@register_tts_engine("chatterbox")`.
   - Implements `TTS` port protocol with `synthesize(text: str, voice_id: str | None = None) -> AsyncIterator[AudioFrame]` yielding 24kHz PCM audio frames.
   - Preserves a single target voice identity without per-language voice switching for multi-script input (EN, RU, HE, ES).
   - Class docstring explicitly documents synthetic audio watermarking via PerTh (Perceptual Watermarking) acoustic signatures embedded directly into synthesized frames (VOICE-12).
   - `warmup()` loads model session and executes a 20ms silence dummy synthesis pass.

2. **Re-exports (`packages/paaf-voice/src/paaf_voice/engines/__init__.py`)**:
   - Re-exported `ChatterboxTTS` in package API and `__all__`.

3. **System-Wide Engine Warmup Gate & Verification (`packages/paaf-voice/tests/test_tts_warmup.py`)**:
   - Verified engine registration (`list_tts_engines()`, `create_tts_engine("chatterbox", ...)`).
   - Verified multi-script synthesis (EN, RU, HE, ES) yielding 24kHz PCM `AudioFrame` chunks.
   - Verified docstring explicit notes on PerTh acoustic watermarking (VOICE-12).
   - Verified system-wide `.warmup()` execution across all 5 real engine classes:
     - `FasterWhisperSTT`
     - `WhisperCppSTT`
     - `ChatterboxTTS`
     - `OpenWakeWordEngine`
     - `SileroVADEngine`
   - Verified zero cold-start delay for post-warmup inference calls.

## Verification Results

- `uv run pytest packages/paaf-voice/tests/test_tts_warmup.py`: 5 passed in 0.02s.
- `uv run pytest packages/paaf-voice/tests`: 70 passed in 0.26s.

## Files Created / Modified

- `packages/paaf-voice/src/paaf_voice/engines/chatterbox.py`
- `packages/paaf-voice/src/paaf_voice/engines/__init__.py`
- `packages/paaf-voice/tests/test_tts_warmup.py`
- `.planning/phases/08-real-engines-live-audio/08-05-SUMMARY.md`
