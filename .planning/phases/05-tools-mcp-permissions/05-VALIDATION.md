---
phase: 5
slug: tools-mcp-permissions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-08
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `pytest tests/test_tools.py` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_tools.py`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | TOOL-01, TOOL-08 | — | Built-in tools registered and peer graph fed into prompt | unit | `pytest tests/test_tools.py` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | TOOL-02 | — | @tool decorator inspects signature & schema | unit | `pytest tests/test_tools.py` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | TOOL-03, TOOL-04 | — | MCP config loaded & added to unified registry | unit | `pytest tests/test_mcp.py` | ❌ W0 | ⬜ pending |
| 05-01-04 | 01 | 1 | TOOL-05, TOOL-06 | T-05-01 | Confirmation tier prompts out loud & waits for approval | unit | `pytest tests/test_permissions.py` | ❌ W0 | ⬜ pending |
| 05-01-05 | 01 | 1 | TOOL-07 | T-05-02 | CI test verifies zero defensive prompt injection strings | unit | `pytest tests/test_security_governance.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tools.py` — stubs for TOOL-01, TOOL-02, TOOL-08
- [ ] `tests/test_mcp.py` — stubs for TOOL-03, TOOL-04
- [ ] `tests/test_permissions.py` — stubs for TOOL-05, TOOL-06
- [ ] `tests/test_security_governance.py` — stubs for TOOL-07

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|

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
