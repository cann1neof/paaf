# Requirements: PAAF — Personalized Agentic Assistant Framework

**Defined:** 2026-07-19
**Core Value:** The user owns the assistant's mind — they pick the model, write its persona, install its skills, expose its tools, and decide what it does while it thinks, without writing code and with nothing hidden from them.

**Architecture these requirements are written against** (confirmed 2026-07-19):
Five framework packages — `paaf-core`, `paaf-llm` (Module 1), `paaf-voice` (Module 2), `paaf-session` (turn orchestrator), `paaf-trace` — plus two apps, `app-embedded` and `app-desktop`.
`paaf-session` stays **narrow**: it owns only what requires knowing that time is passing and audio is playing.

## v1 Requirements

### Phase-0 Validation (SPIKE)

Throwaway code answering questions that cannot be settled by reading. Nothing here ships. Every result is recorded in `DECISIONS.md`.

- [ ] **SPIKE-01**: Measure whether Chatterbox Multilingual V3 handles intra-sentence code-switching, using ≥20 real mixed-script sentences (en/ru/he/es) with varying `language_id`
- [ ] **SPIKE-02**: Judge Chatterbox Hebrew output quality by native ear and record the verdict verbatim
- [ ] **SPIKE-03**: Measure Chatterbox time-to-first-audio for one short sentence on Mac (MPS and CPU-only) to establish whether it is realtime-feasible, and on what class of hardware
- [ ] **SPIKE-04**: Measure Whisper accuracy on the same mixed-script sentences — does it lock onto one language and transliterate or translate the rest?
- [ ] **SPIKE-05**: Verify Ollama token counts surface as non-`None` through LangChain callbacks
- [ ] **SPIKE-06**: Verify MCP tool call args and results surface through `langchain-mcp-adapters` callbacks — this is the falsification test for the agent-framework choice
- [ ] **SPIKE-07**: Agent-framework bake-off (LangChain/LangGraph vs Pydantic AI) judged on one criterion: which is easier to hide behind a port
- [ ] **SPIKE-08**: End-to-end latency round-trip (WAV in → WAV out) establishing a real per-stage budget
- [ ] **SPIKE-09**: Record the measured multilingual reality in `DECISIONS.md`, and constrain every public claim to what was measured

### Foundation (FOUND)

- [ ] **FOUND-01**: uv workspace monorepo with the five framework packages and two apps, each independently versioned
- [ ] **FOUND-02**: `paaf-llm` is independently `pip install`-able without pulling in voice or audio dependencies
- [ ] **FOUND-03**: CI runs the full test suite with no audio hardware and no network
- [ ] **FOUND-04**: import-linter forbidden contracts fail CI if `paaf-llm` imports `paaf-voice` (or vice versa), or if `langchain*` is imported outside the designated adapter package
- [ ] **FOUND-05**: `DECISIONS.md` exists from the first commit and records the anti-feature list, the skills-security posture, and the injection-defense constraint
- [ ] **FOUND-06**: `CONTRIBUTING.md` plus an architecture document that lets an outsider run the tests and find their way around
- [ ] **FOUND-07**: Apache-2.0 on the framework, license headers, DCO, conventional commits, semver

### Configuration & Secrets (CORE)

- [ ] **CORE-01**: Config is one YAML tree on disk, validated against a typed schema on every read and write
- [ ] **CORE-02**: Config writes are atomic (temp file, fsync, rename) so a crash mid-write cannot corrupt it
- [ ] **CORE-03**: Config carries a monotonic revision; concurrent edits are rejected with a conflict rather than silently overwriting
- [ ] **CORE-04**: API keys live in a separate encrypted store, write-only over the API, never in the YAML tree, never logged
- [ ] **CORE-05**: Every component declares its network endpoints through a common interface, so offline enforcement is architectural rather than a scattered set of checks
- [ ] **CORE-06**: Config keys are classified into reload tiers — hot, warm, cold, restart-only — and the tier is discoverable

### Trace Store (TRACE)

- [ ] **TRACE-01**: Local SQLite store in WAL mode with a single writer task fed by a bounded queue, never on the audio hot path
- [ ] **TRACE-02**: Every run records prompts, selected model, tool calls with arguments and results, timings, and token counts
- [ ] **TRACE-03**: `time_to_first_audio` is a first-class recorded metric
- [ ] **TRACE-04**: Time-to-first-audio is asserted in CI against a regression threshold, measured cold, using a fake TTS
- [ ] **TRACE-05**: Nothing in the trace store ever leaves the device

### Model Management (MODEL)

- [ ] **MODEL-01**: User defines named model profiles — provider, model name, endpoint, generation parameters — with no code
- [ ] **MODEL-02**: Providers supported at minimum: Ollama, OpenAI-compatible endpoints, Anthropic
- [ ] **MODEL-03**: User configures an ordered fallback chain that survives an unreachable cloud provider mid-conversation
- [ ] **MODEL-04**: Fallback also triggers on a degraded-but-reachable provider, not only on a hard connection error
- [ ] **MODEL-05**: User writes simple rules routing an intent to a chosen model profile
- [ ] **MODEL-06**: Multiple endpoints of the same provider are addressable as distinct profiles, so two local servers on the LAN can serve different roles
- [ ] **MODEL-07**: User tests a model profile from the desktop app and sees the result
- [ ] **MODEL-08**: The public API exposes only PAAF types — no agent-framework types leak, proven by the full `paaf-llm` suite passing against the fake adapter with the real framework uninstalled

### Persona (PERS)

- [ ] **PERS-01**: User writes a base system prompt
- [ ] **PERS-02**: Active skills contribute persona fragments that compose with the base prompt
- [ ] **PERS-03**: Runtime context (time, device name, room) composes into the prompt
- [ ] **PERS-04**: The final composed prompt is inspectable verbatim, exactly as sent to the model
- [ ] **PERS-05**: PAAF never injects instructions the user did not write and cannot see

### Tools & MCP (TOOL)

- [ ] **TOOL-01**: Built-in tools ship for timers, alarms, weather, and music control
- [ ] **TOOL-02**: User defines a custom Python tool with a single decorator
- [ ] **TOOL-03**: User adds an MCP server by pasting its config; its tools appear in the registry
- [ ] **TOOL-04**: All three sources appear in one unified registry
- [ ] **TOOL-05**: Every tool carries a permission tier — observe, act, or confirm
- [ ] **TOOL-06**: A `confirm`-tier tool causes the assistant to ask out loud and wait for a spoken answer before executing
- [ ] **TOOL-07**: The permission model is the documented defense against prompt injection via tool results — no hidden defensive instructions, ever
- [ ] **TOOL-08**: A Home Assistant tool package ships as an example skill, so the assistant can drive HA without depending on it

### Skills (SKILL)

- [ ] **SKILL-01**: A skill is a folder or git repo with a manifest declaring name, version, permissions, persona fragment, and tools
- [ ] **SKILL-02**: User installs a skill from a git URL via CLI
- [ ] **SKILL-03**: Requested permissions are shown and explicitly approved at install time
- [ ] **SKILL-04**: User enables and disables installed skills without uninstalling
- [ ] **SKILL-05**: Documentation states honestly that skills run in-process with no sandbox, and that the manifest is disclosure rather than enforcement

### Voice (VOICE)

- [ ] **VOICE-01**: STT, TTS, wake word, and VAD each sit behind a swappable interface
- [ ] **VOICE-02**: Test fakes for every interface ship as a supported part of the package, written before the real engines
- [ ] **VOICE-03**: Streaming STT with partial results, never told which language to expect
- [ ] **VOICE-04**: Multilingual TTS speaking mixed-language replies in one voice identity
- [ ] **VOICE-05**: A per-language engine override exists as an escape hatch — an engine override, never per-language voice switching
- [ ] **VOICE-06**: Sentence aggregation splits a token stream into speakable sentences using Unicode rules that work across Latin, Cyrillic, and Hebrew script, with no per-language configuration
- [ ] **VOICE-07**: Wake word detection with a swappable engine
- [ ] **VOICE-08**: VAD and end-of-speech detection, tunable, running continuously including during playback
- [ ] **VOICE-09**: Live microphone and speaker I/O with a ring buffer, exposing a playhead position and a reference tap for echo cancellation
- [ ] **VOICE-10**: Every engine exposes a warmup call, run at startup before the device advertises itself as ready
- [ ] **VOICE-11**: ~80% of the module is testable from WAV fixtures with no microphone
- [ ] **VOICE-12**: Chatterbox watermarking behavior is documented explicitly as a known property of the default engine

### Session — Turn Orchestration (SESS)

Narrow by design: only what requires knowing that time is passing and audio is playing.

- [ ] **SESS-01**: A turn state machine drives wake → capture → transcribe → think → speak, with explicit cancellation scopes
- [ ] **SESS-02**: LLM tokens stream into sentence-chunked TTS so speech begins on the first complete sentence, not the full reply
- [ ] **SESS-03**: User interrupts the assistant mid-sentence; playback stops and capture begins within 250ms
- [ ] **SESS-04**: On interruption, conversation history is truncated to what was actually played out of the speaker, not what the model generated
- [ ] **SESS-05**: Audio output is arbitrated by priority so a behavior sound and a reply sentence never play over each other
- [ ] **SESS-06**: A declarative behaviors table drives timed escalation during a long request — a sound at one threshold, speech at another, ambient audio at a third
- [ ] **SESS-07**: Behaviors also cover model-unavailable, tool-error, and on-wake events
- [ ] **SESS-08**: The full turn lifecycle including barge-in is tested deterministically in CI with fake audio and a virtual playhead, no hardware
- [ ] **SESS-09**: Conversation continues without re-waking for a configurable follow-up window

### Embedded App (APP)

- [ ] **APP-01**: A single process wires the session to real audio devices and runs as a Linux service
- [ ] **APP-02**: REST API for settings and skill management
- [ ] **APP-03**: WebSocket for live logs, live state, and a text chat channel
- [ ] **APP-04**: API binds LAN-only and rejects non-LAN origins
- [ ] **APP-05**: Device announces itself over mDNS
- [ ] **APP-06**: First desktop connection pairs via a PIN shown by the device; the client stores a token
- [ ] **APP-07**: Hot and warm config changes apply without restarting the process; cold and restart-only tiers are reported honestly to the user
- [ ] **APP-08**: Offline mode is enforced — the process refuses to start any component declaring a non-LAN endpoint
- [ ] **APP-09**: GPIO hooks for a mute-switch read and a status LED, no-ops on hardware without GPIO
- [ ] **APP-10**: Update checks are manual and consented, never automatic

### Desktop App (DESK)

- [ ] **DESK-01**: Discovers devices on the LAN and pairs with one
- [ ] **DESK-02**: Models page — profiles, fallback chains, routing rules, test button
- [ ] **DESK-03**: Persona page — editor plus the verbatim composed prompt
- [ ] **DESK-04**: Skills page — install from git URL, permission review, enable and disable
- [ ] **DESK-05**: Tools & MCP page — registry, permission tiers, MCP server configuration
- [ ] **DESK-06**: Behaviors page — the escalation table as a friendly editor
- [ ] **DESK-07**: Voice page — engine and voice selection with preview, wake word, device selection with level meters
- [ ] **DESK-08**: Logs & Traces page — live tail plus per-conversation drill-down
- [ ] **DESK-09**: Privacy page — offline toggle and a helper showing current open connections
- [ ] **DESK-10**: Chat panel for testing the assistant without speaking
- [ ] **DESK-11**: Holds no state beyond device tokens; the device is the source of truth and the assistant survives the desktop app being deleted
- [ ] **DESK-12**: Renders right-to-left text correctly everywhere it can appear
- [ ] **DESK-13**: No optimistic UI — rejected settings never appear as applied

### Privacy (PRIV)

- [ ] **PRIV-01**: No accounts, anywhere
- [ ] **PRIV-02**: No telemetry, ever, not even anonymous or opt-in
- [ ] **PRIV-03**: A CI job runs a scripted offline session under packet capture and fails the build on any non-LAN packet
- [ ] **PRIV-04**: Dependency network behavior is re-audited on every lockfile update and every Chromium bump
- [ ] **PRIV-05**: Electron ships with auto-update and Chromium background services disabled
- [ ] **PRIV-06**: Model downloads are explicit and consented, never lazy on first run
- [ ] **PRIV-07**: The published verification recipe lets a user reproduce the offline claim themselves, and explains expected mDNS traffic

### Open Source & Launch (OSS)

- [ ] **OSS-01**: `paaf-llm` published to PyPI as a standalone usable package, with the verbatim prompt inspector working, before voice exists
- [ ] **OSS-02**: Documentation site covering install, configuration, skill authoring, and the framework API
- [ ] **OSS-03**: An honest comparison page that concedes Home Assistant's real strengths
- [ ] **OSS-04**: A third-party developer can build a different assistant on the framework alone, proven by an example that is not PAAF's own app
- [ ] **OSS-05**: Public launch — demo video, HN, r/selfhosted, r/LocalLLaMA
- [ ] **OSS-06**: Public claims about multilingual quality match SPIKE-01 through SPIKE-04 measurements exactly

## v2 Requirements

Acknowledged, deliberately deferred, not in this roadmap.

### Retrieval & Memory
- **MEM-01**: Semantic search over user documents, exposed as a tool in `paaf-llm`
- **MEM-02**: Long-term conversational memory — deferred because it is a research problem and it fights prompt inspectability

### Voice & Hardware
- **HW-01**: Reference hardware build guide with photos and an assembly walkthrough
- **HW-02**: Hardware mic-kill switch design with multimeter verification steps
- **HW-03**: 3D-printable enclosure with published STL/STEP files
- **HW-04**: Flashable OS image or one-line install script
- **VOICE-V2-01**: Custom branded wake word

### Platform
- **RT-01**: Absorb a local speech-to-speech model behind the existing Voice interface
- **ROUTE-01**: Sophisticated model routing beyond simple rules

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Reference hardware build in this milestone | No target hardware owned yet; deferred to v2. Scope creep into hardware is what actually killed Mycroft. |
| macOS/Windows as end-user targets | Mac is a dev harness; Linux is the product. Cross-platform abstraction tax for a platform not shipped. |
| Own device protocol, microcontroller satellites | Multi-room's honest answer is multiple cheap devices, not a new protocol. |
| Wyoming / ESPHome inbound compatibility | Looks like free distribution; actually inverts the architecture and makes PAAF a peripheral to Home Assistant's brain, rendering the LLM layer irrelevant. |
| Home Assistant as a dependency | HA is exposed as a tool package. Never required. |
| Skills marketplace | A moderation, security, and hosting obligation a solo maintainer cannot carry. |
| Training our own STT/TTS/LLM models | We consume open models. |
| Selling hardware or cloud services | Founding commitment against corporate capture. |
| Telemetry of any kind | Would falsify the project's only unassailable differentiator. |
| A content-filtering layer of our own | Strict neutrality: any model, any prompt, no platform-added filtering. |
| Hidden prompt-injection defenses | Forbidden by "nothing hidden from the user." The permission model carries this weight instead. |
| Per-language voice switching | Rejected by the user: it breaks on the exact code-switched case it would exist to solve. |
| Voice biometrics, emotion detection, avatars | Not core to owning the assistant's mind. |
| Visual flow builder | Configuration is YAML plus a control panel, not a node graph. |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (pending roadmap) | — | Pending |

**Coverage:**
- v1 requirements: 110 total
- Mapped to phases: 0
- Unmapped: 110 ⚠️

---
*Requirements defined: 2026-07-19*
*Last updated: 2026-07-19 after initial definition*
