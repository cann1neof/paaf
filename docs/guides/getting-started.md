<!-- generated-by: gsd-doc-writer -->
# Getting Started

Follow these instructions to get PAAF running on your local machine.

## Prerequisites

- **Python**: `>=3.12`
- **Package Manager**: `uv`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cann1neof/paaf.git
   cd paaf
   ```

2. Synchronize virtual environment and workspace packages:
   ```bash
   uv sync
   ```

## First Run

Define a PAAF configuration (`paaf.yaml`):

```yaml
version: "1.0"
profile: "default"
security:
  spoken_confirmation:
    enabled: true
voice:
  stt_engine: "faster_whisper"
  tts_engine: "chatterbox"
  wakeword_engine: "openwakeword"
  vad_engine: "silero_vad"
```

Run tests to verify setup:

```bash
uv run pytest
```

Validate architectural import dependency contracts:

```bash
uv run lint-imports
```

## Voice Model Management

PAAF enforces strict privacy guarantees with zero background auto-downloads. Model weights must be explicitly downloaded by the user via the CLI before use:

```bash
# Download model weights explicitly
uv run paaf voice download-models --engine faster_whisper --model base
uv run paaf voice download-models --engine whisper_cpp --model ggml-base.bin
uv run paaf voice download-models --engine chatterbox --model multilingual-onnx

# List installed model weights
uv run paaf voice list-models
```

## Common Setup Issues

- **Missing uv**: Ensure `uv` is installed (`pip install uv` or via brew).
- **Audio device errors**: Check your audio input/output devices with `uv run paaf voice list-devices`.

## Next Steps

- See [DEVELOPMENT.md](development.md) for local development setup.
- See [TESTING.md](testing.md) for testing guidelines.
