# PAAF — Personalized Agentic Assistant Framework

PAAF is a local-first, privacy-preserving assistant framework where the **user owns the mind**.

## Quickstart

```bash
# Install monolithic framework
pip install paaf

# Optional: install engine dependencies for LLM adapters
pip install "paaf[engine]"

# Inspect composed prompt
paaf prompt --config paaf.yaml

# Hold conversation with configured models
paaf chat --config paaf.yaml

# Manage skills
paaf skill list
paaf skill install <git-url-or-path>
```
