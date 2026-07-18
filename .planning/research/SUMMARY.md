# Project Research Summary

**Project:** PAAF — Personalized Agentic Assistant Framework
**Domain:** Local-first, LLM-native personal voice assistant (Python framework + headless Linux appliance + Electron control panel)
**Researched:** 2026-07-13 (research) / 2026-07-18 (synthesis)
**Confidence:** MEDIUM-HIGH overall — HIGH on versions/licenses/language coverage and on the realtime-pipeline architecture; LOW on the single most load-bearing product claim (multilingual TTS quality and code-switching), which is unresolvable by reading and must be spiked first.

## Executive Summary

PAAF is a single-user voice appliance, and every credible reference implementation (Pipecat, LiveKit Agents) builds this shape the same way: an **overlapped streaming pipeline** (STT partials → LLM tokens → sentence-chunked TTS → speaker) owned by a **named orchestrator component with its own lifecycle**. Sequential pipelines land at 2–4s and are non-products; overlapped ones reach sub-1s. The project's own sketch gets the big calls right (build on an existing agent framework, hide its types, two decoupled modules) but is missing that orchestrator — the research's most consequential architectural finding.

Research overturned three assumptions written into PROJECT.md and project-docs. First, the **stability argument has reversed**: LangChain shipped 1.0 with a no-breaking-changes-until-2.0 policy and has held it ~9 months, while Pydantic AI shipped a breaking 2.0 on 2026-06-23 and *shortened* its own stability window from six months to three. Second, **Kokoro is disqualified** (no Hebrew *and* no Russian — 2 of 4 required languages), and Piper is out too (`rhasspy/piper` archived; successor `piper1-gpl` is GPL-3.0). Third, **Hebrew collapses both the STT and TTS decision trees to exactly one survivor each**: Whisper large-v3 family, and Chatterbox Multilingual V3. There is no menu; there is one path — and that path's quality is unverified.

The risk profile follows from that. Four pitfalls can end the project: unverified Hebrew/code-switching TTS (the #1 surviving differentiator), a blown latency budget, solo-maintainer collapse, and a publicly falsified privacy claim. Three of the four are addressable with cheap, early, mechanical gates: a Phase-0 spike run *before any architecture code and before any hardware purchase*; TTFA tracked as a CI metric from the trace-store phase onward using a fake TTS; and a `tcpdump`-based CI job that fails the build on any non-LAN packet. Critically, **nearly the whole system — including the hardest component, the barge-in state machine — is buildable and CI-testable on a Mac with no audio hardware**, which means the roadmap does not have to wait on hardware the maintainer has not bought yet.

## Key Findings

### Recommended Stack

Hebrew is the single most constraining requirement in the project and it eliminates almost every fashionable 2026 choice. Everything else is a normal decision; the voice engines are not decisions at all.

**Core technologies:**
- **Python 3.12** — runtime; 3.13 still carries wheel risk across the torch/audio-ML chain. Pin it.
- **LangChain 1.3.13 + LangGraph 1.2.9** (MIT) — agent runtime. Chosen because `AsyncCallbackHandler` is a near-perfect fit for draining runs into local SQLite with zero cloud, and `interrupt()` + checkpointer nearly implements the `confirm` permission tier for free. **Confidence MEDIUM — deliberately falsifiable via Spike #5.**
- **`langchain-mcp-adapters` 0.3.0** — MCP client. ⚠️ Still `0.x` carrying a core user-facing feature; the weakest link in the LangChain case, *not* covered by the 1.0 stability policy.
- **Chatterbox Multilingual V3** (`chatterbox-tts` 0.1.7, MIT, 500M) — TTS. **The only open engine covering en+ru+he+es in one model with one cloned voice identity**, which satisfies the "no per-language voice switching" rule by construction. Quality is **unverified**.
- **faster-whisper 1.2.1 / Whisper large-v3-turbo** (MIT) — STT. Whisper is the only family with Hebrew. ⚠️ CTranslate2 has **no Metal backend** — CPU-only on the Mac; use `whisper.cpp` or `mlx-whisper` for the dev harness (the pluggable STT interface's first proof of value).
- **Silero VAD 6.2.1** (MIT) — VAD/end-of-speech. Uncontested; ~1ms/chunk, free to run continuously during playback, which barge-in requires.
- **openWakeWord 0.6.0** (Apache-2.0) — wake word. ⚠️ Semi-dormant (PyPI frozen since 2024-02). Keep behind a swappable Protocol; `sherpa-onnx` KWS is the escape hatch.
- **Ollama** + **FastAPI** + **Pydantic v2** + **aiosqlite** + **sounddevice** (not PyAudio) + **uv/ruff/pytest/import-linter**; Electron + TS + React + **TanStack Query** (server-state cache, not Redux — the device is the source of truth).
- **`sherpa-onnx`** — Plan B escape hatch: one ONNX runtime for STT+TTS+VAD+KWS, CPU-first, Apache-2.0, very active, if Chatterbox compute proves fatal.

Two flags to carry: **Chatterbox embeds PerTh neural watermarking in every output by default** — for a project committed to "nothing hidden from the user," that must be an explicit documented decision, not an accident. And PROJECT.md's claim that "STT is a non-issue" is **overconfident**: Whisper emits one language token per 30s window and on code-switched speech tends to lock onto one language and transliterate or silently translate the other.

### Expected Features

The wedge is still live but **narrower than project-docs/04 assumes**, and that document is materially stale: Rhasspy is formally archived, Willow is near-dormant, and a competitor the prior scan missed — **Row-Bot** (1.4k★, very active, markets itself as "Personal AI Sovereignty") — erodes several claimed differentiators. Of eleven claims, five hold, one holds if reframed, five are eroded.

**Must have (table stakes):**
- Wake word, streaming STT, VAD/end-of-speech, barge-in, LLM conversation loop
- **Streaming sentence-by-sentence TTS** — no longer optional; HA shipped it with a claimed 9–13× perceived-latency win, so whole-reply TTS now reads as *broken*
- **MCP client** — was a differentiator in 2024; is table stakes now
- Local (Ollama) + cloud model support; a config UI; conversation continuation without re-waking; timers/alarms/weather/music built-ins; systemd service
- **~1.5s time-to-first-audio** — not a feature, a budget enforced across all of the above

**Should have (SURVIVING differentiators — lead with these):**
- **Ordered health-based fallback chains** — ✅ holds. *No voice assistant has this.* HA's "fallback" is intent-engine-first, a different axis. Demo: unplug the WAN mid-sentence.
- **Layered persona with the FINAL COMPOSED PROMPT inspectable verbatim** — ✅ holds, and it is the **best value/cost ratio in the whole project**. Row-Bot has the prompt-section architecture but as a *caching* contract, and it *injects instructions the user didn't write*. Nobody surfaces the literal final string.
- **Verifiable offline mode** (enforced + packet-capture-clean + no telemetry ever) — ✅ holds strongly. Everyone claims privacy; nobody lets you check.
- **`confirm` permission tier spoken out loud** — ✅ holds. Row-Bot gates destructive tools behind a *desktop dialog*; out-loud confirmation on a screenless far-field appliance is unclaimed.
- **Native intra-sentence code-switching (en/ru/he/es, never told which)** — ✅ holds strongly. HA's "multilingual" means two wake words bound to two separate per-language pipelines — the literal opposite. **Highest differentiation, highest risk.**
- **Declarative behaviors table** — ✅ holds *if reframed*. LiveKit already ships `BackgroundAudioPlayer` with lifecycle-bound thinking sounds. The novel part is the **user-editable timed escalation ladder (2s→6s→12s) covering failure modes**, not "we invented thinking sounds." Overclaiming will be called out at launch.

**ERODED (ship because table stakes; do not lead with them):** named model profiles across providers (Row-Bot ships it), intent-based routing (Row-Bot: "provider-aware routing"), unified tool registry (standard 2026 architecture), skills-as-git-repo-plus-manifest (Row-Bot Skills Hub; OVOS has had manifests for a decade), "we have a polished desktop app" (the differentiator is the *topology* — a stateless deletable remote control for a headless appliance — not the Electron).

**Positioning consequence:** do NOT lead the launch with "user-facing LLM management" — Row-Bot owns that phrase. Lead with *"an assistant appliance you own, that shows you its own mind, and proves it's offline."*

**Defer (v2+ / anti-features to hold):** long-term memory (a research problem that also fights prompt inspectability), multi-room (a protocol project), skills marketplace (a moderation/security/hosting obligation a solo maintainer cannot carry), flow builder, voice biometrics, emotion/avatars, macOS/Windows end-user support, own STT/TTS training, and **telemetry of any kind, ever**. Also refuse **Wyoming/ESPHome inbound compatibility** — "the sneakiest anti-feature": it looks like free distribution but inverts the architecture, making PAAF a peripheral to HA's brain and the LLM management layer irrelevant. **Watch local speech-to-speech models** — the biggest strategic risk to the pipeline design; keep the Voice interface abstract enough to absorb one.

### Architecture Approach

The sketch is directionally right and structurally incomplete: one omission that costs weeks, plus six underspecifications that each map to a predictable bug.

**Defect 1 — THE BIG ONE: nobody owns the realtime loop.** The sketch calls mic→wake→STT→LLM→TTS→speaker "wiring." It is the hardest component in the system, and both reference implementations give it a package (Pipecat's `Pipeline`, LiveKit's `AgentSession`). **Fix: a third framework package, `paaf-session`.** And it is *forced by the project's own decoupling rule*: correct barge-in must truncate assistant history to what was actually spoken out of the DAC, which requires simultaneously cancelling an LLM stream and reaching into LLM turn history — so barge-in cannot live in Module 2, which by rule knows nothing about LLMs. The sketch's module list is internally inconsistent and `paaf-session` is the resolution.

**The other six defects, compressed:**
2. The diagram (data flowing *through* both modules in series, with LangChain between them) contradicts the prose. Both modules are libraries the session *calls*, not stages in a wire. Redraw before someone reads it as a spec.
3. Barge-in is listed as a Module-2 feature. It cannot be one (see above).
4. **AEC has no home.** Pipecat and LiveKit both get it free from their transport (Daily / WebRTC). PAAF has no transport, so **PAAF must own AEC**. Ladder: hardware DSP mic → Linux `module-echo-cancel` → in-process `AudioFilter`. Never half-duplex (it deletes barge-in); partial ducking (−10 to −20 dB) as the degraded fallback.
5. **The behaviors executor and the reply will fight over the speaker.** `after 6s → "Still working on it…"` and the first reply sentence can be ready in the same 100ms window. Fix: a priority-laned `AudioOutputBus` (earcons > reply speech > behavior speech > ambient). Cheap to build, impossible to retrofit gracefully.
6. **"Change the YAML, restart nothing" is under-scoped.** Split config into **HOT** (persona/tools/behaviors/tiers/profile selection, <100ms), **WARM** (model weights, STT/TTS engine — build+warm+swap at turn boundary, 1–30s invisible), **COLD** (audio device, sample rate, wake-word engine — rebuild the audio task group, ~1–2s deaf), **RESTART** (bind address, offline toggle). Scope the exit criterion to HOT+WARM and be honest that RESTART exists.
7. **"One YAML tree, the API edits it" is a lost-update/corruption hazard.** Fix: validate → tmp+fsync+rename → monotonic revision, with ETag/`If-Match` and 409 on conflict. Never merge a config tree bidirectionally. Secrets live in a separate encrypted store, write-only over the API.

**Major components:**
1. `paaf-core` — config IO (validate→atomic write→revision), secret store, LAN/offline guards. Knows nothing about LLMs or voice.
2. `paaf-llm` (Module 1) — model profiles, fallbacks, routing, persona composition, tool registry + tiers, skills, MCP. Pure text, zero audio, zero framework types in the public API. `adapters/langgraph/` is the only place `langchain*` is importable; `adapters/fake/` is written *first*.
3. `paaf-voice` (Module 2) — wake word, VAD, STT, TTS, **sentence aggregation** (rules-based Unicode terminators — **never NLTK**, which is per-language and violates the no-language-config rule), audio IO, AEC hook. `testing/` fakes are a first-class shipped subpackage.
4. **`paaf-session`** — the realtime loop: turn state machine, cancellation scopes, barge-in, `AudioOutputBus`, behaviors executor. The only component that knows tokens become speech.
5. `paaf-trace` — SQLite WAL, bounded queue → one writer task, `wal_autocheckpoint=0`. `time_to_first_audio_us` is a first-class column. Never on the hot path.
6. `app-embedded` (FastAPI REST+WS, mDNS, PIN pairing, offline enforcement, systemd) and `app-desktop` (Electron; renders device state, holds only tokens).

**The boundary holds:** the only type crossing Module 1 ↔ Module 2 is `str` inside an `AsyncIterator`. Enforce it with **import-linter forbidden contracts in CI at step 0** — ~20 lines that turn "the modules know nothing about each other" from a wish into a build failure.

**The build-order finding that matters most** (see table below): the entire barge-in state machine is testable on a Mac with no microphone, via `ScriptedAudioSource` (speech at t=1.2s, i.e. during playback), `FakeAudioSink` with a virtual playhead advancing in simulated realtime, `FakeSTT`/`FakeTTS`, and the fake LLM adapter.

| # | Component | Depends on | HW |
|---|---|---|---|
| 0 | Repo skeleton: uv workspace, CI, **import-linter contracts**, DECISIONS.md, licenses, CONTRIBUTING | — | **NO-HW** |
| 1 | **Spike A**: agent-framework bake-off, judged on "easier to hide behind a port" | 0 | **NO-HW** |
| 1b | **Spike B**: latency round-trip (WAV in → WAV out) | 0 | **NO-HW** |
| 2 | `paaf-core`: config schema, atomic write + revision, secrets, LAN/offline guards, **endpoint declaration** | 0 | **NO-HW** |
| 3 | `paaf-trace`: SQLite WAL + queue + single writer | 2 | **NO-HW** — must precede voice; it's how TTFA is measured |
| 4 | `paaf-llm` ports + **`fake/` adapter (written FIRST)** | 2,3 | **NO-HW** |
| 5 | `paaf-llm` `langgraph/` adapter: profiles, fallbacks, routing | 4 | **NO-HW** |
| 6 | `paaf-llm`: persona composition + verbatim inspection | 4 | **NO-HW** |
| 7 | `paaf-llm`: tool registry, `@tool`, permission tiers, MCP client | 4 | **NO-HW** |
| 8 | `paaf-llm`: skill manifest + entry-point loader + permission review | 7 | **NO-HW** |
| 9 | CLI `paaf chat` — **ship `paaf-llm` to PyPI here** (dated milestone) | 4–8 | **NO-HW** |
| 10 | `paaf-voice`: Protocols + **`testing/` fakes** + sentence aggregator | 2 | **NO-HW** |
| 11 | `paaf-voice`: STT/TTS/WakeWord/VAD engines behind the Protocols | 10 | **NO-HW** (WAV fixtures → golden transcripts; ~80% of Module 2) |
| 12 | `paaf-voice`: live device IO, ring buffer, AEC hook, reference tap | 11 | **MIC** (~200 LOC) |
| 13 | **`paaf-session`**: turn state machine, `AudioOutputBus`, **barge-in**, behaviors | 4,10,3 | **NO-HW** ⭐ |
| 14 | `app-embedded`: FastAPI REST+WS, mDNS, pairing, offline enforcement, reload driver | 2,13 | **NO-HW** |
| 15 | Device bring-up: systemd hardening, `tcpdump` verification, TTFA on target | 12,14 | **TARGET** |
| 16 | `app-desktop`: Electron, discovery, pairing, the eight pages | 14 | **NO-HW** |
| 17 | Reference hardware build | 15 | **TARGET** (deferred) |

**Only four things genuinely need real hardware: AEC quality, far-field wake-word accuracy, real-device latency numbers, and GPIO — all tuning, not architecture.** The sketch's "Phase 2 exit: works on a Pi" can be substantially de-risked and front-loaded onto the Mac. Do not let the roadmap gate on a device that hasn't been bought.

### Critical Pitfalls

Four are project-killers, ranked:

1. **🔴 Hebrew / code-switching TTS doesn't work** (Phase 0). It is the #1 surviving differentiator and it is **[UNVERIFIED]**. Chatterbox takes a per-call `language_id` — *per-utterance selection, not documented intra-sentence code-switching*, and this is not a documented feature of **any** engine found. Hebrew is an abjad with unmarked vowels; generic multilingual TTS generally mispronounces it without a G2P front-end. *Avoid:* 20 real mixed-script sentences through Chatterbox and through Whisper, before any architecture code; native-ear Hebrew judgement recorded in DECISIONS.md; write the README claim at the level measured, not hoped. Design the per-language *engine override* escape hatch now (costs nothing architecturally, converts "Hebrew is broken" into "Hebrew has a documented tradeoff you control"). **Never** reopen per-language *voice* switching — it breaks on the exact case it was rejected for.
2. **🔴 Latency lands at 4–5s instead of 1.5s** (design in Phase 0, enforced from step 3). A slow voice assistant is not a worse product, it is a *non*-product. The five specific mistakes: conservative VAD hangover (300–700ms, the biggest controllable chunk, and a one-line constant); waiting for the full LLM reply before speaking; **Ollama's default 5-min `keep_alive`** (a home assistant is idle by definition, so the cold path is the *common* case — set `keep_alive: -1`); cold-start JIT (every engine Protocol needs `async warmup()`, run at boot before mDNS advertises); CPU inference contention (bounded per-engine limiter; never inference on the event loop). *Avoid:* **TTFA as a CI metric with a regression threshold from step 3**, measured cold, using a fake TTS that timestamps its first chunk. Optimize end-of-speech and TTFT; optimizing TTS is mostly wasted effort.
3. **🔴 Solo-maintainer collapse** — the modal outcome in this exact space. **Mycroft** (wound down Feb 2023) is the verified case study: a patent suit drained cash and **hardware killed it** (Mark II BOM $99→$300, ~$100k in injection molds, COVID supply chain, unfulfillable Kickstarter). Kathy Reid's post-mortem adds: no music service, incumbents sell hardware as a loss leader, the skill-discovery problem, and privacy-as-friction. **Willow** is the structural datapoint: as of 2026-02-13 the repo is not archived but shows only low-level ESP-IDF maintenance commits with no product development. *The load-bearing lesson is structural and does not depend on any individual cause: a bus factor of 1 is a real risk, and scope creep into hardware is what actually kills these projects.* PROJECT.md's deferral of the reference build is the single most important decision in the document. *Avoid:* CONTRIBUTING.md + hardware-free CI at step 0; anti-feature list written publicly in DECISIONS.md at step 0; **`paaf-llm` shipped to PyPI at step 9 as a dated commitment** — necessary but *not sufficient*, since it lands in the most crowded library category in open source. Strengthen it by publishing with the verbatim prompt inspector already working and pairing it with a written artifact (the LangChain-vs-Pydantic-AI stability reversal is genuinely publishable). Set a support-time cap before launch, while calm.
4. **🔴 Privacy claim publicly falsified** (step 2 → 14 → every release). One `tcpdump` screenshot in the launch thread destroys the only unassailable differentiator, permanently. Nobody adds telemetry on purpose — it arrives via **dependency defaults that change across versions** (verified: LangSmith tracing is opt-in, but self-hosted Langfuse reports to PostHog by default unless `TELEMETRY_ENABLED=false`). Leak sources: Electron auto-updater, Chromium's own services (Safe Browsing, variations seed, DNS prefetch, OCSP), lazy first-run model downloads, crash reporters. *Avoid:* **endpoint declaration in the component interface from step 2** (architectural, not a toggle — retrofitting is unwinnable whack-a-mole); a **`tcpdump` CI job that fails the build on any non-LAN packet during a scripted offline session** — the highest-leverage item in the entire research relative to cost; re-audit on every lockfile update and every Chromium bump; publish the verification *recipe*, including what mDNS looks like and why it's there; **never ship telemetry, not even anonymous opt-in.**

Severe, below the kill line: **AEC/barge-in never works acceptably** (recoverable via a documented hardware recommendation — and note the MacBook trap: macOS has no `module-echo-cancel`, so develop barge-in with headphones or fakes, and never tune wake-word thresholds on a near-field laptop mic); **the wrapper leaks the agent framework** (the `confirm` tier built on LangGraph `interrupt()` is where this project will most likely leak — treat `interrupt()` as an *implementation* of a PAAF-owned pause/resume concept, never the concept itself; semantic leaks are harder to spot than type leaks; the test that proves it's real is *the full `paaf-llm` suite passing against the fake with no framework installed*); **plugin security theater** (HA precedent: custom integrations run in-process with complete access and HA does not claim a sandbox; Jan 2021 disclosures found unauthenticated arbitrary file read); **losing the HA comparison at launch** (ship the HA tool package in v1 — best objection-per-hour ratio in the roadmap — and have an honest comparison page ready that concedes HA's real strengths).

**The injection-defense constraint — record this as a deliberate consequence, not an oversight.** Prompt injection via tool results is a real threat on a device with `act` permissions. Row-Bot defends with hidden injection-defense instructions in its system prompt. **PAAF's "we add nothing you can't see" commitment forbids that.** Therefore the defense *must* be the permission model — `confirm` on every irreversible or physical action — and nothing else. This is a values commitment cashed out as an architectural constraint, and it must be written into DECISIONS.md at step 0 so nobody later "fixes" it with a secret system prompt.

## Implications for Roadmap

### Phase 0: Spikes — Falsify Before You Build
**Rationale:** Five of the project's highest-risk claims are unresolvable by reading, and two of them (hardware feasibility, the language promise) determine what gets built *and what gets bought*. Nothing here is architecture code.
**Delivers:** measured answers to the unverified-claims list; a decided Hebrew fallback position recorded in DECISIONS.md; a hardware requirement derived from measurement rather than assumption.
**Avoids:** Pitfalls 1 and 2 (and a wasted hardware purchase).
**Gate:** the README language claim may not exceed what was measured here.

### Phase 1: Skeleton, Contracts, and the Honest Foundation
**Rationale:** The mechanical enforcement mechanisms are all cheap now and miserable later. Import-linter contracts "must land here, not later."
**Delivers:** uv workspace (steps 0, 2, 3), hardware-free CI, import-linter forbidden contracts, CONTRIBUTING.md, DECISIONS.md (anti-features + skills-security posture + injection-defense constraint), `paaf-core` with **endpoint declaration**, `paaf-trace` with TTFA as a CI metric.
**Avoids:** Pitfalls 3, 4, 6, and the config-corruption hazard (Defect 7).

### Phase 2: `paaf-llm` — Ship Something Real
**Rationale:** Fake adapter first (step 4) defines a port a fake can satisfy; the real adapter (step 5) then cannot shape it. This is the highest-value structural decision in the build order. Everything downstream is unlocked in CI.
**Delivers:** steps 4–9 — ports + fake, LangGraph adapter, persona + **verbatim prompt inspector**, tool registry + permission tiers + MCP, skill loader, `paaf chat` CLI, and a **dated PyPI release**.
**Addresses:** fallback chains, verbatim prompt, unified registry, permission model, HA tool package.
**Avoids:** Pitfalls 3, 6, 7.

### Phase 3: `paaf-voice` — Protocols and Fakes Before Engines
**Rationale:** ~80% of Module 2 needs no microphone. If the fakes come second, the Protocols will have been shaped by one implementation and the fakes won't fit.
**Delivers:** steps 10–12 — Protocols, `testing/` fakes, the Unicode sentence aggregator (tested in all four languages *and mixed script*), engines behind Protocols, then thin live device IO with the **playhead and reference tap** APIs.
**Avoids:** Pitfall 10, the NLTK anti-pattern, and the two APIs the naive design misses.

### Phase 4: `paaf-session` — The Missing Component
**Rationale:** ⭐ Hardest component, zero hardware required. Build it *before* the device is bought, not after.
**Delivers:** step 13 — turn state machine, cancellation scopes, `AudioOutputBus` priority lanes, **barge-in with playhead-truthful history commit and pre-roll**, behaviors executor.
**Avoids:** Defects 1/3/5, Pitfalls 5 and 10.

### Phase 5: Appliance + Control Panel
**Rationale:** The session must exist before the app can own its lifecycle; the API must exist before the desktop can render device state.
**Delivers:** steps 14 and 16 — FastAPI REST+WS with ETag/revisions, mDNS, PIN pairing, offline enforcement, config-tier reload driver; Electron with TanStack Query, no optimistic UI, RTL correctness everywhere.
**Avoids:** Pitfalls 4 and 9.

### Phase 6: Target Hardware and Launch
**Rationale:** The only genuinely hardware-gated work: AEC quality, far-field wake word, real-device latency, GPIO, systemd hardening, `tcpdump` verification. Plus the launch, which is a single-shot event.
**Avoids:** Pitfalls 5 and 8.

### Phase Ordering Rationale

- **`paaf-trace` precedes `paaf-voice`** because TTFA is measurable with a fake TTS and must be a CI regression gate from the earliest possible moment.
- **The fake adapter precedes the real adapter** because a port with one implementation is a mirror, not a port.
- **`paaf-session` is not gated on hardware**, which inverts the sketch's phase plan and front-loads the hardest work onto the machine the maintainer already owns.
- **Endpoint declaration and import contracts land at step 0–2** because both are architectural and both become unwinnable audits if deferred.
- **`paaf-llm` ships publicly mid-roadmap** as burnout mitigation *and* competitive necessity — five 1k+ star local-voice-assistant projects appeared since the prior scan.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 0** — the entire phase *is* research; it needs a measurement protocol, not a plan.
- **Phase 3/4** — end-of-speech latency is the biggest budget chunk and the least documented; decide whether a semantic turn detector is worth adding, and whether a **language-agnostic** one exists (PAAF's no-language-config rule demands it). LiveKit ships a ~135M SmolLM-v2 fine-tune for this.
- **Phase 5** — the **COLD config tier** (hot-reload of a live audio task group) is the one path with no reference implementation to copy. Spike before promising it in the UI. Also: the composed-prompt token-count ceiling — how many skills before local-7B TTFT degrades? Nobody has published this.
- **Phase 6** — prove AEC on a real cheap USB speakerphone with `module-echo-cancel`; a failure here is a *hardware* decision driven by a *software* finding.

Phases with standard patterns (skip research-phase):
- **Phase 1** — uv workspaces, SQLite WAL, atomic config writes are all well-documented.
- **Phase 2** — LangChain/LangGraph and entry-point plugin loading are documented; the risk is discipline, not knowledge.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** on versions/licenses/language coverage (pulled live from PyPI/GitHub/HF APIs 2026-07-13); **MEDIUM** on the LangChain recommendation (close call, deliberately falsifiable); **MEDIUM-LOW** on TTS *quality* | Deductive language-coverage reasoning is solid; quality is unmeasurable by reading |
| Features | **MEDIUM-HIGH** | Competitor *state* verified against GitHub API, HA blog, and project READMEs. Absence claims ("nobody else has X") are inherently MEDIUM |
| Architecture | **HIGH** on the realtime pipeline (Pipecat + LiveKit agreeing independently); **MEDIUM** on hot-reload tiers, skills loading, packaging (design synthesis, not a citable reference implementation) | Latency-budget numbers are estimates and must be measured in Spike B, not trusted |
| Pitfalls | **MEDIUM-HIGH** | Post-mortems and competitor/library behavior verified against primary sources; AEC and latency claims from framework docs |

**Overall confidence:** MEDIUM-HIGH — with the explicit caveat that the project's most load-bearing product claim sits at LOW and is the reason Phase 0 exists.

### Gaps to Address

**The unverified-claims list — everything that cannot be settled by reading. This is the Phase-0 spike, and it is the single most actionable output of this research.**

- **[UNVERIFIED] Chatterbox intra-sentence code-switching.** Not a documented feature of *any* engine found. 20 real mixed-script sentences, varying `language_id`. If it fails, the founding language promise is unimplementable as designed — go to the fallback ladder *before* building. Warning sign to watch for in yourself: "the backbone is an LLM-style model so `language_id` is probably just a prior." That is hope, not evidence.
- **[UNVERIFIED] Chatterbox Hebrew output quality.** Native-ear judgement. `he` appearing in a 23-language list is a *coverage* claim, not a *quality* claim.
- **[UNVERIFIED] Chatterbox realtime feasibility on target hardware.** A 500M autoregressive model will not run realtime on a Pi-class CPU, and project-docs targets Pi-class. Time-to-first-audio for one short sentence on Mac MPS / CPU-only / consumer GPU. **Run this before buying hardware.**
- **[UNVERIFIED] Ollama token counts surfacing non-`None` through LangChain callbacks.** The trace store's token column depends on it.
- **[UNVERIFIED] MCP tool args/results surfacing through `langchain-mcp-adapters` callbacks.** This is the falsification test for the framework choice — if MCP traces are opaque, switch to Pydantic AI without regret.
- **[UNVERIFIED] Current best-in-class local model for tool-calling reliability.** Web search hit its session limit; the Ollama "popular" sort is a lagging lifetime-cumulative indicator. Qwen3-family-sized-to-VRAM remains the sane default. Re-check and benchmark yourself at implementation time — select on **tool-calling reliability, not chat quality**.
- **Whisper code-switched STT accuracy** — MEDIUM, architecturally reasoned (one language token per 30s window), not measured. WER on the same 20 sentences; does it lock to one language? Correct PROJECT.md's "STT is a non-issue" claim before it appears in a README.
- **[UNVERIFIED — carried forward as an option, not a recommendation] Phonikud** (arXiv 2506.12311, `thewh1teagle/phonikud`) — an open Hebrew G2P front-end emitting fully-specified IPA with stress, reported Pi-capable, which STACK.md's Hebrew fallback ladder omits. If raw Chatterbox Hebrew fails, evaluate it behind the TTS Protocol. Neither its quality nor its integration cost has been assessed here.
- **A claim in PITFALLS.md concerning the death of a named real person (Willow's founder) is flagged there as UNVERIFIED and is deliberately not repeated here.** The bus-factor lesson is carried forward structurally only. Do not restate the personal claim in any public or planning document without primary-source confirmation.

## Sources

### Primary (HIGH confidence)
- PyPI JSON API / GitHub REST API / HuggingFace Hub API — versions, licenses, release dates, stars, archived status, model-card language metadata (all queried 2026-07-13)
- LangChain 1.0 release + release policy (no breaking changes until 2.0); Pydantic AI v2 article (2026-06-23 breaking release, 6mo→3mo stability window)
- Chatterbox README (resemble-ai) — 23-language list, `language_id` API, PerTh watermarking; coqui/XTTS-v2 model card (CPML non-commercial)
- home-assistant.io — Voice Chapter 11 (2025-10), blog sitemap confirming no Chapter 12 through 2026-07, 2026 release notes
- LiveKit Agents docs and Pipecat docs/API reference — `AgentSession`, `FrameProcessor`, `TextAggregationMode`, interruption semantics, `BackgroundAudioPlayer`
- SQLite WAL docs; Python Packaging User Guide (entry points, "never import from untrusted sources"); uv workspaces (Astral)
- Mycroft wind-down (Feb 2023) and Kathy Reid's post-mortem

### Secondary (MEDIUM confidence)
- Voice-agent latency decompositions and AEC practitioner write-ups (echo-to-near-end ratio below −10 dB; barge-in as the double-talk case)
- 2026 local-voice-stack write-ups (Qwen3 as community default; ~1.5s voice-to-voice bar)
- Row-Bot, isair/jarvis, OHF-Voice/linux-voice-assistant, Dograh READMEs and docs
- Practitioner patterns: SQLite single-writer queue, per-package release automation

### Tertiary (LOW confidence — needs validation)
- Chatterbox Hebrew quality, code-switching behavior, and realtime feasibility — **unmeasured; Phase 0**
- Phonikud as a Hebrew G2P front-end — **flagged, not evaluated**
- Current community-default local model for tool calling — **[UNVERIFIED]**
- Latency-budget per-stage figures other than LiveKit's cited TTFT/TTFB — estimates

---
*Research completed: 2026-07-18*
*Ready for roadmap: yes*
