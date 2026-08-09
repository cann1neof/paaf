---
phase: 8
slug: real-engines-live-audio
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-09
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `packages/paaf-voice/pyproject.toml` |
| **Quick run command** | `uv run pytest packages/paaf-voice/tests/unit/ -x` |
| **Full suite command** | `uv run pytest packages/paaf-voice/tests/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/paaf-voice/tests/unit/ -x`
- **After every plan wave:** Run `uv run pytest packages/paaf-voice/tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | VOICE-03 | T-08-01 | Pluggable STT dynamic engine registry | unit | `uv run pytest packages/paaf-voice/tests/unit/test_engine_registry.py` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | VOICE-03 | T-08-02 | FasterWhisperSTT & WhisperCppSTT adapter implementations | unit | `uv run pytest packages/paaf-voice/tests/unit/test_stt_engines.py` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | PRIV-06 | T-08-03 | Explicit CLI model download & missing weight error gate | unit | `uv run pytest packages/paaf-voice/tests/unit/test_model_cli.py` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | VOICE-09 | T-08-04 | sounddevice mic/speaker streaming, resampler, playhead & tap | unit | `uv run pytest packages/paaf-voice/tests/unit/test_audio_io.py` | ❌ W0 | ⬜ pending |
| 08-04-01 | 04 | 4 | VOICE-07, VOICE-08 | T-08-05 | openWakeWord & Silero VAD dual threshold continuous sensing | unit | `uv run pytest packages/paaf-voice/tests/unit/test_wakeword_vad.py` | ❌ W0 | ⬜ pending |
| 08-05-01 | 05 | 5 | VOICE-04, VOICE-05, VOICE-10, VOICE-12 | T-08-06 | ChatterboxTTS, engine warmup dummy pass & watermarking docs | unit | `uv run pytest packages/paaf-voice/tests/unit/test_tts_warmup.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/paaf-voice/tests/unit/test_engine_registry.py` — registry & factory tests
- [ ] `packages/paaf-voice/tests/unit/test_stt_engines.py` — STT engine unit tests with WAV fixtures
- [ ] `packages/paaf-voice/tests/unit/test_model_cli.py` — CLI download consent and ModelMissingError tests
- [ ] `packages/paaf-voice/tests/unit/test_audio_io.py` — sounddevice I/O and resampler tests
- [ ] `packages/paaf-voice/tests/unit/test_wakeword_vad.py` — wake word and continuous VAD tests
- [ ] `packages/paaf-voice/tests/unit/test_tts_warmup.py` — TTS synthesis, warmup gate, and doc tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real mic hardware capture on Raspberry Pi | VOICE-09 | Requires physical USB microphone hardware | Run `paaf voice list-devices` and test live audio loopback on Raspberry Pi |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-08-09
