# PAAF — Personalized Agentic Assistant Framework

## What This Is

An open-source personal voice assistant that its user completely owns, delivered as two things. **The Framework**: a Python package with exactly two core modules — *LLM Management* (which model, which skills, which tools, which persona, which behaviors — exposed as user-facing concepts, not code) and *Voice* (streaming speech-to-text and text-to-speech). **The App**: an embedded assistant process that runs on the user's own Linux machine and imports the framework directly, plus an Electron desktop app that is the control panel — every tweak and setting of the assistant, configured from your computer.

It is for two audiences equally: self-hosters and privacy-minded people who want an assistant they can run and verify, and developers who want to build a *different* assistant on the framework alone.

## Core Value

**The user owns the assistant's mind.** They pick the model (local, API, or hybrid), write its persona, install its skills, expose its tools, and decide what it does while it thinks — all without writing code, and with nothing hidden from them. If everything else fails, this must work.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Framework — LLM Management**
- [ ] User picks the model: named model profiles across providers (local via Ollama, OpenAI-compatible, Anthropic, others), configured without code
- [ ] Ordered fallback chains: cloud unreachable → local; local overloaded → smaller local
- [ ] Simple intent-based routing rules (e.g. a fast local model for home control), rules-first — sophisticated routing deferred
- [ ] Layered persona composition: user base prompt + skill-contributed fragments + runtime context, with the *final composed prompt inspectable verbatim* — no hidden instructions, ever
- [ ] Unified tool registry from three sources: built-ins, user Python tools via a clean decorator, and MCP servers
- [ ] Per-tool permission tiers: `observe` / `act` / `confirm` (confirm = assistant asks out loud before executing)
- [ ] Installable skills: a folder/git repo with a manifest (permissions, persona fragment, tools, hooks), permissions reviewed at install
- [ ] Declarative behaviors table — what the assistant does while a request runs long, when a model is unavailable, when a tool errors, on wake
- [ ] Local trace store (SQLite): every run's prompts, model choice, tool calls with args/results, timings, token counts — nothing leaves the device
- [ ] Public API exposes only *our* concepts and never leaks the underlying agent framework's types

**Framework — Voice**
- [ ] Streaming STT with no language configuration — the assistant understands whatever language(s) the user speaks, including code-switching mid-sentence, because it is never told which to expect
- [ ] Streaming TTS via a **multilingual** engine, so the assistant can speak back in the same languages it was addressed in
- [ ] Sentence-by-sentence TTS streaming: speech begins on the first completed sentence of the reply, not after the whole reply
- [ ] Wake word detection (community-trainable engine)
- [ ] VAD / end-of-speech detection
- [ ] Barge-in: user speaks during playback → playback dies, capture begins
- [ ] Voice module and LLM module know nothing about each other — either is independently usable

**Embedded App**
- [ ] Single process wiring mic → wake word → STT → LLM → TTS → speaker, plus the behaviors executor
- [ ] Local config API (REST for settings/skills, WebSocket for live logs, state, and a push-to-talk/chat channel), LAN-only
- [ ] mDNS announcement so the desktop app can discover it
- [ ] Config is one YAML tree on disk; the API edits it and hot-reloads the framework
- [ ] Fully-offline mode, enforced (refuses to start any component with a non-LAN endpoint) and verifiable with a packet capture
- [ ] Runs as a Linux service; hardware interaction (GPIO mute-switch read, status LED) is thin and optional so the same app runs on a machine with no GPIO

**Desktop App (Electron)**
- [ ] Device discovery and pairing (first-connect PIN shown by the device, token stored client-side)
- [ ] Pages: Models, Persona, Skills, Tools & MCP, Behaviors, Voice, Logs & Traces, Privacy
- [ ] A chat panel for testing the assistant without speaking
- [ ] Holds no state of its own beyond device tokens — the device is always the source of truth, and the assistant keeps working if the desktop app is closed or deleted

**Project**
- [ ] Framework is `pip install`-able and usable standalone to build a *different* assistant
- [ ] Docs site, CI (framework tests need no hardware), `DECISIONS.md` from day one
- [ ] Public launch: HN, r/selfhosted, r/LocalLLaMA, demo video

### Out of Scope

- **Reference hardware build, enclosure, mic-kill switch** — deferred to a later milestone; the user is developing on a Mac and will buy target hardware later. The docs (`project-docs/03-hardware.md`) are preserved for when it happens.
- **macOS as a supported target** — Mac is the dev harness, Linux is the product. The embedded app is not promised to run on macOS for end users.
- **Our own device protocol, microcontroller firmware, satellites** — if multi-room is demanded later, the honest answer is running multiple cheap devices, not inventing a protocol.
- **Training models** — we consume open models, we don't make them.
- **Selling hardware, cloud services, accounts, telemetry** — no corporate/state control is a founding commitment, not a feature flag.
- **A content-filtering layer of our own** — strict neutrality: the user picks any model and writes any prompt; the platform adds nothing.
- **Home Assistant as a dependency** — HA is supported as a *tool package* the assistant can command, never as something you must install.
- **Sophisticated LLM-based routing** — rules first; fancy routing is a later concern.

## Context

**Origin.** Four founding problems drive this: open platform, hardware freedom & trust, user-facing LLM management, and freedom from corporate/state control. Detailed source documents live in `project-docs/` (01 project management, 02 core software, 03 hardware, 04 landscape research) and remain the reference for anything this file compresses.

**The competitive wedge.** Home Assistant Assist is the strongest existing open voice stack and will be the #1 comparison at launch. It is a smart-home platform with a voice feature: you must run all of Home Assistant, and the LLM is a single "conversation agent" dropdown — no user-facing model routing or fallbacks, no long-request behaviors, no LLM-native skill packaging, minimal persona control. PAAF is assistant-first: **the LLM framework is the product**, no smart-home install required, and HA becomes just one tool the assistant can drive. OpenVoiceOS carries pre-LLM DNA (intent parsing at the core) and can't retrofit its way out. Willow proved solo-maintainer risk is real — hence publishing early.

**Language handling is a founding property, not a feature.** The user speaks English, Russian, Hebrew, and Spanish, often mixed within a single sentence, and expects the assistant to simply cope — the way an LLM does. STT is a non-issue here (Whisper-class models are natively multilingual and handle code-switching). TTS is where the constraint bites: a single-language phoneme model cannot voice a mixed-script sentence, so a **multilingual TTS engine is a hard requirement**, and engine selection must be driven by it.

**Latency is the make-or-break.** Voice feels dead above ~1.5–2s to first audio. Streaming TTS and the long-request behaviors are core features, not polish. Time-to-first-audio on the reference config is a tracked number from the Voice phase onward.

**Existing state.** Greenfield — no code written, no spikes run. `project-docs/` only.

## Constraints

- **Dev environment**: macOS laptop, no target hardware yet — Mac is a dev harness only, Linux is the ship target. Budget for hardware is being saved.
- **Time**: 20+ h/week, this is a main focus.
- **Cost**: minimal — local models via Ollama plus API keys for cloud profiles. Hardware purchase deferred.
- **Agent framework**: the public API must never leak the underlying agent framework's types, so it stays swappable. This is both wrapper hygiene and dependency-risk mitigation.
- **Privacy**: no accounts, no telemetry, no mandatory cloud. Offline mode must be *verifiable by the user*, not merely claimed.
- **Licensing**: Apache-2.0 for the framework (maximizes reuse); the app may match or go AGPL for capture-resistance. DCO, no CLA.
- **Solo maintainer**: publish the framework as soon as it stands alone — it is a useful, shareable artifact before voice exists, and shipping early is the burnout mitigation.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build on an existing agent framework rather than writing the agent loop | The agent loop, provider integrations, tool calling, and tracing are the 80% that's already solved. Our value is the 20% that makes it *an assistant you own*. | — Pending |
| **Which** agent framework is genuinely open — LangChain/LangGraph is the default hypothesis, Pydantic AI the credible challenger | LangChain's feature set maps near 1:1 onto our requirements (provider-agnostic model loading, `.with_fallbacks()`, tool registry, MCP adapters, callbacks → trace store) but churns and its abstractions can fight you. Pydantic AI is better typed and calmer but has a smaller ecosystem. Research + a spike decide on real code. | — Pending |
| Multilingual TTS engine required (not per-language voice switching) | The assistant must speak back in the same mixed languages it was addressed in. Per-sentence language detection with voice switching still breaks on code-switched sentences and changes voice identity mid-reply. | — Pending |
| No language configuration anywhere in the pipeline | Whisper-class STT is natively multilingual. Forcing the user to declare a language would be a self-inflicted limitation. | — Pending |
| Linux is the product, macOS is a dev harness | Avoids paying a cross-platform abstraction tax for a platform we don't ship. | — Pending |
| Hardware reference build deferred out of this milestone | No target hardware yet; the software must stand on its own regardless. | — Pending |
| Name is `PAAF` (Personalized Agentic Assistant Framework), working title | A real name can be chosen before launch without touching architecture. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-13 after initialization*
