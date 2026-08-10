<!-- generated-by: gsd-doc-writer -->
# Configuration Overview

`paaf.yaml` is the single source of truth for model profiles, reload tiers, secret key references, voice settings, and skill configurations.

## Schema Overview

```yaml
version: "1.0"
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
voice:
  stt:
    engine: "faster_whisper"
    model: "base"
    device: "auto"
    compute_type: "int8"
```

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
