---
phase: 07
slug: paaf-voice-ports-fakes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-08
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest packages/paaf-voice/tests/` |
| **Full suite command** | `pytest packages/paaf-voice/tests/` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest packages/paaf-voice/tests/`
- **After every plan wave:** Run `pytest packages/paaf-voice/tests/`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | VOICE-01, VOICE-02 | ASVS-Buffer | Structural protocol compliance without external dependencies | unit | `pytest packages/paaf-voice/tests/test_ports.py` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | VOICE-11 | ASVS-Buffer | Deterministic playhead/sample tracking without hardware | unit | `pytest packages/paaf-voice/tests/test_fakes.py` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | VOICE-01, VOICE-02 | ASVS-Async | Engine test doubles state isolation & warmup lifecycle | unit | `pytest packages/paaf-voice/tests/test_fakes.py` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | VOICE-06 | ASVS-ReDoS | TTSSanitizer markdown/emoji/URL stripping | unit | `pytest packages/paaf-voice/tests/test_sanitizer.py` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 2 | VOICE-06 | ASVS-ReDoS | Unicode sentence boundary detection and abbreviation protection | unit | `pytest packages/paaf-voice/tests/test_aggregator.py` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 3 | VOICE-11 | ASVS-Resource | Hardware-free WAV test fixture generation & playback | integration | `pytest packages/paaf-voice/tests/test_wav_fixtures.py` | ❌ W0 | ⬜ pending |
| 07-04-02 | 04 | 3 | VOICE-06 | ASVS-Resource | TTFA reduction via short first-chunk threshold | benchmark | `pytest packages/paaf-voice/tests/test_ttfa_benchmark.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/paaf-voice/tests/test_ports.py` — stubs for VOICE-01, VOICE-02
- [ ] `packages/paaf-voice/tests/test_fakes.py` — stubs for VOICE-11
- [ ] `packages/paaf-voice/tests/test_aggregator.py` — stubs for VOICE-06
- [ ] `packages/paaf-voice/tests/test_sanitizer.py` — stubs for VOICE-06
- [ ] `packages/paaf-voice/tests/test_ttfa_benchmark.py` — stubs for VOICE-06
- [ ] `packages/paaf-voice/tests/test_wav_fixtures.py` — stubs for VOICE-11

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending 2026-08-08
