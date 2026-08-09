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

## Next Steps

- Read [ARCHITECTURE.md](../../ARCHITECTURE.md) for framework component design and import contracts.
- Read [paaf.yaml Configuration Reference](../configuration/paaf-yaml.md) for profile schema options and reload tiers.
- Read [Development Guide](../guides/development.md) for local monorepo development.
- Read [Testing Guide](../guides/testing.md) for running tests and import contract linter.
