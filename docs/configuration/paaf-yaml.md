# `paaf.yaml` Configuration Reference

`paaf.yaml` is the single source of truth for model profiles, reload tiers, secret key references, and skill configurations.

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

skills:
  git_helper:
    enabled: true
    path: .paaf/skills/git_helper
    permissions:
      exec: confirm
```

## Reload Tiers

Config changes apply according to explicit reload tiers:
- **HOT:** Takes effect immediately with no restart (e.g. enabling/disabling skills, updating permissions).
- **WARM:** Takes effect on the next turn (e.g. temperature, system prompt updates).
- **COLD:** Re-initializes subsystem (e.g. changing model name).
- **RESTART:** Requires full process restart (e.g. changing provider or endpoint).

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PAAF_CONFIG_PATH` | Optional | `./paaf.yaml` | Path to the active `paaf.yaml` configuration file |
| `PAAF_SECRET_STORE_PATH` | Optional | `~/.paaf/secrets.enc` | Path to the encrypted secret store file |
| `PAAF_PASSPHRASE` | Optional | `""` | Master passphrase used to derive the Fernet key for secret store encryption at boot |
| `PAAF_ENV` | Optional | `development` | Deployment environment identifier (`development`, `testing`, `production`) |

## Required vs Optional Settings

- **Required Settings**: `version` (must be `"1.0"`), `profiles` (must contain at least one valid model profile).
- **Optional Settings**: `active_profile` (defaults to first defined profile), `fallback_chain` (defaults to empty list), `skills` (defaults to empty map), `security.spoken_confirmation` (defaults to disabled).

## Defaults

- `version`: `"1.0"`
- `temperature`: `0.7`
- `security.spoken_confirmation.enabled`: `false`
- `trace.enabled`: `true`
- `trace.db_path`: `~/.paaf/trace.db`

## Per-Environment Overrides

Environment overrides can be loaded by setting `PAAF_CONFIG_PATH` to point to environment-specific YAML files (e.g. `paaf.development.yaml`, `paaf.production.yaml`) or by setting environment variables in CI/CD pipelines.
