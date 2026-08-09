<!-- generated-by: gsd-doc-writer -->
# PAAF — Personalized Agentic Assistant Framework

A local-first, modular, and privacy-focused framework for building personalized agentic AI assistants.

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python: >=3.12](https://img.shields.io/badge/Python->=3.12-green.svg)](pyproject.toml)

PAAF provides a local-first architecture for AI assistants featuring spoken confirmation gates, model-agnostic LLM engine composition, multi-tier YAML configuration, zero-egress telemetry tracing, and hardware-decoupled voice pipeline test doubles.

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

## Quick Start

1. Define a PAAF configuration (`paaf.yaml`):

```yaml
version: "1.0"
profile: "default"
security:
  spoken_confirmation:
    enabled: true
```

2. Run tests to verify setup:

```bash
uv run pytest
```

3. Validate import dependency contracts:

```bash
uv run lint-imports
```

## Package Architecture

PAAF is organized into specialized, decoupled packages inside `packages/`:

| Package | Description |
|---------|-------------|
| [`paaf-core`](packages/paaf-core) | Core domain models, configuration schema (`paaf.yaml`), reload tiers, and secret management |
| [`paaf-llm`](packages/paaf-llm) | Model-agnostic LLM engine composition, mesh router, permission engine, and spoken confirmation gates |
| [`paaf-session`](packages/paaf-session) | Turn-based voice state machine and session context management |
| [`paaf-trace`](packages/paaf-trace) | Local-only zero-egress trace queue, handoff logs, and TTFA telemetry |
| [`paaf-voice`](packages/paaf-voice) | Voice port protocols (`AudioSource`, `AudioSink`, `STT`, `TTS`, `VAD`, `WakeWord`), test doubles, and sentence aggregator |

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
