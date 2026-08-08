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
