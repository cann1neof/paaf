# API Reference

## Python API

### `paaf_llm.agent.Agent`
Main turn loop runner for conversation turns and prompt compilation.

### `paaf_llm.skills.installer.install_skill`
Staging-based installation engine for remote or local skills.

### `paaf_core.config.store`
Atomic configuration reader/writer with optimistic revision lock.

### `paaf_voice.ports`
Core voice protocols (ports) and immutable value objects for audio streaming, STT, TTS, wake word detection, and voice activity detection (VAD).

#### Value Objects
- **`AudioFrame(data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2, timestamp_ms: float = 0.0)`**: Immutable dataclass representing a raw PCM audio chunk. Exposes `duration_ms` property.
- **`STTResult(text: str, is_final: bool = True, language: str | None = None, confidence: float = 1.0)`**: Data container for speech-to-text transcription output.
- **`WakeWordResult(detected: bool, keyword: str | None = None, confidence: float = 0.0)`**: Data container for wake word detection status.
- **`VADResult(is_speech: bool, confidence: float = 0.0)`**: Data container for voice activity detection status.

#### Protocols (Ports)
- **`STT` / `STTPort`**: Protocol interface for speech-to-text recognition engines.
  - `transcribe_stream(audio_stream: AsyncIterable[AudioFrame]) -> AsyncIterator[STTResult]`
  - `warmup() -> None`
- **`TTS` / `TTSPort`**: Protocol interface for text-to-speech synthesis engines.
  - `synthesize(text: str, voice_id: str | None = None) -> AsyncIterator[AudioFrame]`
  - `warmup() -> None`
- **`WakeWord` / `WakeWordPort`**: Protocol interface for wake word detection engines.
  - `detect(frame: AudioFrame) -> WakeWordResult`
  - `warmup() -> None`
- **`VAD` / `VADPort`**: Protocol interface for voice activity detection engines.
  - `process_frame(frame: AudioFrame) -> VADResult`
  - `warmup() -> None`
- **`AudioSource`**: Protocol interface for audio input streams (hardware mic or stream).
  - `read_frames(frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]`
  - `start() -> None`
  - `stop() -> None`
- **`AudioSink`**: Protocol interface for audio output streams (hardware speaker or sink).
  - `write_frame(frame: AudioFrame) -> None`
  - `get_playhead_position() -> float`
  - `get_reference_tap() -> bytes`

### `paaf_voice.engines`
Dynamic engine registry framework and real engine adapters for STT, TTS, wake word, and VAD.

#### Engine Registry & Factory Functions
- **`@register_stt_engine(name: str)`**: Class decorator registering an STT implementation under `name`.
- **`@register_tts_engine(name: str)`**: Class decorator registering a TTS implementation under `name`.
- **`@register_wake_engine(name: str)`**: Class decorator registering a WakeWord implementation under `name`.
- **`@register_vad_engine(name: str)`**: Class decorator registering a VAD implementation under `name`.
- **`create_stt_engine(name: str, **kwargs) -> STT`**: Instantiate a registered STT engine by name.
- **`create_tts_engine(name: str, **kwargs) -> TTS`**: Instantiate a registered TTS engine by name.
- **`create_wake_engine(name: str, **kwargs) -> WakeWord`**: Instantiate a registered WakeWord engine by name.
- **`create_vad_engine(name: str, **kwargs) -> VAD`**: Instantiate a registered VAD engine by name.
- **`get_engine_for_language(lang: str, default_engine: str, overrides: dict[str, str] | None = None) -> str`**: Resolves engine name based on ISO language code and override rules (VOICE-05).
- **`list_stt_engines()`, `list_tts_engines()`, `list_wake_engines()`, `list_vad_engines()`**: Query sorted lists of currently registered engine identifiers.
- **`clear_registries()`**: Clears engine registries (intended for test isolation).

#### Engine Implementations
- **`FasterWhisperSTT(model_size_or_path: str = "base", device: str = "auto", compute_type: str = "default", download_root: str | None = None, language: str | None = None)`**: Speech-to-Text engine adapter wrapping `faster-whisper` (CTranslate2).
- **`WhisperCppSTT(model_path: str = "ggml-base.bin", n_threads: int = 4, language: str | None = None)`**: High-performance, low-footprint STT adapter wrapping `whisper.cpp` (`pywhispercpp`) tailored for ARM/edge platforms.
- **`ChatterboxTTS(model_path: str | None = None, voice_id: str = "default", sample_rate: int = 24000)`**: Multilingual Text-To-Speech engine adapter wrapping Chatterbox / Dicta-ONNX. Supports seamless multi-language synthesis across English, Russian, Hebrew, and Spanish under a single target voice identity (VOICE-04), featuring PerTh acoustic signature watermarking (VOICE-12).
- **`OpenWakeWordEngine(model_path_or_name: str = "hey_jarvis", threshold: float = 0.5)`**: Wake word detection engine adapter wrapping `openWakeWord` (ONNX).
- **`SileroVADEngine(model_path: str | None = None, speech_threshold_idle: float = 0.50, speech_threshold_playback: float = 0.65, sample_rate: int = 16000)`**: Voice Activity Detection engine adapter wrapping Silero VAD (ONNX). Supports continuous sensing with dynamic dual thresholds for idle vs active speaker playback to eliminate echo false triggers (VOICE-08).

### `paaf_voice.audio`
Hardware audio input/output adapters powered by `sounddevice` and PortAudio.

- **`SoundDeviceAudioSource(device_index: int | str | None = None, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2)`**: Real-time microphone audio capture stream implementing `AudioSource`.
- **`SoundDeviceAudioSink(device_index: int | str | None = None, target_sample_rate: int = 48000, channels: int = 1, sample_width: int = 2, max_tap_bytes: int = 320000)`**: Real-time speaker playback sink implementing `AudioSink`. Performs dynamic sample rate conversion (`soxr` / fallback) and maintains a rolling reference tap buffer for Acoustic Echo Cancellation (AEC).

### `paaf_voice.exceptions`
Exception hierarchy and model weight verification helpers.

- **`VoiceError`**: Base exception class for all PAAF voice errors.
- **`ModelMissingError(engine_name: str, model_name: str, cache_dir: str | Path | None = None)`**: Raised when required offline model weights are missing from disk cache (PRIV-06 gate).
- **`verify_model_present(engine_name: str, model_name: str, cache_dir: str | Path | None = None) -> Path`**: Validates whether model weights exist in the local cache directory, returning the `Path` or raising `ModelMissingError`.

---

## CLI Reference

### `paaf voice` Command Group
CLI tools for PAAF voice model management, offline weight downloads, and audio hardware inspection.

#### `paaf voice download-models`
Download engine model weights into the local cache directory with explicit user consent (PRIV-06).

```bash
paaf voice download-models [OPTIONS]
```

**Options:**
- `-e, --engine TEXT`: Target engine identifier (default: `faster_whisper`). Supported engines: `faster_whisper`, `whisper_cpp`, `chatterbox`, `openwakeword`, `silero_vad`.
- `-m, --model TEXT`: Model identifier or weight file (default: `base`). Examples: `tiny`, `base`, `small`, `ggml-base.bin`, `hey_jarvis`, `silero_vad.onnx`.
- `-c, --cache-dir PATH`: Custom model weight cache directory (default: `~/.cache/paaf/models`).

#### `paaf voice list-models`
List locally installed model weights within the cache directory (PRIV-06).

```bash
paaf voice list-models [OPTIONS]
```

**Options:**
- `-c, --cache-dir PATH`: Custom model weight cache directory (default: `~/.cache/paaf/models`).

#### `paaf voice list-devices`
Inspect connected audio input (microphones) and output (speakers) hardware devices, displaying device indices, channel counts, default sample rates, and default roles (VOICE-09).

```bash
paaf voice list-devices
```

