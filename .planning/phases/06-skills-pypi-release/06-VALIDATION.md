---
phase: 6
slug: skills-pypi-release
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-08
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest packages/paaf-llm/tests/test_skills.py` |
| **Full suite command** | `uv run pytest && ./scripts/check_release_venv.sh && uv run mkdocs build --strict` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/paaf-llm/tests/test_skills.py`
- **After every plan wave:** Run `uv run pytest && ./scripts/check_release_venv.sh`
- **Before `/gsd-verify-work`:** Full suite must be green (`pytest`, `check_release_venv.sh`, `mkdocs build --strict`)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | SKILL-01 | T-06-01 | Skill manifest parser validates permission declarations and tool signatures | unit | `uv run pytest packages/paaf-llm/tests/test_skills.py -k test_manifest` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | SKILL-02 | T-06-02 | Skill staging performs git clone into `.paaf/staging/<id>` and rolls back on failure | integration | `uv run pytest packages/paaf-llm/tests/test_skills.py -k test_staging` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | SKILL-03 | T-06-03 | Skill install CLI shows interactive permissions review and security disclosure | integration | `uv run pytest packages/paaf-llm/tests/test_skills.py -k test_install_cli` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | SKILL-04 | T-06-04 | Enable/disable skill updates `paaf.yaml` and hot-reloads tool registry & prompt composer | integration | `uv run pytest packages/paaf-llm/tests/test_skills.py -k test_enable_disable` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | SKILL-05 | T-06-05 | System prompt includes mandatory security disclosure regarding in-process skill execution | unit | `uv run pytest packages/paaf-llm/tests/test_skills.py -k test_security_disclosure` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 2 | OSS-01 | T-06-06 | Monolithic `paaf` wheel builds and installs cleanly in an isolated venv | integration | `./scripts/check_release_venv.sh` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 2 | OSS-02 | T-06-07 | MkDocs documentation site builds strictly with no broken links or missing sections | docs | `uv run mkdocs build --strict` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/paaf-llm/tests/test_skills.py` — stubs for SKILL-01..05
- [ ] `scripts/check_release_venv.sh` — clean venv release verification script
- [ ] `mkdocs.yml` — MkDocs Material documentation configuration

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive terminal prompt approval | SKILL-03 | CLI prompt interactive input stream | Run `paaf skill install <git-url>` in interactive terminal and verify prompt display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
