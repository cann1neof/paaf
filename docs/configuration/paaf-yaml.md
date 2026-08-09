# `paaf.yaml` Configuration Reference

`paaf.yaml` is the single source of truth for model profiles, reload tiers, secret key references, voice settings, and skill configurations.

## Schema Overview

```yaml
active_profile: assistant
fallback_chain:
  - fast_local
profiles:
  assistant:
    provider: ollama
    model: llama3.1
    temperature: 0.7
    peers:
      - coding_specialist
    capabilities: "General assistant for everyday tasks"

  coding_specialist:
    provider: anthropic
    model: claude-3-5-sonnet-20241022
    api_key_ref: anthropic_key
    capabilities: "Expert software engineer"

voice:
  stt:
    engine: "faster_whisper"    # or "whisper_cpp" (for Raspberry Pi / low RAM)
    model: "base"               # or "ggml-base.bin"
    device: "auto"              # "cpu", "mps", "cuda"
    compute_type: "int8"
    engine_overrides: {}        # optional per-language engine override escape hatch (VOICE-05)

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

skills:
  git_helper:
    enabled: true
    path: .paaf/skills/git_helper
    permissions:
      exec: confirm
```

## Voice Configuration

The `voice` section controls offline audio processing, Speech-to-Text (STT), Text-to-Speech (TTS), Wake Word detection, and Voice Activity Detection (VAD).

### Speech-to-Text (`voice.stt`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engine` | string | `"faster_whisper"` | STT processing engine (`faster_whisper` for standard hardware, `whisper_cpp` for Raspberry Pi / low RAM) |
| `model` | string | `"base"` | Model size or filename (`base`, `tiny`, `small`, `medium`, `large-v3` for `faster_whisper`; `ggml-base.bin`, `ggml-tiny.bin` for `whisper_cpp`) |
| `device` | string | `"auto"` | Compute device selection (`auto`, `cpu`, `mps`, `cuda`) |
| `compute_type` | string | `"int8"` | Quantization compute precision (`int8`, `float16`, `float32`) |
| `engine_overrides` | map | `{}` | Optional per-language engine override map for multi-lingual routing escape hatch (VOICE-05) |

### Text-to-Speech (`voice.tts`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engine` | string | `"chatterbox"` | TTS synthesis engine |
| `voice_id` | string | `"default"` | Target voice identifier or voice profile |

### Wake Word (`voice.wake_word`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engine` | string | `"openwakeword"` | Wake word detection engine |
| `model` | string | `"hey_jarvis"` | Target wake word model identifier (`hey_jarvis`, `alexa`) |

### Voice Activity Detection (`voice.vad`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `engine` | string | `"silero"` | VAD engine identifier |
| `speech_threshold_idle` | float | `0.50` | Speech confidence threshold when assistant is idle/listening |
| `speech_threshold_playback` | float | `0.65` | Higher speech confidence threshold during active audio playback to prevent self-triggering |

## Voice Model Management CLI

PAAF provides CLI commands to manage offline model weights with explicit user consent (PRIV-06).

### Downloading Models

Download engine weights into the local cache directory (`~/.cache/paaf/models`):

```bash
paaf voice download-models --engine faster_whisper --model base
```

Options:
- `-e, --engine`: Target engine (`faster_whisper`, `whisper_cpp`, `chatterbox`, `openwakeword`, `silero_vad`). Default: `faster_whisper`.
- `-m, --model`: Target model identifier (e.g. `base`, `tiny`, `ggml-base.bin`, `hey_jarvis`). Default: `base`.
- `-c, --cache-dir`: Custom model weight cache directory.

### Listing Installed Models

View all downloaded and cached model weights:

```bash
paaf voice list-models
```

## Reload Tiers

Config changes apply according to explicit reload tiers:
- **HOT:** Takes effect immediately with no restart (e.g. enabling/disabling skills, updating permissions).
- **WARM:** Takes effect on the next turn (e.g. temperature, system prompt updates, VAD threshold adjustments).
- **COLD:** Re-initializes subsystem (e.g. changing model name, voice ID, wake word model).
- **RESTART:** Requires full process restart (e.g. changing provider or endpoint, STT/TTS engine selection).

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAAF_CONFIG_PATH` | Optional | `./paaf.yaml` | Path to the active `paaf.yaml` configuration file |
| `PAAF_SECRET_STORE_PATH` | Optional | `~/.paaf/secrets.enc` | Path to the encrypted secret store file |
| `PAAF_PASSPHRASE` | Optional | `""` | Master passphrase used to derive the Fernet key for secret store encryption at boot |
| `PAAF_ENV` | Optional | `development` | Deployment environment identifier (`development`, `testing`, `production`) |

## Required vs Optional Settings

- **Required Settings**: `version` (must be `"1.0"`), `profiles` (must contain at least one valid model profile).
- **Optional Settings**: `active_profile` (defaults to first defined profile), `fallback_chain` (defaults to empty list), `skills` (defaults to empty map), `voice` (defaults to standard `faster_whisper` / `chatterbox` / `openwakeword` / `silero` defaults), `security.spoken_confirmation` (defaults to disabled).

## Defaults

- `version`: `"1.0"`
- `temperature`: `0.7`
- `voice.stt.engine`: `"faster_whisper"`
- `voice.stt.model`: `"base"`
- `voice.stt.device`: `"auto"`
- `voice.stt.compute_type`: `"int8"`
- `voice.tts.engine`: `"chatterbox"`
- `voice.tts.voice_id`: `"default"`
- `voice.wake_word.engine`: `"openwakeword"`
- `voice.wake_word.model`: `"hey_jarvis"`
- `voice.vad.engine`: `"silero"`
- `voice.vad.speech_threshold_idle`: `0.50`
- `voice.vad.speech_threshold_playback`: `0.65`
- `security.spoken_confirmation.enabled`: `false`
- `trace.enabled`: `true`
- `trace.db_path`: `~/.paaf/trace.db`

## Per-Environment Overrides

Environment overrides can be loaded by setting `PAAF_CONFIG_PATH` to point to environment-specific YAML files (e.g. `paaf.development.yaml`, `paaf.production.yaml`) or by setting environment variables in CI/CD pipelines.
