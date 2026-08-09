# Plan 08-03 Summary: Live Audio Hardware I/O (sounddevice), Dynamic Resampling & Device Management

## Executive Summary

Plan 08-03 implements real cross-platform live audio hardware input (`SoundDeviceAudioSource`) and output (`SoundDeviceAudioSink`) adapters using `sounddevice` (PortAudio wrapper) and `soxr` dynamic resampler under requirements VOICE-09 and decisions D-06, D-07, and D-08.

`SoundDeviceAudioSource` captures live 16kHz 16-bit mono microphone PCM frames (20ms / 320 samples per frame). `SoundDeviceAudioSink` plays TTS audio out of physical speakers using `soxr` (or fallback sample converter) for dynamic sample rate conversion (converting Chatterbox TTS or 16k/22.05k/24k streams to output soundcard rates like 44.1kHz or 48kHz), tracks playhead position in seconds (`get_playhead_position()`), and exposes played PCM bytes via `get_reference_tap()` for downstream acoustic echo cancellation (AEC).

Additionally, `paaf voice list-devices` lists all connected audio hardware microphone inputs and speaker outputs.

## Implementation Details

1. **`SoundDeviceAudioSource` (`packages/paaf-voice/src/paaf_voice/audio/sounddevice_io.py`)**:
   - Implements `AudioSource` port protocol (`start()`, `stop()`, `read_frames(frame_duration_ms=20)`).
   - Configures PortAudio input stream at 16kHz 16-bit mono.
   - Lock-free C audio callback copies input PCM frames into a thread-safe queue (`queue.Queue`).
   - `read_frames()` yields 20ms `AudioFrame` chunks with accurate timestamp tracking.

2. **`SoundDeviceAudioSink` (`packages/paaf-voice/src/paaf_voice/audio/sounddevice_io.py`)**:
   - Implements `AudioSink` port protocol (`write_frame()`, `get_playhead_position()`, `get_reference_tap()`).
   - Resamples incoming audio streams to output sample rate (`target_sample_rate`, e.g. 48kHz) via `soxr.resample()` with pure Python linear interpolation fallback for headless/stub test runners.
   - Maintains virtual playhead position in seconds (`get_playhead_position()`).
   - Maintains thread-safe ring buffer (`_reference_tap_buffer`) bounded by `max_tap_bytes` (default 320kB = ~10s) and exposes played PCM bytes via `get_reference_tap()`.

3. **`paaf voice list-devices` (`packages/paaf-voice/src/paaf_voice/cli/devices.py`)**:
   - Subcommand added to `voice_cli` Click group.
   - `get_audio_devices()` queries system hardware audio devices via `sounddevice.query_devices()`.
   - Displays formatted table of input/output devices including device index, name, input channels, output channels, default sample rate, and default role.

4. **Re-exports (`packages/paaf-voice/src/paaf_voice/audio/__init__.py`)**:
   - Re-exports `SoundDeviceAudioSource` and `SoundDeviceAudioSink`.

5. **Unit Tests & Verification (`packages/paaf-voice/tests/test_audio_io.py`)**:
   - Verified `AudioSource` and `AudioSink` protocol compliance (`isinstance`).
   - Verified async `read_frames()` 20ms chunking and timestamp progression.
   - Verified `write_frame()` sample rate conversion, playhead position calculation, reference tap retrieval, and ring buffer max bounds.
   - Verified `get_audio_devices()` mock formatting and `paaf voice list-devices` CLI output formatting.

## Verification Results

- `uv run pytest packages/paaf-voice/tests/test_audio_io.py`: 6 passed in 0.03s.
- `uv run pytest packages/paaf-voice/tests`: 65 passed in 0.21s.

## Files Created / Modified

- `packages/paaf-voice/src/paaf_voice/audio/__init__.py`
- `packages/paaf-voice/src/paaf_voice/audio/sounddevice_io.py`
- `packages/paaf-voice/src/paaf_voice/cli/devices.py`
- `packages/paaf-voice/src/paaf_voice/cli/__init__.py`
- `packages/paaf-voice/tests/test_audio_io.py`
- `.planning/phases/08-real-engines-live-audio/08-03-SUMMARY.md`
