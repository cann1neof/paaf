---
title: "Testing Guide"
---
<!-- generated-by: gsd-doc-writer -->

# Testing Guide

This document details the testing architecture, test execution commands, zero-egress network isolation, voice subsystem test strategies, and CI integration for PAAF.

## Test Framework & Setup

PAAF uses `pytest` as its primary test runner, configured for workspace-wide test discovery:

- **Runner**: `pytest` (`>= 9.1.1`)
- **Async Support**: `pytest-asyncio` (`>= 1.4.0`) with `asyncio_mode = "auto"`
- **Socket Isolation**: `pytest-socket` (`0.7.0`) enforcing architectural zero-egress

## Running Tests

Run the full workspace test suite:

```bash
uv run pytest
```

Run tests for a single package:

```bash
uv run pytest packages/paaf-voice/
```

Run a specific test file:

```bash
uv run pytest packages/paaf-voice/tests/test_ports.py
```

Run import boundary contract checks:

```bash
uv run lint-imports
```

## Architectural Zero-Egress Enforcement

To guarantee privacy and local-first compliance, `pyproject.toml` configures `pytest-socket` options:

```toml
[tool.pytest.ini_options]
addopts = "--disable-socket --allow-unix-socket --import-mode=importlib -p no:langsmith_plugin"
```

1. **`--disable-socket`**: Intercepts and blocks any attempt to open an internet socket (`AF_INET`/`AF_INET6`). Any unexpected cloud telemetry or egress attempt immediately fails the test suite.
2. **`--allow-unix-socket`**: Allows local Unix domain sockets (`AF_UNIX`) required for local IPC and Python `asyncio` event-loop self-pipes.
3. **`-p no:langsmith_plugin`**: Disables third-party cloud telemetry plugins from loading into test processes.

## Voice Subsystem Testing (Zero-Hardware Architecture)

The `paaf-voice` package is engineered for deterministic, high-speed execution without requiring physical microphone/speaker hardware or live audio devices:

- **Test Suite Metrics**: 70 unit and integration tests execute cleanly in under `0.3s`.
- **Synthetic & File Fixtures**: Audio streaming, VAD, Wake Word, STT, and TTS engines are validated using synthetic PCM byte buffers (e.g. `b"\x00" * 640` chunk frames) and local WAV test fixtures (`packages/paaf-voice/tests/fixtures/wav/`).
- **Test Doubles**: `paaf_voice.testing` provides isolated test doubles that avoid all system audio driver and hardware dependencies:
  - `FakeAudioSource`: Simulates hardware microphone streams by yielding controllable PCM frames.
  - `FakeAudioSink`: Simulates hardware speaker outputs by capturing rendered audio bytes in memory.
  - `FakeSTT`: Returns deterministic transcripts from audio frames without invoking deep neural networks.
  - `FakeTTS`: Generates synthetic PCM frames for string prompts without loading TTS models.
  - `FakeVAD`: Produces predictable speech activity state transitions.
  - `FakeWakeWord`: Triggers simulated detection events on demand.

### Running Voice Package Tests

Run the full `paaf-voice` test suite directly:

```bash
uv run pytest packages/paaf-voice/
```

## Writing New Tests

1. **Location & Naming**: Place tests in `packages/<package-name>/tests/test_<feature>.py`.
2. **Async Tests**: Annotate async test functions with `@pytest.mark.asyncio`:
   ```python
   import pytest
   from paaf_voice.testing import FakeAudioSource

   @pytest.mark.asyncio
   async def test_audio_source_stream():
       source = FakeAudioSource(pcm_data=b"\x00" * 640)
       frames = [frame async for frame in source.read_frames()]
       assert len(frames) == 1
   ```
3. **Test Doubles**: Use built-in test doubles (`FakeLLMAdapter`, `FakeAudioSink`, `FakeAudioSource`, `FakeSTT`, `FakeTTS`, `FakeVAD`, `FakeWakeWord`) instead of live network services or physical hardware.

## Import Boundary Negative Controls

Import boundary enforcement is verified by negative control test files in `tests/negcontrol/`:
- `tests/negcontrol/test_voice_imports_llm.py` — Verifies `import-linter` detects forbidden `voice ↔ llm` imports.
- `tests/negcontrol/test_langchain_leak.py` — Verifies `langchain` types cannot leak outside `paaf_llm._engine`.
- `tests/negcontrol/test_network_client_leak.py` — Verifies network client libraries (`httpx`, `requests`) are blocked in core packages.

## CI Integration

Continuous Integration is configured via `.github/workflows/ci.yml`:
- **Triggers**: Push to `main` and all Pull Requests.
- **Jobs**:
  1. `lint-imports`: Runs `uv run lint-imports` to enforce import architecture contracts.
  2. `test`: Runs `uv run pytest` to execute the full test suite with network isolation.
  3. `dco`: Enforces Developer Certificate of Origin (`Signed-off-by`) on commits.
