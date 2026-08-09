# Quickstart Guide

Get up and running with PAAF in under 2 minutes.

## 1. Installation

Install the monolithic framework from PyPI:

```bash
pip install paaf
```

To enable heavy LLM engine adapters (Ollama, OpenAI, Anthropic), install the optional `[engine]` extra:

```bash
pip install "paaf[engine]"
```

To enable local voice processing (STT, TTS, WakeWord, VAD), install the `[voice]` extra:

```bash
pip install "paaf[voice]"
```

## 2. Initialize Configuration

Create a `paaf.yaml` in your workspace to bind LLM profiles and voice engines:

```yaml
active_profile: main_assistant
profiles:
  main_assistant:
    provider: ollama
    model: llama3.1
    capabilities: "General assistance and reasoning"

voice:
  stt:
    engine: "faster_whisper"    # or "whisper_cpp" (for Raspberry Pi / low RAM)
    model: "base"               # or "ggml-base.bin"
    device: "auto"              # "cpu", "mps", "cuda"
    compute_type: "int8"

  tts:
    engine: "chatterbox"
    voice_id: "default"

  wake_word:
    engine: "openwakeword"
    model: "hey_jarvis"

  vad:
    engine: "silero"
    speech_threshold_idle: 0.50
    speech_threshold_playback: 0.65
```

## 3. Hardware Device Selection & Voice Model Setup

### List Audio Hardware Devices

List available physical audio input (microphone) and output (speaker) devices:

```bash
paaf voice list-devices
```

### Download Voice Models (Explicit Consent Required)

In alignment with local-first privacy policies, model downloads require explicit CLI consent and will never initiate automatically in the background.

Download offline engine weights for your chosen STT engine:

Standard hardware (`faster_whisper`):
```bash
paaf voice download-models --engine faster_whisper --model base
```

Raspberry Pi or low-RAM environments (`whisper_cpp`):
```bash
paaf voice download-models --engine whisper_cpp --model ggml-base.bin
```

## 4. Inspect Composed Prompt

Run the prompt inspector to verify the byte-exact system prompt:

```bash
paaf prompt --config paaf.yaml
```

## 5. Start Chat

Run interactive chat:

```bash
paaf chat --config paaf.yaml
```

## Prerequisites

- **Python**: `>= 3.12.0`
- **Package Manager**: `uv` (recommended) or `pip`
- **Git**: `2.30.0` or higher

## Common Setup Issues

1. **Missing `paaf.yaml` Configuration**:
   - *Symptom*: `FileNotFoundError: paaf.yaml not found`.
   - *Solution*: Create a `paaf.yaml` in the current working directory or pass `--config /path/to/paaf.yaml`.

2. **Network Egress Blocked in Tests**:
   - *Symptom*: `SocketBlockedError: A socket open attempt was intercepted`.
   - *Solution*: PAAF test suites enforce zero network egress by default (`--disable-socket`). Use `FakeLLMAdapter` or `FakeAudioSource` test doubles instead of making live API requests in unit tests.

3. **Uncached Voice Model Error**:
   - *Symptom*: Model file not found when initializing voice pipeline.
   - *Solution*: Run `paaf voice download-models --engine <engine> --model <model>` to explicitly download required weights with CLI consent.

## Next Steps

- Read [ARCHITECTURE.md](../../ARCHITECTURE.md) for framework component design and import contracts.
- Read [paaf.yaml Configuration Reference](../configuration/paaf-yaml.md) for profile schema options and reload tiers.
- Read [Development Guide](../guides/development.md) for local monorepo development.
- Read [Testing Guide](../guides/testing.md) for running tests and import contract linter.
