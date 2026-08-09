---
phase: "08"
plan: "02"
title: "Explicit Model Management CLI & Consent Gate (PRIV-06)"
completed: true
date: 2026-08-09
---

# Executive Summary — 08-02 Explicit Model Management CLI & Consent Gate (PRIV-06)

## Achievements

1. **Model Missing Safeguard & PRIV-06 Consent Gate**:
   - Created `paaf_voice.exceptions.ModelMissingError` inheriting from `VoiceError`.
   - Formatted exception messages to include exact CLI command instructions: `"STT model '{model_name}' for engine '{engine_name}' not found in {cache_dir}. Run 'paaf voice download-models --engine {engine_name} --model {model_name}' to download with explicit consent."`
   - Implemented `verify_model_present(engine_name, model_name, cache_dir)` helper to validate presence of model weights prior to engine boot.

2. **Model Management CLI Commands (`paaf voice`)**:
   - Created `src/paaf_voice/cli/models.py` with `download-models` and `list-models` Click command implementations.
   - Enforced target directory default at `~/.cache/paaf/models/`.
   - Integrated progress/status reporting using `rich` console styling.
   - Re-exported commands in `src/paaf_voice/cli/__init__.py` and mounted `voice_cli` on the main `paaf` CLI.

3. **Verification & Testing**:
   - Created `tests/test_model_cli.py` covering exception formatting, weight verification checks, `download-models` execution, and `list-models` outputs.
   - Verified that zero background auto-downloads occur during engine initialization.
   - All 59 tests in `packages/paaf-voice` passed cleanly.

## Key Files Modified

- `packages/paaf-voice/src/paaf_voice/exceptions.py`
- `packages/paaf-voice/src/paaf_voice/cli/models.py`
- `packages/paaf-voice/src/paaf_voice/cli/__init__.py`
- `packages/paaf-voice/src/paaf_voice/__init__.py`
- `packages/paaf-voice/pyproject.toml`
- `packages/paaf-llm/src/paaf_llm/cli.py`
- `packages/paaf-voice/tests/test_model_cli.py`

## Verification Command Results

```bash
uv run pytest packages/paaf-voice/tests/test_model_cli.py
# Output: 7 passed in 0.13s
```
