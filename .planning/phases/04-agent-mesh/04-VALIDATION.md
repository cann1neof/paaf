---
phase: 4
slug: agent-mesh
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-07
completed: 2026-08-08
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-asyncio 1.4.0 (`asyncio_mode = "auto"`) |
| **Config file** | `/pyproject.toml` `[tool.pytest.ini_options]` — `--disable-socket --allow-unix-socket --import-mode=importlib -p no:langsmith_plugin`, `testpaths = ["packages"]` |
| **Quick run command** | `uv run pytest packages/paaf-llm -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5 seconds (fake-adapter suite is sub-second; full suite ~5s) |

**Additional phase gates (not part of the normal suite):**

| Gate | Command | Why it is separate |
|------|---------|--------------------|
| Framework-uninstalled (SC#5) | `bash scripts/check_framework_uninstalled.sh` | Runs `pytest --pyargs paaf_llm` in a clean venv. **SC#5 is stated in terms of this gate — the phase is not done without it green.** |
| Engine-adapter | `uv sync --extra engine && uv run pytest packages/paaf-llm/tests/test_engine_adapter.py` | Only lane where `langchain*` is installed |
| Import confinement | `uv run lint-imports` | Enforces `langchain*` confined to `paaf_llm._engine` |

**⚠ Packaging step that must not be missed.** Every new mesh test file that must run in the
framework-uninstalled lane has to be added to `[tool.hatch.build.targets.wheel.force-include]` in
`packages/paaf-llm/pyproject.toml` — the shipped suite is an explicit file list, **not a glob**. A new
`test_mesh.py` that is not listed will pass locally and be invisible to the SC#5 gate. Such files may
import only `paaf_llm` + `paaf_core` + `paaf_trace` and their declared deps.

---

## Sampling Rate

- **After every task commit:** `uv run pytest packages/paaf-llm -q`
- **After every plan wave:** `uv run pytest -q` + `uv run lint-imports`
- **Before `/gsd-verify-work`:** full suite green **AND** `framework-uninstalled` green **AND**
  `engine-adapter` green **AND** `ttfa-gate` unbreached
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-1 | 04-01 | 1 | MESH-01 | T-03-02 | No config key can express a routing rule; `extra="forbid"` rejects smuggled mesh fields | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k rules -x` | ✅ | ✅ green |
| 04-01-2 | 04-01 | 1 | MESH-01 | — | A declared handoff tool is offered and the model's choice is followed | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k tool -x` | ✅ | ✅ green |
| 04-01-2 | 04-01 | 1 | MESH-02 | T-03-36 | Undeclared target → `UndeclaredPeer`, recorded, **not** followed | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k undeclared -x` | ✅ | ✅ green |
| 04-01-2 | 04-01 | 1 | MESH-02 | — | **Negative control:** a *declared* target is NOT blocked | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k tool -x` | ✅ | ✅ green |
| 04-01-2 | 04-01 | 1 | MESH-02 | — | Tool surface contains exactly the declared peers (capability removal) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k surface -x` | ✅ | ✅ green |
| 04-06-1 | 04-06 | 5 | MESH-03 | — | Receiving agent's messages contain the full prior conversation | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k conversation -x` | ✅ | ✅ green |
| 04-06-1 | 04-06 | 5 | MESH-03 | — | A→B→A hand-back works; conversation does not restart | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k repeat -x` | ✅ | ✅ green |
| 04-06-1 | 04-06 | 5 | MESH-03 | — | No handoff tool call ever appears in `Agent.history` (Pitfall 1) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k history -x` | ✅ | ✅ green |
| 04-06-1 | 04-06 | 5 | MESH-03 | — | Awake agent is sticky across user turns (within process, not persisted) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k sticky -x` | ✅ | ✅ green |
| 04-05-1 | 04-05 | 4 | MESH-04 | — | Explainer generated from *this* agent's manifest + peers appears verbatim in `--provenance` | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k explainer -x` | ✅ | ✅ green |
| 04-05-1 | 04-05 | 4 | MESH-04 | — | Two agents get genuinely different prompts (D-17) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k per_agent -x` | ✅ | ✅ green |
| 04-05-1 | 04-05 | 4 | MESH-04 | — | `compose()` still equals the joined segment texts (byte-exact invariant) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k byte_exact -x` | ✅ | ✅ green |
| 04-05-1 | 04-05 | 4 | MESH-04 | — | **Every** offered tool name + description appears in `--provenance` (PERS-05 made mechanical) | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k tool_surface_visible -x` | ✅ | ✅ green |
| 04-05-1 | 04-05 | 4 | MESH-04 | — | `paaf prompt --agent <name>` targets a non-awake peer, and the reserved observer | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k agent_flag -x` | ✅ | ✅ green |
| 04-02-1 | 04-02 | 2 | MESH-05 | — | One `runs` row per agent leg, correlated by `turn_id`; per-agent `fallback_trail` intact | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k legs -x` | ✅ | ✅ green |
| 04-02-1 | 04-02 | 2 | MESH-05 | — | Every handoff attempt recorded incl. rejected ones and observer verdicts | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k attempts -x` | ✅ | ✅ green |
| 04-02-1 | 04-02 | 2 | MESH-05 | — | Schema applies cleanly to a **pre-existing** DB file (Pitfall 5) | integration | `uv run pytest packages/paaf-trace/tests/test_trace_schema.py -k reopen -x` | ✅ | ✅ green |
| 04-07-2 | 04-07 | 6 | MESH-06 | — | Observer vetoes a constraint-violating handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k vetoes -x` | ✅ | ✅ green |
| 04-07-2 | 04-07 | 6 | MESH-06 | — | **Negative control:** observer does NOT veto a good handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k allows -x` | ✅ | ✅ green |
| 04-07-3 | 04-07 | 6 | MESH-06 | — | Observer re-route outside the caller's peers is rejected identically (D-06) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k reroute_guarded -x` | ✅ | ✅ green |
| 04-07-2 | 04-07 | 6 | MESH-06 | — | Observer without the re-route grant cannot re-route, whatever it emits (D-04) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k grant_bounds -x` | ✅ | ✅ green |
| 04-08-1 | 04-08 | 6 | MESH-06 | — | No `observer` profile → mesh runs unobserved and **says so** (D-07) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k unobserved_notice -x` | ✅ | ✅ green |
| 04-03-1 | 04-03 | 3 | D-08 | — | Hop budget stops a loop; handoff tool is withdrawn at the wall | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k budget -x` | ✅ | ✅ green |
| 04-08-3 | 04-08 | 6 | D-05 / OQ-1 | — | Correction signal is observable headlessly; veto retry-leg segment never enters `Agent.history` | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k correction_signal -x` | ✅ | ✅ green |
| 04-03-2 | 04-03 | 3 | OQ-2 | — | Budget exhaustion with no `default_agent` → awake agent answers, tools withdrawn, recorded | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k exhaustion -x` | ✅ | ✅ green |
| 04-08-2 | 04-08 | 6 | OQ-4 | — | Observer chain fully degraded → fail-open **with** D-07 notice + trace row (never silent) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k fail_open_loud -x` | ✅ | ✅ green |
| 04-04-1 | 04-04 | 3 | SC#4 | — | Each agent applies its **own** `fallback_chain`, nested inside the handoff loop | unit | `uv run pytest packages/paaf-llm/tests/test_fallback.py -k per_agent -x` | ✅ | ✅ green |
| 04-08-3 | 04-08 | 6 | SC#5 | — | The entire mesh suite passes with the framework uninstalled | integration | `bash scripts/check_framework_uninstalled.sh` | ✅ | ✅ green |
| 04-01-1 | 04-01 | 1 | SC#5 | — | No framework type leaks through any new public signature | unit | `uv run pytest packages/paaf-llm/tests/test_no_leak.py -x` | ✅ | ✅ green |
| 04-01-1 | 04-01 | 1 | — | T-03-04 | `langchain*` stays confined to `_engine` | lint | `uv run lint-imports` | ✅ | ✅ green |

---

## Wave 0 Requirements

- [x] `packages/paaf-llm/tests/test_mesh.py` — MESH-01 / MESH-02 / MESH-03 + hop budget + OQ-2
- [x] `packages/paaf-llm/tests/test_observer.py` — MESH-06 + D-04 / D-05 / D-06 / D-07 + OQ-1 / OQ-4
- [x] `packages/paaf-llm/tests/test_mesh_trace.py` — MESH-05
- [x] `packages/paaf-trace/tests/test_trace_schema.py` — reopen-existing-DB case (Pitfall 5)
- [x] Extend `packages/paaf-llm/tests/conftest.py` — a `make_mesh_config` fixture (peers, per-agent
      fallback chains, optional observer).
- [x] Extend `FakeAdapter` — scripted `tool_calls` plus a `tool_offers` recording seam.
- [x] Add every new shipped test file to `[tool.hatch.build.targets.wheel.force-include]` in
      `packages/paaf-llm/pyproject.toml`
- [x] Extend `tests/negcontrol/` if a new import boundary is introduced (**none needed**)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live tool-call streaming on `langchain-ollama==1.1.0` (assumption A1) | — (non-blocking) | The pytest default is `--disable-socket --allow-unix-socket`, so a live-Ollama check cannot run as a plain test | Measured in Plan 04-04 (Assumption A1 finding: 30/30 tool calls executed reliably). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** COMPLETE (2026-08-08)
