---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 04
current_phase_name: Agent Mesh
status: executing
stopped_at: Completed 04-07-PLAN.md
last_updated: "2026-08-07T11:17:03.481Z"
last_activity: 2026-08-07
last_activity_desc: 04-05 complete (per-agent prompts, generated explainer, visible tool surface)
progress:
  total_phases: 13
  completed_phases: 3
  total_plans: 41
  completed_plans: 39
  percent: 23
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-19)

**Core value:** The user owns the assistant's mind — they pick the model, write its persona, install its skills, expose its tools, and decide what it does while it thinks, without writing code and with nothing hidden from them.
**Current focus:** Phase 04 — Agent Mesh

## Current Position

Phase: 04 (Agent Mesh) — EXECUTING
Plan: 8 of 9
Status: Ready to execute
Last activity: 2026-08-07 — 04-07 complete (the observer: bounded by its tool grant, confined to the caller's peer graph)

Progress: [████████░░] 78%  (7/9 plans in phase 04)

## Performance Metrics

**Velocity:**

- Total plans completed: 19
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 10 | - | - |
| 02 | 9 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 12min | 2 tasks | 7 files |
| Phase 01 P02 | 6min | 3 tasks | 4 files |
| Phase 01 P03 | 35min | 3 tasks | 5 files |
| Phase 01 P04 | 25min | 3 tasks | 5 files |
| Phase 01 P05 | 26min | 2 tasks | 9 files |
| Phase 01 P07 | 39min | 2 tasks | 5 files |
| Phase 01 P09 | 37min | 2 tasks | 7 files |
| Phase 01 P10 | 15min | 2 tasks | 5 files |
| Phase 02 P01 | 15min | 2 tasks | 20 files |
| Phase 02 P02 | 12min | 3 tasks | 10 files |
| Phase 02 P03 | 5min | 2 tasks | 5 files |
| Phase 02 P04 | 3min | 2 tasks | 8 files |
| Phase 02 P05 | 3min | 2 tasks | 4 files |
| Phase 02 P06 | 8min | 1 tasks | 3 files |
| Phase 02 P07 | 25min | 3 tasks | 8 files |
| Phase 02 P08 | 4min | 3 tasks | 7 files |
| Phase 02 P09 | 12min | 2 tasks | 4 files |
| Phase 04 P01 | 50m | 3 tasks | 11 files |
| Phase 04 P02 | ~35 min | 2 tasks | 6 files |
| Phase 04 P03 | ~30 min | 3 tasks | 9 files |
| Phase 04 P04 | 25min | 2 tasks | 4 files |
| Phase 04 P05 | 55min | 3 tasks | 9 files |
| Phase 04 P06 | ~65 min | 3 tasks | 9 files |
| Phase 04 P07 | ~70 min | 3 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Phase 1 is throwaway spike code. Nothing ships from it; its exit gate constrains every later public claim about multilingual behavior.
- [Roadmap]: Fake adapters precede real implementations in both `paaf-llm` (Phase 3) and `paaf-voice` (Phase 6). A port with one implementation is a mirror.
- [Roadmap]: Import contracts (FOUND-04), endpoint declaration (CORE-05) and the TTFA CI gate (TRACE-04) all land in Phase 2 — retrofitting any of them is an unwinnable audit.
- [Roadmap]: `paaf-llm` ships to PyPI in Phase 5, mid-roadmap, as burnout mitigation — not at launch.
- [Roadmap]: Only Phase 12 is hardware-gated. AEC quality, far-field accuracy, real-device latency, and GPIO are the only four things needing the target device.
- [Phase ?]: [01-01] Phase 1 throwaway code is quarantined under spike/; SC#5 is enforceable by one 'ls'. Test config lives INSIDE spike/ — no root pyproject.toml, pytest.ini or .venv, since Phase 2 (FOUND-01) owns the uv workspace.
- [Phase ?]: [01-01] Toolchain baseline: uv 0.11.31, CPython 3.12.13, ffmpeg 8.1.2, pytest 9.1.1 + pytest-asyncio 1.4.0 in spike/.venv. Canonical test command is 'uv run --python spike/.venv/bin/python pytest spike/ -q' — a bare 'uv run' cannot resolve without a root project.
- [Phase ?]: [01-01] Shared spike fixtures import stdlib + pytest only, so they collect in both the voice and bake-off venvs. The device fixture yields the STRINGS 'cpu'/'mps' because Chatterbox compares device by string equality despite its torch.device type hint.
- [Phase 01]: Corpus same-script category uses Cyrillic/Latin homoglyph pairs (РЕСТОРАН vs PECTOPAH), never Latin transliteration of Russian — Transliteration bypasses Chatterbox's russian_text_stresser / add_hebrew_diacritics paths entirely, so the spike would measure a pipeline it never ran (01-RESEARCH Pitfall 1)
- [Phase 01]: D-14 blindness is enforced structurally: shuffle_blind refuses to write mapping.json inside the directory being judged, and seed is keyword-only with no default — A mapping next to the clips defeats the blind pass in the most banal way; an unseeded shuffle makes the listening order unreproducible for Phase 7's re-run-and-diff (D-07)
- [Phase 01]: SPIKE-01 left unchecked after 01-02 — this plan builds the measuring instrument, plan 01-05 takes the measurement — SPIKE-01 says 'Measure whether Chatterbox handles intra-sentence code-switching'; no model was loaded here, and a premature checkbox is exactly what the SC#4 claim audit exists to catch
- [Phase 01]: GATE 0 is GREEN: Hebrew is synthesized WITH diacritics, usable device is mps, and seeded synthesis is bitwise identical so D-07's re-run-and-diff promise holds — Gate 0 must pass before any Hebrew clip reaches a native ear (Pitfall 1); MPS working contradicts the pessimistic prior and removes the expected CPU fallback
- [Phase 01]: UPSTREAM DEFECT: chatterbox-tts 0.1.7 calls Dicta() with no args while every dicta-onnx release requires model_path, and swallows the TypeError — 'pip install dicta-onnx' alone does NOT fix Pitfall 1 — The TypeError falls to except Exception, not except ImportError, so a different warning fires than Pitfall 1 says to watch for while Hebrew still reaches the model unvocalized; the repair seeds chatterbox's _dicta global so the measured pipeline stays the intended one
- [Phase 01]: Every Hebrew result must be attributed to CONFIG_REPAIRED, with CONFIG_DEFAULT reported separately as what a plain pip install yields — D-05: what an ordinary user gets is itself a finding; naming both configurations stops any result being quoted without its assembly
- [Phase 01]: Ollama model default RE-CHECKED and CHANGED: plain qwen3 is no longer in the top-20 tool-capable models, and qwen3.6 is disqualified because its ladder starts at 27b/17GB on an 18GB machine. Chose qwen3.5:9b (capability, SPIKE-05/06/07) + qwen3.5:2b (latency, SPIKE-08), both tools-capable and Apache-2.0, pinned by explicit tag never latest
- [Phase 01]: TOOL-CALL GATE GREEN: 30/30 well-formed calls, 100% in every condition, both models, via both the raw ollama client and init_chat_model
- [Phase 01]: PRIVACY BUG: the ollama python client 0.6.2 list() pydantic schema silently drops capabilities, so the PRIV-02 no-cloud check passed VACUOUSLY for every tag including the real qwen3.5:cloud. capabilities_of now reads /api/show and treats an empty list as an error
- [Phase 01]: Telemetry-off is enforced at TWO levels: langsmith and logfire-api ship as hard transitive deps of langchain and pydantic-ai, so env vars alone cannot establish PRIV-02. Runtime state is asserted and the plan's four vars were extended to nine incl. OTEL_EXPORTER_OTLP_ENDPOINT
- [Phase 01]: Held pydantic-ai-slim at 2.13.0 rather than today's 2.16.0. Cadence recorded as Decision-1 evidence: pydantic-ai shipped 7 minors in 9 days, langchain 8 patches in 43 days and is still on 1.3.x
- [Phase ?]: SPIKE-04: Whisper large-v3 locks to one language per clip; multilingual=True does not unlock code-switching (posterior identical 46/46). Embedded language transliterated/garbled into Latin unless locked to a non-Latin language; task=translate flattens to English. D-05 caveat binding: synthetic Chatterbox speech, Chatterbox/Whisper failures inseparable.
- [Phase ?]: Phase 1 exits with data only: LangChain stands (MCP falsifier negative); Hebrew verdict + fallback rung PENDING (01-08 unexecuted)
- [Phase 02]: [02-01] pytest-socket pinned to 0.7.0 (uv-resolved); closes RESEARCH A3 unpinned item and threat T-02-SC
- [Phase 02]: [02-01] Added pytest --import-mode=importlib so five identically-named test_smoke.py modules coexist without __init__.py (Rule 3 blocking auto-fix)
- [Phase 02]: [02-01] Virtual workspace root (tool.uv package=false); requires-python >=3.12 resolved to 3.12.13; apps not scaffolded (D-07)
- [Phase ?]: Force-include the paaf-llm wheel-smoke test into the wheel so pytest --pyargs finds it in a clean venv (Plan 02-03)
- [Phase ?]: Scope the isolation-only wheel-smoke test out of the workspace suite via conftest collect_ignore_glob (Plan 02-03)
- [Phase 02]: [02-04] Config subsystem: AppConfig (Pydantic v2, extra=forbid) validates on read/write; atomic_write_bytes does temp+fsync+os.replace+dirfsync; write_config gates a monotonic revision inside a FileLock and raises ConflictError on stale writes; reload_tiers() discovers per-field HOT/WARM/COLD/RESTART, unannotated fields default to RESTART
- [Phase 02]: Master-key provisioning source = passphrase-at-boot (02-05) — Strongest option: key derived from passphrase via scrypt at unlock, never at rest (only per-store salt persisted). TRADEOFF: breaks unattended headless restart — every service (re)start needs the passphrase; Phase 9 (APP-*) owns boot-time delivery. key-file-0600/systemd-credential addable later without interface change.
- [Phase 02]: CORE-05: network locality classified via stdlib ipaddress + .local/localhost suffix, never DNS (offline-safe under --disable-socket); EndpointRegistry.non_lan_endpoints() is the exact set Phase-9 APP-08 will refuse
- [Phase ?]: Trace store: single _writer task owns the aiosqlite connection; emit() is synchronous put_nowait + drop-counter so audio never stalls (TRACE-01)
- [Phase ?]: time_to_first_audio is a first-class REAL column on runs; recorded via TtfaUpdate through the writer (TRACE-03)
- [Phase ?]: Added --allow-unix-socket to test addopts: asyncio self-pipe allowed, AF_INET egress still blocked (TRACE-05 preserved)
- [Phase ?]: App license recorded as OPEN governance question — framework Apache-2.0 locked, apps default Apache-2.0 v1, AGPL not chosen (Plan 08)
- [Phase ?]: Governance rot-guard (tests/test_governance.py) globs packages/*/src/**/*.py and fails CI on any source file missing the SPDX Apache-2.0 header (FOUND-07, Plan 08)
- [Phase 02]: TTFA accuracy guard proven non-vacuous via constant + whole-round-trip negative controls (Pitfall 3); BUDGET is a measurement/overhead-regression guardrail, not a shipped-latency claim (D-09)
- [Phase ?]: 04-01: ToolCallingChatAdapter extends ChatAdapter as a second runtime_checkable Protocol — the Phase-3 port definition stays byte-identical (D-02)
- [Phase ?]: 04-01: UndeclaredPeer is a taxonomy sibling of AllProvidersFailed/EngineError — never an AdapterError, so the fallback loop cannot swallow a routing violation
- [Phase ?]: 04-01: peer enforcement is belt-and-braces — capability removal in handoff_tools() AND a runtime guard checking awake.peers, never LlmConfig.profiles
- [Phase ?]: 04-01: Agent.awake_agent is sticky in-process and not persisted; _chain() now starts from it rather than config.active_profile
- [Phase ?]: 04-02: mesh trace uses NEW FK-free tables (handoffs, turn_legs) — never a column on runs, since the migration-less executescript schema makes an added column a silent no-op on an existing trace.db (Pitfall 5)
- [Phase ?]: 04-02: observer columns (observer_verdict/profile/rerouted_to) declared before the observer exists (04-07) because there is no path to add them later
- [Phase 04]: Hop budget floor and default are ONE constant (mesh.HOP_BUDGET_FLOOR=3), imported by the Pydantic constraint — Two numbers that must agree are one number that eventually does not. Three because the legitimate A-B-A hand-back costs two hops (MESH-03), so the wall must stand above it.
- [Phase 04]: At budget exhaustion with no default_agent, the currently-awake agent answers with the tools withdrawn (OQ-2) — That is the absence of a further move, not a guess, so D-09 holds. Falling back to active_profile would be PAAF choosing an agent in the one situation where the user declined to.
- [Phase 04]: _run_chain takes tool_path separately from tools, so an EMPTY tool tuple still crosses the port on the mesh path — At the wall, no-moves is a statement rather than an absence. A call shape derived from bool(tools) could not tell the withdrawn leg apart from a Phase-3 single-agent turn, and the wall would be unobservable exactly where the budget test needs to see it.
- [Phase 04]: FakeAdapter publishes scripted tool calls on the tool COUNT, not the code path — A leg offered zero tools cannot have called one. Keying on the path alone would let the fake publish a handoff for the withdrawn leg, which is precisely the engine bug the budget test exists to catch.
- [Phase 04]: A bind_tools failure raises an unconditional EngineError, NOT via _translate — _translate classifies by exception TYPE NAME, so a binding error named like a transport failure would be reported as a degraded provider and swallowed by the fallback loop. Binding contacts nobody, so it raises the way bind() raises.
- [Phase 04]: The tool binding is NOT cached with the model — the offered surface changes per leg (04-03's wall withdraws it entirely), so a cached binding would serve one leg's moves to the next. bind_tools wraps the cached model, so re-binding per call costs no connection.
- [Phase 04]: Assumption A1 CONFIRMED by measurement, not inference: langchain-ollama==1.1.0 / Ollama 0.32.1 stream 45-57 text chunks with a handoff tool bound (ttft 1.9-6.2s) on qwen3.5:2b and :9b, and aggregate exactly one PAAF ToolCall with dict arguments. Secondary finding: both models return the tool call with ZERO prose, which bears on D-11.
- [Phase ?]: 04-05: the generated explainer names PEERS, never tool names — which is what makes OQ-3's default/provenance boundary mechanically assertable in both directions
- [Phase ?]: 04-05: explainer_for and handoff_tools quote a peer's manifest through the SAME _describe(), so the prompt and the tool description cannot disagree about the same agent
- [Phase ?]: 04-05: a user-authored explainer template is substituted with str.replace, never str.format — prose contains braces, and a KeyError there would crash the one path that shows what was sent
- [Phase ?]: 04-05: the tool surface renders with click.echo rather than a rich console — echo interprets nothing at all, which is strictly stronger than markup=False for a byte-exactness command
- [Phase ?]: 04-06: ModelProfile.fallback_chain is an override of the global chain (empty means global), so SC#4 is per-agent without breaking any Phase-3 config
- [Phase ?]: 04-06: the fallback-chain self-reference check lives on LlmConfig._check_refs — a ModelProfile carries no name field, so a bare model cannot know it is self-referencing
- [Phase ?]: 04-06: one runs + one turn_legs row per agent LEG, correlated by an engine-generated uuid4 turn_id; never a new column on runs (Pitfall 5)
- [Phase ?]: 04-06: pre-handoff prose is recorded on the accepted handoffs row's detail column — the trace has never had a completion-text column, so dropping it is presentation, not loss (T-04-31)
- [Phase ?]: 04-06: MESH-05 left Pending — 04-09 also carries it and the observer columns 04-07 owns are still NULL (the 04-02 precedent)
- [Phase ?]: 04-07: the observer's grant answers 'may it re-route at all'; mesh.resolve_handoff answers 'may it reach that target' — two layers, one graph
- [Phase ?]: 04-07: a veto SPENDS a hop, so the deterministic wall still guarantees termination under a refusing observer
- [Phase ?]: 04-07: the observer's leg writes no runs/turn_legs row — it is never awake, so a leg row would make turn_legs.agent lie

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

- **Highest-risk unverified claim:** Chatterbox intra-sentence code-switching and Hebrew quality. Phase 1 exists to measure it. If it fails, the founding language promise needs its fallback ladder *before* Phase 6 begins.
- **Hardware not yet owned.** Budget is being saved. Phase 1 measurements determine what class of machine to buy; no phase before 12 may gate on it.
- **`langchain-mcp-adapters` is 0.x** and carries a core user-facing feature outside LangChain's 1.0 stability policy. SPIKE-06 is the falsification test.
- dicta-onnx is now on the CRITICAL PATH for Hebrew (Gate 0 proved Hebrew needs it plus a manually-supplied weights file), yet it declares NO LICENSE on PyPI or GitHub and is thinly maintained (9 stars, single individual, no release since 2025-05-31). An unlicensed transitive dep is a real distribution problem for an Apache-2.0 framework — must be resolved before Phase 6 / packaging.
- The conftest-shadowing trap is only half closed: spike/voice/ avoids it purely because 'voice' sorts after test_fixtures_smoke.py. Any future spike/<earlier-sorting-dir>/conftest.py will break the base suite collection entirely. Durable fix is moving 01-01's FakeModel/FakeTool into spike/fakes.py

### Roadmap Evolution

- Phase 4 inserted after Phase 3: Agent Mesh (LLM-driven handoff); reframed MODEL-05 to capability manifest + peer graph; renumbered old 4-12 -> 5-13; pulled LLM routing into v1

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Hardware | Reference build, enclosure, mic-kill switch | Deferred to v2 | Milestone start |
| Memory | Semantic search, long-term conversational memory | Deferred to v2 | Milestone start |
| Routing | Automated mis-route detection / routing-quality eval (ROUTE-01). LLM-driven routing itself is now v1 core — Phase 4 Agent Mesh | Partially pulled into v1 | 2026-08-04 |

## Session Continuity

Last session: 2026-08-07T11:17:03.476Z
Stopped at: Completed 04-07-PLAN.md
Resume file: None
