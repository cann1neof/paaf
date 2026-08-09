# Plan 08-04 Summary: Real Wake Word (openWakeWord) & Continuous Dual-Threshold VAD (Silero)

## Overview

Plan 08-04 implements real wake word detection (`OpenWakeWordEngine`) and continuous Voice Activity Detection (`SileroVADEngine`) adapters for PAAF voice under requirements VOICE-07 and VOICE-08.

## Implementation Details

1. **`OpenWakeWordEngine` (`packages/paaf-voice/src/paaf_voice/engines/openwakeword.py`)**:
   - Registered as `"openwakeword"` via `@register_wake_engine("openwakeword")`.
   - Implements `WakeWord` port protocol with `detect(frame: AudioFrame) -> WakeWordResult` and `warmup()`.
   - Supports built-in keywords (e.g. `hey_jarvis`, `alexa`) and custom ONNX models.
   - Configured with `intra_op_num_threads=1` and `inter_op_num_threads=1` in `onnxruntime` SessionOptions for low CPU resource overhead on ARM.

2. **`SileroVADEngine` (`packages/paaf-voice/src/paaf_voice/engines/silero_vad.py`)**:
   - Registered as `"silero"` via `@register_vad_engine("silero")`.
   - Implements `VAD` port protocol with `process_frame(frame: AudioFrame) -> VADResult`, `warmup()`, and state management (`reset_states()`).
   - Implements continuous dual thresholding:
     - `speech_threshold_idle` (default `0.50`): sensitivity when idle.
     - `speech_threshold_playback` (default `0.65`): sensitivity when TTS audio playback is active.
     - `set_playback_active(active: bool)` dynamically switches between idle and playback active thresholds, preventing speaker acoustic bleed false triggers.

3. **Re-exports (`packages/paaf-voice/src/paaf_voice/engines/__init__.py`)**:
   - Exposed `OpenWakeWordEngine` and `SileroVADEngine` in package API.

4. **Unit Tests (`packages/paaf-voice/tests/test_wakeword_vad.py`)**:
   - Verified engine registration in factory registries (`list_wake_engines()`, `list_vad_engines()`).
   - Verified factory creation with `create_wake_engine()` and `create_vad_engine()`.
   - Verified `OpenWakeWordEngine` detection confidence calculation, keyword parsing, warmup, and missing dependency handling.
   - Verified `SileroVADEngine` dual-threshold switching between idle (`0.50`) and active playback (`0.65`).

## Verification Results

- `uv run pytest packages/paaf-voice/tests/test_wakeword_vad.py`: 7 passed in 0.02s.
- `uv run pytest packages/paaf-voice/tests`: 52 passed in 0.07s.

## Files Created / Modified

- `packages/paaf-voice/src/paaf_voice/engines/openwakeword.py`
- `packages/paaf-voice/src/paaf_voice/engines/silero_vad.py`
- `packages/paaf-voice/src/paaf_voice/engines/__init__.py`
- `packages/paaf-voice/tests/test_wakeword_vad.py`
- `.planning/phases/08-real-engines-live-audio/08-04-SUMMARY.md`
