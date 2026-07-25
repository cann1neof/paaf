# Roadmap: PAAF — Personalized Agentic Assistant Framework

## Overview

The journey starts by trying to break the project's own founding promise. Phase 1 is throwaway measurement code that answers, with evidence, whether a multilingual assistant that is never told which language it is hearing can actually be built with the only engines that cover Hebrew — and what hardware it would take. Nothing ships from it, and no public claim later in the project may exceed what it measured.

From there the build runs in vertical slices along the dependency graph. Phase 2 lays a monorepo where the architectural rules are CI failures rather than good intentions: import contracts, endpoint declaration, atomic config, and a time-to-first-audio regression gate measured with a fake TTS before any audio exists. Phases 3–5 build `paaf-llm` fake-adapter-first until a stranger can `pip install paaf-llm`, write a persona, install a skill, and read the exact prompt the assistant sent — the framework standing alone, published mid-roadmap as the deliberate hedge against solo-maintainer burnout.

Phases 6–8 build voice the same way, test doubles before engines, and then the hardest component in the system — the realtime turn loop with barge-in that truncates history to what actually left the speaker — entirely in CI on a machine with no audio hardware. Phases 9–11 turn that into an appliance with a control panel that holds no truth of its own. Phase 12 is the only hardware-gated work: real-device latency, echo cancellation, far-field accuracy, a packet-capture recipe a stranger can reproduce, and the launch.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Spike Gate** - Falsify the language promise, the stack, and the hardware assumption before writing any architecture (completed 2026-07-25)
- [ ] **Phase 2: Foundation** - Workspace, CI-enforced contracts, config, secrets, and the latency regression gate
- [ ] **Phase 3: paaf-llm Core** - Ports and fake adapter first, then models, fallbacks, routing, and the verbatim prompt
- [ ] **Phase 4: Tools, MCP & Permissions** - Unified tool registry across three sources with tiers the user sets
- [ ] **Phase 5: Skills & PyPI Release** - Installable skills, and `paaf-llm` shipped publicly before voice exists
- [ ] **Phase 6: paaf-voice Ports & Fakes** - Test doubles and the language-agnostic sentence aggregator, before any engine
- [ ] **Phase 7: Real Engines & Live Audio** - Whisper, Chatterbox, wake word and VAD behind the ports; the machine hears and speaks
- [ ] **Phase 8: paaf-session** - The turn loop and truthful barge-in, hardened in CI with no audio hardware
- [ ] **Phase 9: The Appliance** - One Linux process with a LAN API, mDNS, hot reload, and enforced offline mode
- [ ] **Phase 10: Desktop Core** - Discovery, pairing, models, persona, and chat, with the device as the only truth
- [ ] **Phase 11: Desktop Remaining Pages** - Skills, tools, behaviors, voice, traces, and privacy
- [ ] **Phase 12: Bring-Up & Launch** - Real-device latency, a reproducible offline proof, docs, and going public

## Phase Details

### Phase 1: Spike Gate

**Goal**: Replace the project's five load-bearing unverified claims with measurements, so the language promise, the agent-framework choice, and the hardware purchase are all decided by evidence rather than hope.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: SPIKE-01, SPIKE-02, SPIKE-03, SPIKE-04, SPIKE-05, SPIKE-06, SPIKE-07, SPIKE-08, SPIKE-09
**Success Criteria** (what must be TRUE):

  1. A native Hebrew speaker's verdict on Chatterbox output is recorded verbatim in `DECISIONS.md`, alongside results for ≥20 real mixed-script en/ru/he/es sentences run through both Chatterbox (varying `language_id`) and Whisper — including whether Whisper locks onto one language and transliterates or translates the rest.
  2. Time-to-first-audio for one short Chatterbox sentence is known on Mac MPS and on CPU, and a per-stage latency budget derived from a real WAV-in → WAV-out round trip exists — enough to say what class of hardware to buy, before buying any.
  3. Running LangChain/LangGraph and Pydantic AI against the same sketched port shows which is easier to hide behind it, and Ollama token counts and MCP tool args/results are confirmed either visible or not visible through callbacks.
  4. `DECISIONS.md` states the measured multilingual reality in plain language, and no claim anywhere in the repo — README included — exceeds it.
  5. No code written in this phase survives into any shipped package.

**Plans**: 10/10 plans complete
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — System toolchain (uv/3.12/ffmpeg) + `spike/` quarantine scaffold + pytest inside spike/

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Failure-grid corpus fixture + grid tests + blind-shuffle harness (D-01/02/03/14)
- [x] 01-03-PLAN.md — Voice venv + GATE 0 engine readiness (dicta-onnx checkpoint, Hebrew/device/seed)
- [x] 01-04-PLAN.md — Bake-off venv + Ollama daemon + tool-call sanity gate + telemetry-off

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-05-PLAN.md — Corpus render (SPIKE-01): ~40 clips matrix+embedded+None-control, seeded, leak-isolated
- [x] 01-06-PLAN.md — Framework bake-off: one PAAF port × two adapters + trace/MCP (SPIKE-05/06/07)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-07-PLAN.md — Whisper transcription (SPIKE-04): lock-on / transliterate / translate, D-05 caveat
- [x] 01-08-PLAN.md — Blind native-ear Hebrew verdict + ru/es spot-check (SPIKE-02, D-13/14/20)

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-09-PLAN.md — Latency: TTFA (MPS+CPU) + round-trip walking skeleton per-stage budget (SPIKE-03/08)

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 01-10-PLAN.md — RESULTS.md (raw, first) + DECISIONS.md + SC#4 claim audit (SPIKE-09)

**UI hint**: no

### Phase 2: Foundation

**Goal**: A monorepo where the architectural rules that everything else depends on are build failures rather than intentions, and where time-to-first-audio is already a number CI defends.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, TRACE-01, TRACE-02, TRACE-03, TRACE-04, TRACE-05, PRIV-01, PRIV-02
**Success Criteria** (what must be TRUE):

  1. A deliberate violation — `paaf-voice` importing `paaf-llm`, or `langchain*` imported outside the designated adapter package — fails CI on import-linter, and the whole suite otherwise runs green with no audio hardware and no network.
  2. A separate CI job installs the built `paaf-llm` wheel into a clean venv with no workspace present and runs its smoke tests, so "independently installable" cannot rot.
  3. Editing config validates against a typed schema, writes atomically, and bumps a monotonic revision; a stale-revision write is rejected as a conflict instead of silently overwriting, and API keys live in a separate store that the YAML and the logs never contain.
  4. Every component declares its network endpoints through one common interface, and each config key reports its reload tier (hot / warm / cold / restart-only) on request.
  5. A run's prompts, model choice, tool calls with args and results, timings and token counts land in a local SQLite store off the hot path, `time_to_first_audio` is a first-class column, and a CI job asserts it cold against a regression threshold using a fake TTS — before any real audio engine exists.
  6. `DECISIONS.md`, `CONTRIBUTING.md`, the architecture doc, Apache-2.0 headers and DCO exist from the first commits, with the anti-feature list, the no-accounts/no-telemetry-ever commitment, the skills-security posture, and the permission-model-as-only-injection-defense constraint written down publicly.

**Plans**: TBD
**UI hint**: no

### Phase 3: paaf-llm Core

**Goal**: `paaf chat` holds a real conversation using a model the user named in YAML, survives losing its provider mid-sentence, and shows the user the exact prompt it sent.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05, MODEL-06, MODEL-08, PERS-01, PERS-02, PERS-03, PERS-04, PERS-05
**Success Criteria** (what must be TRUE):

  1. The `fake/` adapter is written and merged **before** the real adapter exists, and the entire `paaf-llm` test suite passes against it with the agent framework uninstalled — the proof that the port is a port and not a mirror.
  2. The user names model profiles across Ollama, OpenAI-compatible endpoints and Anthropic in YAML — including two separate local servers on the LAN as distinct profiles — and `paaf chat` uses them without a line of code.
  3. Pulling the WAN mid-conversation moves the reply onto a local profile and the conversation continues; a degraded-but-reachable provider triggers the same chain, not just a hard connection error.
  4. A user-written intent rule routes a request to a chosen profile, and the trace shows which profile actually served it and whether it was a fallback.
  5. One command prints the final composed prompt verbatim — base prompt, skill fragments, runtime context — exactly as sent to the model, and it contains nothing the user did not write.

**Plans**: TBD
**UI hint**: no

### Phase 4: Tools, MCP & Permissions

**Goal**: The assistant can act on the world through built-ins, a plain decorated Python function, and an MCP server — with every tool carrying a permission tier the user chose.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08
**Success Criteria** (what must be TRUE):

  1. Timers, alarms, weather and music control work from `paaf chat`, and a user's own function becomes a callable tool by adding one decorator.
  2. Pasting an MCP server config makes its tools appear in the same registry as the built-ins and the user's own, distinguishable only by declared source.
  3. Every tool carries an `observe` / `act` / `confirm` tier, and a `confirm`-tier tool causes the assistant to ask and wait for approval before executing, with the trace recording whether it was approved.
  4. A Home Assistant tool package works as an example skill, driving HA over its API, with no Home Assistant dependency anywhere in the framework.
  5. The docs name the permission model as the *only* defense against prompt injection via tool results, and a search of the repo turns up no hidden defensive instructions in any prompt.

**Plans**: TBD
**UI hint**: no

### Phase 5: Skills & PyPI Release

**Goal**: A stranger `pip install`s `paaf-llm`, builds a text assistant with it, and installs a skill from a git URL — the framework standing alone and shipped publicly, well before voice exists.
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: SKILL-01, SKILL-02, SKILL-03, SKILL-04, SKILL-05, OSS-01, OSS-02
**Success Criteria** (what must be TRUE):

  1. Installing a skill from a git URL shows its manifest's requested permissions for explicit approval before anything is imported, and a failed dependency resolution refuses loudly and changes nothing.
  2. Enabling or disabling an installed skill changes the composed prompt and the tool registry without uninstalling it.
  3. `paaf-llm` is live on PyPI and installs into a clean venv on a machine that has never seen this repo, with the verbatim prompt inspector working there.
  4. A published docs site covers install, configuration, skill authoring and the framework API **for everything that exists at this point**, and is explicit about what does not exist yet rather than silent about it — the voice and appliance sections are added in Phase 12, not implied here.
  5. The docs and the install prompt both state plainly that skills run in-process with no sandbox, that the manifest is disclosure rather than enforcement, and that MCP is the preferred path for anything the user has not audited.

**Plans**: TBD
**UI hint**: no

### Phase 6: paaf-voice Ports & Fakes

**Goal**: A voice module whose shape was set by its test doubles rather than by one engine, able to split a mixed-script token stream into speakable sentences with no language configuration anywhere in it.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: VOICE-01, VOICE-02, VOICE-06, VOICE-11
**Success Criteria** (what must be TRUE):

  1. STT, TTS, wake word, VAD, audio source and audio sink each sit behind a swappable interface, and shipped fakes for all of them are written and merged **before** any real engine — including a scripted audio source and a sink with a virtual playhead.
  2. The aggregator splits a token stream into speakable sentences correctly across Latin, Cyrillic and Hebrew script — including sentences that switch script mid-way — using Unicode terminator rules, with no per-language setting anywhere to get wrong and no NLTK in the dependency tree.
  3. The first chunk of a turn is emitted on a deliberately short threshold and later chunks on a longer one, and a test demonstrates that the first-chunk threshold is what moves time-to-first-audio.
  4. Markdown, emoji and code blocks never reach a TTS engine as literal symbols, and roughly 80% of the module's tests run from WAV fixtures with no microphone present.

**Plans**: TBD
**UI hint**: no

### Phase 7: Real Engines & Live Audio

**Goal**: Real Whisper, real Chatterbox, real wake word and VAD sit behind the ports the fakes already defined, and the machine can actually hear and speak in four mixed languages.
**Mode:** mvp
**Depends on**: Phase 6
**Requirements**: VOICE-03, VOICE-04, VOICE-05, VOICE-07, VOICE-08, VOICE-09, VOICE-10, VOICE-12, PRIV-06
**Success Criteria** (what must be TRUE):

  1. Speaking English, Russian, Hebrew and Spanish — mixed within a single sentence — produces a streaming transcript with partial results, with no language configured anywhere in the pipeline, and the observed behavior matches what Phase 1 measured rather than what was hoped.
  2. A mixed-language reply is spoken back in one voice identity; a per-language *engine* override exists as an escape hatch, and per-language voice switching appears nowhere in the codebase.
  3. The wake word fires with a swappable engine, VAD keeps running continuously including during playback, and live mic/speaker I/O exposes a playhead position and a reference tap for echo cancellation.
  4. Every engine warms up at startup before the device advertises itself as ready, and no model is ever downloaded without the user explicitly consenting.
  5. Chatterbox's PerTh watermarking is documented as a known property of the default engine, found in the docs rather than discovered by a user.

**Plans**: TBD
**UI hint**: no

### Phase 8: paaf-session

**Goal**: The hardest component in the system — the realtime turn loop with barge-in that tells the truth about what was actually heard — built and hardened in CI on a machine with no audio hardware.
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: SESS-01, SESS-02, SESS-03, SESS-04, SESS-05, SESS-06, SESS-07, SESS-08, SESS-09
**Success Criteria** (what must be TRUE):

  1. A turn runs wake → capture → transcribe → think → speak under explicit cancellation scopes, and speech begins on the first complete sentence of the reply rather than after the whole reply.
  2. Interrupting the assistant mid-sentence stops playback and starts capture within 250ms, with the pre-roll audio captured during debounce prepended so the user's first word is not clipped.
  3. The assistant message committed to conversation history equals exactly the text that left the speaker before the playhead — not what the model generated — asserted by a deterministic CI test using fake audio and a virtual playhead, with no hardware anywhere in the run.
  4. A behavior sound and a reply sentence never play over each other; a ready reply sentence preempts a filler mid-word.
  5. A user-editable escalation table fires at its configured thresholds during a long request and also on model-unavailable, tool-error and wake events, and the conversation continues without re-waking inside a configurable follow-up window.

**Plans**: TBD
**UI hint**: no

### Phase 9: The Appliance

**Goal**: One Linux process that owns the session's lifecycle, announces itself on the LAN, reloads config without restarting, and can prove it is offline.
**Mode:** mvp
**Depends on**: Phase 8
**Requirements**: APP-01, APP-02, APP-03, APP-04, APP-05, APP-06, APP-07, APP-08, APP-09, APP-10, PRIV-03
**Success Criteria** (what must be TRUE):

  1. A single process wires the session to real audio devices, runs as a Linux service, and announces itself over mDNS so a client can find it without being told an address.
  2. A first connection pairs with a PIN the device displays and returns a bearer token; the API serves settings and skills over REST and live logs, live state and a text chat channel over WebSocket, and rejects any non-LAN peer or origin.
  3. Editing persona, tools, behaviors or model-profile selection applies without restarting the process, while cold and restart-only keys are reported to the user as exactly that rather than silently ignored or falsely claimed.
  4. With offline mode on, the process refuses to start any component declaring a non-LAN endpoint, and a CI job running a scripted offline session under packet capture fails the build on any non-LAN packet.
  5. Update checks happen only when the user asks, and GPIO hooks for a mute-switch read and a status LED no-op cleanly on hardware that has no GPIO.

**Plans**: TBD
**UI hint**: no

### Phase 10: Desktop Core

**Goal**: An Electron control panel that finds the device, pairs with it, and lets the user pick a model and write a persona — with the device as the only source of truth and the assistant surviving the app's deletion.
**Mode:** mvp
**Depends on**: Phase 9
**Requirements**: DESK-01, DESK-02, DESK-03, DESK-10, DESK-11, DESK-12, DESK-13, MODEL-07, PRIV-05
**Success Criteria** (what must be TRUE):

  1. The app discovers the device on the LAN, pairs with the PIN the device shows, and stores nothing but the token in the OS keychain.
  2. The Models page edits profiles, fallback chains and routing rules, and a test button runs a profile on the device and shows the actual result.
  3. The Persona page shows the editor beside the verbatim composed prompt exactly as the device would send it, and a chat panel tests the assistant without speaking to it.
  4. A rejected setting never appears applied — the UI renders device state after the change lands, never its own prediction — and deleting the desktop app entirely leaves the assistant working unchanged.
  5. Hebrew and other right-to-left text renders correctly everywhere it can appear, and the Electron build ships with auto-update and Chromium background services disabled.

**Plans**: TBD
**UI hint**: yes

### Phase 11: Desktop Remaining Pages

**Goal**: Every remaining thing the user owns about the assistant — its skills, its tools, what it does while it thinks, its voice, its history, and its privacy — is editable and inspectable from the control panel.
**Mode:** mvp
**Depends on**: Phase 10
**Requirements**: DESK-04, DESK-05, DESK-06, DESK-07, DESK-08, DESK-09
**Success Criteria** (what must be TRUE):

  1. Skills install from a git URL through the app with the permission review shown before approval, and enable/disable works without uninstalling.
  2. The Tools & MCP page lists the unified registry with each tool's permission tier editable and MCP servers configurable in place.
  3. The behaviors escalation table is editable as a friendly editor rather than raw YAML.
  4. The Voice page previews engines and voices, sets the wake word, and selects input and output devices with live level meters.
  5. Logs tail live and any past conversation drills down to its prompts, model choice, tool calls and timings; the Privacy page toggles offline mode and shows the connections the device currently has open.

**Plans**: TBD
**UI hint**: yes

### Phase 12: Bring-Up & Launch

**Goal**: The assistant runs on the target Linux box with a measured latency number, a stranger can reproduce the offline claim themselves, and the project is public with claims that match what was measured.
**Mode:** mvp
**Depends on**: Phase 11
**Requirements**: PRIV-04, PRIV-07, OSS-03, OSS-04, OSS-05, OSS-06
**Success Criteria** (what must be TRUE):

  1. Time-to-first-audio is measured on the real device and published as a number, alongside echo-cancellation and far-field wake-word behavior on a documented reference microphone.
  2. A published verification recipe lets a user reproduce the offline claim with their own packet capture, including an explanation of the mDNS traffic they will see and why it is there.
  3. Dependency network behavior is re-audited against the current lockfile and Chromium build, with the result recorded and the audit wired to repeat on every future bump.
  4. The Phase-5 docs site is extended to cover voice, the appliance and the desktop app, and a third-party example assistant that is not PAAF's own app is built on the framework alone.
  5. The launch ships with a demo video, an honest comparison page that concedes Home Assistant's real strengths, and multilingual claims that match the Phase 1 measurements exactly.

**Plans**: TBD
**UI hint**: no

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Spike Gate | 10/10 | Complete   | 2026-07-25 |
| 2. Foundation | 0/TBD | Not started | - |
| 3. paaf-llm Core | 0/TBD | Not started | - |
| 4. Tools, MCP & Permissions | 0/TBD | Not started | - |
| 5. Skills & PyPI Release | 0/TBD | Not started | - |
| 6. paaf-voice Ports & Fakes | 0/TBD | Not started | - |
| 7. Real Engines & Live Audio | 0/TBD | Not started | - |
| 8. paaf-session | 0/TBD | Not started | - |
| 9. The Appliance | 0/TBD | Not started | - |
| 10. Desktop Core | 0/TBD | Not started | - |
| 11. Desktop Remaining Pages | 0/TBD | Not started | - |
| 12. Bring-Up & Launch | 0/TBD | Not started | - |

## Coverage

All 110 v1 requirements map to exactly one phase. See the Traceability table in `.planning/REQUIREMENTS.md`.

| Category | Count | Phase(s) |
|----------|-------|----------|
| SPIKE (9) | 9 | 1 |
| FOUND (7) | 7 | 2 |
| CORE (6) | 6 | 2 |
| TRACE (5) | 5 | 2 |
| MODEL (8) | 7 + 1 | 3 (MODEL-01..06, 08), 10 (MODEL-07) |
| PERS (5) | 5 | 3 |
| TOOL (8) | 8 | 4 |
| SKILL (5) | 5 | 5 |
| VOICE (12) | 4 + 8 | 6 (VOICE-01, 02, 06, 11), 7 (rest) |
| SESS (9) | 9 | 8 |
| APP (10) | 10 | 9 |
| DESK (13) | 7 + 6 | 10 (DESK-01, 02, 03, 10, 11, 12, 13), 11 (DESK-04..09) |
| PRIV (7) | 7 | 2 (01, 02), 7 (06), 9 (03), 10 (05), 12 (04, 07) |
| OSS (6) | 6 | 5 (OSS-01, OSS-02), 12 (OSS-03..06) |

## Notes on Structure

**Why Phase 1 comes first and nothing ships from it.** Two of its measurements — Chatterbox's Hebrew quality and its realtime feasibility — determine both what gets built and what hardware gets bought. Its exit gate is a constraint on every later phase: no public claim about multilingual behavior may exceed what was measured here.

**Fake-adapter-first survives the vertical slicing.** This is the specific risk the MVP structure introduces. `paaf-llm`'s `fake/` adapter (Phase 3) and `paaf-voice`'s `testing/` fakes (Phase 6) are written before the corresponding real implementations, never after. A port with only one implementation is a mirror, not a port, and MODEL-08's swappability guarantee depends entirely on this ordering.

**Nothing is gated on hardware except Phase 12.** Only four things genuinely need the target device: echo-cancellation quality, far-field wake-word accuracy, real-device latency numbers, and GPIO. Everything else — including the barge-in state machine, the hardest component in the system — is built and tested on the development machine.

**`paaf-session` stays narrow.** It owns only what requires knowing that time is passing and audio is playing: turn state machine, barge-in, audio output arbitration, behaviors executor, turn-level metrics. Multi-endpoint routing (MODEL-06) lives in `paaf-llm` because it fails that test.

**Phase 5 is a dated public commitment, not a nice-to-have.** Shipping `paaf-llm` to PyPI mid-roadmap is the project's burnout mitigation and it lands as soon as the package stands alone, well before voice work completes.
