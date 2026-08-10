---
phase: 09
slug: paaf-session
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-09
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest packages/paaf-session/tests/test_state_machine.py` |
| **Full suite command** | `uv run pytest packages/paaf-session/tests` |
| **Estimated runtime** | ~1.5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 9 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | SESS-01, SESS-08 | T-09-01 | Enforce timeout boundary | unit | `uv run pytest packages/paaf-session/tests/test_state_machine.py -k test_happy_path_turn_loop` | ✅ | ✅ green |
| 09-01-02 | 01 | 1 | SESS-02 | — | N/A | unit | `uv run pytest packages/paaf-session/tests/test_state_machine.py -k test_streaming_tts_starts_early` | ✅ | ✅ green |
| 09-01-03 | 01 | 1 | SESS-09 | — | N/A | unit | `uv run pytest packages/paaf-session/tests/test_state_machine.py -k test_follow_up_window_timeout` | ✅ | ✅ green |
| 09-02-01 | 02 | 2 | SESS-03 | — | N/A | unit | `uv run pytest packages/paaf-session/tests/test_barge_in.py -k test_barge_in_cancellation` | ✅ | ✅ green |
| 09-02-02 | 02 | 2 | SESS-04 | T-09-02 | Safe truncation | unit | `uv run pytest packages/paaf-session/tests/test_barge_in.py -k test_history_truncation` | ✅ | ✅ green |
| 09-03-01 | 03 | 3 | SESS-05 | — | N/A | unit | `uv run pytest packages/paaf-session/tests/test_audio_arbitration.py` | ✅ | ✅ green |
| 09-03-02 | 03 | 3 | SESS-06 | T-09-03 | declarative execution | unit | `uv run pytest packages/paaf-session/tests/test_behaviors.py -k test_timeout_escalation` | ✅ | ✅ green |
| 09-03-03 | 03 | 3 | SESS-07 | — | N/A | unit | `uv run pytest packages/paaf-session/tests/test_behaviors.py -k test_error_wake_behaviors` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 9s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-10

---

## Validation Audit 2026-08-10
| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
