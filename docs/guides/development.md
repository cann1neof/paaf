---
title: "Development Guide"
---
<!-- generated-by: gsd-doc-writer -->

# Development Guide

This guide covers local development workflows, build tools, code style enforcement, and pull request procedures for PAAF.

## Local Setup

1. **Clone the Repository**:

```bash
git clone https://github.com/cann1neof/paaf.git
cd paaf
```

2. **Sync Virtual Environment & Workspace**:

Using `uv` (recommended):

```bash
uv sync
```

3. **Copy Environment Template**:

Copy `.env.example` if configuring custom LLM API keys:

```bash
cp .env.example .env
```

## Build & Quality Commands

| Command | Description |
|---------|-------------|
| `uv run pytest` | Run the complete workspace unit and integration test suite |
| `uv run lint-imports` | Enforce architecture boundary contracts (`.importlinter`) |
| `uv run ruff check .` | Run Ruff linter across all packages |
| `uv run ruff format --check .` | Check code formatting compliance |
| `uv run mypy packages/` | Perform static type checking |
| `uv run mkdocs serve` | Preview documentation locally |

## Code Style & Architecture Enforcement

PAAF enforces strict code quality and architectural isolation:

- **Ruff**: Enforces Python PEP8 code style, formatting, and linting rules.
- **Mypy**: Enforces strict typing (`strict = true` in `pyproject.toml`).
- **Import Linter**: Enforces 3 mandatory architecture boundaries (`.importlinter`):
  1. `voice ↔ llm` independence (no direct or indirect imports between `paaf-voice` and `paaf-llm`).
  2. `langchain` containment (LangChain/LangGraph imports restricted strictly to `paaf_llm._engine.*`).
  3. No network clients in framework packages (blocks `httpx`, `requests`, `aiohttp`, `socket` imports).

## Branch Conventions

Branch names should reflect the scope of work:
- `feat/feature-name` — New framework features
- `fix/bug-description` — Bug fixes
- `docs/doc-update` — Documentation improvements
- `refactor/subsystem-name` — Internal code refactoring

The default branch is `main` (or active release branch `roadmap/agent-mesh`).

## PR Process

1. **Developer Certificate of Origin (DCO)**:
   Every commit must include a DCO sign-off line (`Signed-off-by: Name <email@example.com>`). Use the `-s` flag when committing:
   ```bash
   git commit -s -m "feat(core): add atomic config write validation"
   ```

2. **Pre-PR Verification**:
   Before submitting a pull request, ensure all tests and import linter checks pass cleanly:
   ```bash
   uv run pytest && uv run lint-imports
   ```

3. **Pull Request Submission**:
   - Open a PR against `main`.
   - Ensure GitHub Actions CI checks (`ci.yml` and `dco.yml`) pass green.
