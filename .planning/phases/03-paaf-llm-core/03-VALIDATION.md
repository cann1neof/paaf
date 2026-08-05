---
phase: 3
slug: paaf-llm-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md` § Validation Architecture. Negative-control discipline (Phase 1/2): a check that cannot fail is not a check.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode=auto`) |
| **Config file** | `/pyproject.toml` `[tool.pytest.ini_options]` — `--disable-socket --allow-unix-socket --import-mode=importlib`, `testpaths=["packages"]` |
| **Quick run command** | `uv run pytest packages/paaf-llm -q` |
| **Full suite command** | `uv run pytest -q` |
| **Framework-uninstalled job** | install `paaf-llm` wheel **without** `[engine]`, then `uv run pytest --pyargs paaf_llm` (extends the Phase-2 clean-venv wheel job) |
| **Estimated runtime** | ~sub-second (fake-adapter unit suite, no network) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest packages/paaf-llm -q` (fake-adapter unit suite; sub-second, no network)
- **After every plan wave:** Run `uv run pytest -q` (whole workspace)
- **Before `/gsd-verify-work`:** Full suite green **AND** the framework-uninstalled job green (SC#1 is not satisfied until both pass)
- **Max feedback latency:** ~5 seconds (quick suite)

---

## Per-Task Verification Map

> Task IDs are assigned by the planner; rows below key on requirement + behavior from research. All start as Wave 0 gaps (test files do not exist yet).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | — | 0 | MODEL-08 / SC#1 | — | Full suite passes with LangChain uninstalled | integration | `pytest --pyargs paaf_llm` (venv without `[engine]`) | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-08 | — | No framework type in any public signature | unit | `pytest packages/paaf-llm/tests/test_no_leak.py` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-03 | — | Fallback FIRES on connection failure mid-conversation; history carries across | unit | `pytest -k test_fallback_connection` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-04 | — | Fallback FIRES on timeout, 5xx, 429, slow-first-token (4 positive) | unit | `pytest -k "test_fallback_degraded"` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-04 | — | **Negative control:** a HEALTHY provider does NOT fall back | unit | `pytest -k test_healthy_no_fallback` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-05 | — | Undeclared peer / fallback target rejected at config load | unit | `pytest -k test_peer_validation` (expects `ValidationError`) | ❌ W0 | ⬜ pending |
| TBD | — | 0 | MODEL-06 | — | Two same-provider LAN profiles are distinct and each classifies LAN | unit | `pytest -k test_two_lan_profiles` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | PERS-04 | — | `paaf prompt` / `--show-prompt` output == string the engine sent (byte-identity) | unit | `pytest -k test_prompt_byte_exact` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | PERS-05 | — | Composed prompt == base + fragments and nothing else; `join(segments)==compose()` | unit | `pytest -k test_no_hidden_prompt` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | D-06 | — | Each fallback trigger reason lands in the trace | integration | `pytest -k test_fallback_traced` | ❌ W0 | ⬜ pending |
| TBD | — | 0 | SPIKE-05 tie-in | — | Token usage read post-aggregation is non-None (fake reports usage once) | unit | `pytest -k test_usage_aggregated` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/paaf-llm/tests/conftest.py` — shared `FakeAdapter` programming fixtures + an async `TraceStore` fixture
- [ ] `packages/paaf-llm/tests/test_no_leak.py` — public-signature PAAF-only assertion (`__init__` exports + `inspect.signature`)
- [ ] `packages/paaf-llm/tests/test_fallback.py` — 4 positive triggers + 1 healthy negative control + history-carries-across
- [ ] `packages/paaf-llm/tests/test_prompt.py` — byte-exact + no-hidden-prompt invariants
- [ ] `packages/paaf-llm/tests/test_profiles.py` — peer/fallback/active cross-ref validation + two-LAN-profiles
- [ ] CI: framework-uninstalled job (extend `.github/workflows/ci.yml` wheel job to run the full `paaf_llm` suite without `[engine]`)
- [ ] `.importlinter`: add the `_engine` whitelist + the three provider modules (`langchain_ollama`/`_anthropic`/`_openai`) to `forbidden_modules`; a negative-control proving a stray provider import fails CI
- [ ] `packages/paaf-trace` schema: additive `served_by` + `fallback_trail` columns (or a `fallbacks` table) + a schema test

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real Ollama / Anthropic / OpenAI-compatible round-trip | MODEL-01/02 | Requires live providers + network; excluded from the socket-disabled CI suite | With Ollama running and API keys set, name profiles in YAML and run `paaf chat`; confirm each profile answers |
| Slow-first-token budget does not false-trigger a legitimately slow cold local model | MODEL-04 / D-05 | Timing behavior against a real cold-loading model can't be asserted deterministically offline | Cold-start a 14B Ollama model, send first turn, confirm no spurious fallback within the configured budget |

*Automated coverage establishes correctness (fake adapter); manual checks confirm the real adapters wire up.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
