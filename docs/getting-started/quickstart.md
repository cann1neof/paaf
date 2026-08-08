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

## 2. Initialize Configuration

Create a `paaf.yaml` in your workspace:

```yaml
active_profile: main_assistant
profiles:
  main_assistant:
    provider: ollama
    model: llama3.1
    capabilities: "General assistance and reasoning"
```

## 3. Inspect Composed Prompt

Run the prompt inspector to verify the byte-exact system prompt:

```bash
paaf prompt --config paaf.yaml
```

## 4. Start Chat

Run interactive chat:

```bash
paaf chat --config paaf.yaml
```
