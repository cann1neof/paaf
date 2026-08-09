<!-- generated-by: gsd-doc-writer -->
# PAAF — Personalized Agentic Assistant Framework

A local-first, modular, and privacy-focused framework for building personalized agentic AI assistants.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python: >=3.12](https://img.shields.io/badge/Python->=3.12-green.svg)](pyproject.toml)
[![Status: Phases 1-8 Complete](https://img.shields.io/badge/Status-Phases%201--8%20Complete-brightgreen.svg)](ARCHITECTURE.md)

PAAF provides a local-first architecture for AI assistants featuring spoken confirmation gates, model-agnostic LLM engine composition, multi-tier YAML configuration, zero-egress telemetry tracing, hardware-decoupled voice pipeline protocols, dual STT engine support (Mac/x86 + Raspberry Pi), multilingual single-voice TTS synthesis, real wake-word/VAD engines, live PortAudio I/O, and zero-auto-download explicit CLI model management.

## Project Status

**Phases 1 through 8 are fully implemented.**
- **431 workspace tests passing** (including **70/70 voice package tests**).
- Architectural import boundary enforcement via `import-linter` (`uv run lint-imports`).

## Installation

Ensure Python 3.12+ and `uv` package manager are installed.

```bash
# Clone the repository
git clone https://github.com/cann1neof/paaf.git
cd paaf

# Synchronize virtual environment and workspace packages
uv sync
```

To install all workspace packages in editable mode manually:

```bash
uv pip install -e packages/paaf-core -e packages/paaf-llm -e packages/paaf-session -e packages/paaf-trace -e packages/paaf-voice
```

## Voice Model Management (PRIV-06)

PAAF enforces strict privacy guarantees with **zero background auto-downloads**. Model weights must be explicitly downloaded by the user via the CLI before use:

```bash
# Download model weights explicitly
uv run paaf voice download-models --engine faster_whisper --model base
uv run paaf voice download-models --engine whisper_cpp --model ggml-base.bin
uv run paaf voice download-models --engine chatterbox --model multilingual-onnx

# List installed model weights
uv run paaf voice list-models

# List available audio input/output hardware devices
uv run paaf voice list-devices
```

## Quick Start

1. Define a PAAF configuration (`paaf.yaml`):

```yaml
version: "1.0"
profile: "default"
security:
  spoken_confirmation:
    enabled: true
voice:
  stt_engine: "faster_whisper"  # or "whisper_cpp" for Raspberry Pi / low-resource ARM
  tts_engine: "chatterbox"
  wakeword_engine: "openwakeword"
  vad_engine: "silero_vad"
```

2. Run tests to verify setup:

```bash
uv run pytest
```

3. Validate architectural import dependency contracts:

```bash
uv run lint-imports
```

## Package Architecture

PAAF is organized into specialized, decoupled packages inside `packages/`:

| Package | Description |
|---------|-------------|
| [`paaf-core`](packages/paaf-core) | Core domain models, configuration schema (`paaf.yaml`), reload tiers, secret management, and network endpoint declarations |
| [`paaf-llm`](packages/paaf-llm) | Model-agnostic LLM engine composition, mesh router, permission engine, observer supervisor, and spoken confirmation gates |
| [`paaf-session`](packages/paaf-session) | Turn-based voice state machine, turn orchestrator, and session context management |
| [`paaf-trace`](packages/paaf-trace) | Local-only zero-egress trace queue, handoff logs, and TTFA telemetry |
| [`paaf-voice`](packages/paaf-voice) | Voice port protocols (`AudioSource`, `AudioSink`, `STT`, `TTS`, `VAD`, `WakeWord`), Engine Registry (`paaf_voice.engines`), dual STT support (`FasterWhisperSTT` / `WhisperCppSTT`), multilingual TTS (`ChatterboxTTS`), real wake-word & VAD (`OpenWakeWordEngine`, `SileroVADEngine`), live audio I/O (`SoundDeviceAudioSource` / `SoundDeviceAudioSink`), explicit model management CLI (`PRIV-06`), engine warmup gates (`VOICE-10`), and sentence aggregator |

## Documentation

- [Architecture Guide](ARCHITECTURE.md) — System components, data flow, and key abstractions
- [Getting Started](docs/getting-started/quickstart.md) — Detailed setup, prerequisites, and first-run guide
- [Configuration Reference](docs/configuration/paaf-yaml.md) — Multi-tier `paaf.yaml` configuration schema
- [Development Guide](docs/guides/development.md) — Local development workflow, build scripts, and linting
- [Testing Guide](docs/guides/testing.md) — Test suite layout, no-egress socket enforcement, and benchmarks

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on code style, testing, and submitting pull requests.

## License

Distributed under the [Apache 2.0 License](LICENSE).
