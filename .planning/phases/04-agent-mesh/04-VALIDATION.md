---
phase: 4
slug: agent-mesh
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-07
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

> Task IDs are assigned by the planner. The rows below are the **requirement-level** contract every
> plan must map its tasks onto — the planner fills `Task ID` / `Plan` / `Wave` and may split a row
> across tasks, but may not drop a row.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | MESH-01 | T-03-02 | No config key can express a routing rule; `extra="forbid"` rejects smuggled mesh fields | unit | `uv run pytest packages/paaf-llm/tests/test_profiles.py -k routing -x` | ❌ W0 (extends existing) | ⬜ pending |
| TBD | TBD | TBD | MESH-01 | — | A declared handoff tool is offered and the model's choice is followed | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k accepts_declared -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-02 | T-03-36 | Undeclared target → `UndeclaredPeer`, recorded, **not** followed | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k undeclared -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-02 | — | **Negative control:** a *declared* target is NOT blocked | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k declared_not_blocked -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-02 | — | Tool surface contains exactly the declared peers (capability removal) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k tool_surface -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-03 | — | Receiving agent's messages contain the full prior conversation | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k carries_history -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-03 | — | A→B→A hand-back works; conversation does not restart | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k hand_back -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-03 | — | No handoff tool call ever appears in `Agent.history` (Pitfall 1) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k history_clean -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-03 | — | Awake agent is sticky across user turns (within process, not persisted) | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k sticky -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-04 | — | Explainer generated from *this* agent's manifest + peers appears verbatim in `--provenance` | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k explainer -x` | ❌ W0 (extends existing) | ⬜ pending |
| TBD | TBD | TBD | MESH-04 | — | Two agents get genuinely different prompts (D-17) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k per_agent -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-04 | — | `compose()` still equals the joined segment texts (byte-exact invariant) | unit | `uv run pytest packages/paaf-llm/tests/test_compose.py -k byte_exact -x` | ✅ exists — **widen, do not replace** | ⬜ pending |
| TBD | TBD | TBD | MESH-04 | — | **Every** offered tool name + description appears in `--provenance` (PERS-05 made mechanical) | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k tool_surface_visible -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-04 | — | `paaf prompt --agent <name>` targets a non-awake peer, and the reserved observer | unit | `uv run pytest packages/paaf-llm/tests/test_inspector.py -k agent_flag -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-05 | — | One `runs` row per agent leg, correlated by `turn_id`; per-agent `fallback_trail` intact | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k legs -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-05 | — | Every handoff attempt recorded incl. rejected ones and observer verdicts | integration | `uv run pytest packages/paaf-llm/tests/test_mesh_trace.py -k attempts -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-05 | — | Schema applies cleanly to a **pre-existing** DB file (Pitfall 5) | integration | `uv run pytest packages/paaf-trace/tests/test_trace_schema.py -k reopen -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-06 | — | Observer vetoes a constraint-violating handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k vetoes -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-06 | — | **Negative control:** observer does NOT veto a good handoff | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k allows -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-06 | — | Observer re-route outside the caller's peers is rejected identically (D-06) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k reroute_guarded -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-06 | — | Observer without the re-route grant cannot re-route, whatever it emits (D-04) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k grant_bounds -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | MESH-06 | — | No `observer` profile → mesh runs unobserved and **says so** (D-07) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k unobserved_notice -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-08 | — | Hop budget stops a loop; handoff tool is withdrawn at the wall | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k budget -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | D-05 / OQ-1 | — | Correction signal is observable headlessly; veto retry-leg segment never enters `Agent.history` | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k correction_signal -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | OQ-2 | — | Budget exhaustion with no `default_agent` → awake agent answers, tools withdrawn, recorded | unit | `uv run pytest packages/paaf-llm/tests/test_mesh.py -k exhaustion_no_default -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | OQ-4 | — | Observer chain fully degraded → fail-open **with** D-07 notice + trace row (never silent) | unit | `uv run pytest packages/paaf-llm/tests/test_observer.py -k fail_open_loud -x` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | SC#4 | — | Each agent applies its **own** `fallback_chain`, nested inside the handoff loop | unit | `uv run pytest packages/paaf-llm/tests/test_fallback.py -k per_agent -x` | ❌ W0 (extends existing) | ⬜ pending |
| TBD | TBD | TBD | SC#5 | — | The entire mesh suite passes with the framework uninstalled | integration | `bash scripts/check_framework_uninstalled.sh` | ✅ script exists — force-include new files | ⬜ pending |
| TBD | TBD | TBD | SC#5 | — | No framework type leaks through any new public signature | unit | `uv run pytest packages/paaf-llm/tests/test_no_leak.py -x` | ✅ exists — auto-covers new exports | ⬜ pending |
| TBD | TBD | TBD | — | T-03-04 | `langchain*` stays confined to `_engine` | lint | `uv run lint-imports` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/paaf-llm/tests/test_mesh.py` — MESH-01 / MESH-02 / MESH-03 + hop budget + OQ-2
- [ ] `packages/paaf-llm/tests/test_observer.py` — MESH-06 + D-04 / D-05 / D-06 / D-07 + OQ-1 / OQ-4
- [ ] `packages/paaf-llm/tests/test_mesh_trace.py` — MESH-05
- [ ] `packages/paaf-trace/tests/test_trace_schema.py` — reopen-existing-DB case (Pitfall 5)
- [ ] Extend `packages/paaf-llm/tests/conftest.py` — a `make_mesh_config` fixture (peers, per-agent
      fallback chains, optional observer). The existing `make_llm_config` cannot express a peer graph.
- [ ] Extend `FakeAdapter` — scripted `tool_calls` plus a `tool_offers` recording seam. Without the
      recording seam the MESH-02 negative control (script a call to an un-offered tool) cannot be written.
- [ ] Add every new shipped test file to `[tool.hatch.build.targets.wheel.force-include]` in
      `packages/paaf-llm/pyproject.toml`
- [ ] Extend `tests/negcontrol/` if a new import boundary is introduced (**none expected**)
- [ ] Framework install: **not needed** — every dependency is already present and pinned

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live tool-call streaming on `langchain-ollama==1.1.0` (assumption A1) | — (non-blocking) | The pytest default is `--disable-socket --allow-unix-socket`, so a live-Ollama check cannot run as a plain test | Run a scratch script outside the suite against local `qwen3.5:2b` with tools bound; confirm tokens stream incrementally. **Non-blocking:** the mesh suite runs on `FakeAdapter`, so a negative result is an engine-adapter latency finding to log, not a phase blocker. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
