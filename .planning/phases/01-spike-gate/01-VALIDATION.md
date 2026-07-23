---
phase: 1
slug: spike-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Phase 1 produces measurements, not shipped behavior. "Tests" here are **harness
> self-checks that protect the validity of the measurements** — they verify the
> instrument, not a product. Per SC#5 they are deleted with the rest of `spike/`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + `pytest-asyncio` (CLAUDE.md §Development Tools) |
| **Config file** | none — Wave 0 installs (config lives **inside `spike/`**, never repo root) |
| **Quick run command** | `uv run pytest spike/ -x -q` (excludes `slow`; no model inference) |
| **Full suite command** | `uv run pytest spike/ -q` (includes `slow` / model-touching) |
| **Estimated runtime** | quick ~5s · full (with model inference) minutes |

⚠️ **Do not create a root `pyproject.toml`/`pytest.ini` in Phase 1.** FOUND-01 (Phase 2)
establishes the uv workspace; CONTEXT.md is explicit that Phase 1 "must not anticipate
that structure." Keep pytest config inside `spike/` so it is removed with the directory.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest spike/ -x -q` (fast; model-touching tests marked `@pytest.mark.slow`)
- **After every plan wave:** Run `uv run pytest spike/ -q` including `slow`
- **Phase gate:** **Gate 0 green before any corpus render**; full suite green before `/gsd-verify-work`
- **Max feedback latency:** < 10s for the quick suite

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| SPIKE-01 | Corpus satisfies the D-02/D-03 grid (all 6 categories present; each of en/ru/he/es appears as both matrix and embedded) | unit | `pytest spike/voice/test_corpus_grid.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-01 | `SUPPORTED_LANGUAGES` contains en/ru/he/es; unknown tag raises `ValueError` | unit | `pytest spike/voice/test_lang_ids.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-02 | **Gate 0:** `dicta_onnx` imports, `Dicta()` mutates Hebrew text, no degradation warning fires | unit | `pytest spike/voice/test_readiness.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-02 | `russian_text_stresser` absence is detected and recorded, not silently absorbed | unit | `pytest spike/voice/test_readiness.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-02 | Blind shuffle is reversible: mapping.json round-trips every clip to its `language_id` (D-14) | unit | `pytest spike/voice/test_blind_mapping.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-03 | Timing harness excludes model load (warm run asserted faster than cold by a wide margin) | integration | `pytest spike/voice/test_ttfa_harness.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-04 | Transcribe harness runs both `multilingual` conditions and captures per-segment language probs | integration | `pytest spike/voice/test_transcribe_harness.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-05 | Trace handler implements **both** `on_chat_model_start` and `on_llm_start`; usage read post-aggregation | unit (fake model) | `pytest spike/bakeoff/test_trace_handler.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-06 | `on_tool_end` capture retains the `artifact` half of `content_and_artifact` | unit (fake tool) | `pytest spike/bakeoff/test_artifact_capture.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-07 | Both adapters satisfy the same port protocol (structural conformance) | unit | `pytest spike/bakeoff/test_port_conformance.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-08 | Per-stage timings sum to wall clock within tolerance (`t_unattributed` ≈ 0) | integration | `pytest spike/voice/test_roundtrip_accounting.py -x` | ❌ W0 | ⬜ pending |
| SPIKE-09 | RESULTS.md exists and is committed **before** DECISIONS.md conclusions (D-09 ordering) | manual | git log inspection | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Python 3.12 toolchain: `uv python install 3.12` — **blocking, provisioning task** (machine has 3.9.6 only)
- [ ] Framework install: `uv pip install pytest pytest-asyncio` (inside the `spike/` venv)
- [ ] `spike/pytest.ini` (or `[tool.pytest.ini_options]` **inside `spike/`**, not at repo root) — with a `slow` marker
- [ ] `spike/conftest.py` — shared fixtures: tmp corpus, fake model, fake tool, device parametrization
- [ ] All 11 test files listed in the verification map above

*Wave 0 is unusually heavy here because the repo is greenfield and the toolchain is unprovisioned — see the environment blockers folded into Wave 1.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Native-ear Hebrew verdict, recorded verbatim | SPIKE-02 / D-13 | Irreducibly human; automation would defeat the requirement | Listen blind (D-14), record verbatim impressions per clip into RESULTS.md |
| Russian/Spanish spot-checks | D-20 | Same as above | Spot-listen ru/es clips; record any catastrophic problem |
| SC#4 claim audit | SPIKE-09 | Reading repo prose against measurements is a judgment task | Read every public claim (README included) against RESULTS.md; no claim may exceed measured reality |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (quick suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
