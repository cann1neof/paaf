# 01 — Project Management

## What we're building (one paragraph)

An open-source personal voice assistant with two deliverables. **The Framework**: a Python wrapper around LangChain with exactly two core modules — LLM Management (which model, which skills, which tools, which behavior settings; LangChain handles the underlying plumbing: API calls, tool invocation, logging, tracing) and Voice (speech-to-text + text-to-speech). **The App**: an embedded assistant process that runs on the device itself and uses the framework directly and locally, plus an Electron desktop app that is the control panel — every tweak and setting of the assistant, configured from your computer.

## Why this shape wins

Building on LangChain is the pragmatic call: the agent loop, provider integrations (OpenAI, Anthropic, Ollama, dozens more), tool calling, structured logging, and tracing (LangSmith or self-hosted alternatives) already exist and are battle-tested. Our value is everything LangChain deliberately doesn't have: an opinionated assistant-shaped configuration layer (models/skills/tools as user-facing concepts, not code), a voice layer, and a polished product wrapped around it. We write the 20% that makes it *an assistant you own*, not the 80% that makes LLM calls work.

## The four founding problems → concrete commitments

**1. Open platform** — framework, app, and docs fully open source; the framework usable standalone by any developer to build a different assistant than ours.

**2. Hardware freedom & trust** — the embedded app runs on any Linux machine the user picks (Pi 5, mini-PC, old laptop, NAS). Mic/speaker are whatever the user plugs in. Reference build includes a hardware mic-kill switch the user can verify with a multimeter. No mystery silicon.

**3. LLM management** — the whole point of core module #1: user decides local model / API / hybrid, edits the system prompt, installs skills, exposes tools (custom or MCP), and configures behaviors like "what happens when a request runs long" — all from the desktop app, no code required (but code always possible).

**4. No corporate/state control** — no accounts, no telemetry, no mandatory cloud, fully-offline mode that's verifiable with a packet capture, and strict neutrality: the user picks any model and writes any prompt; the platform adds no filtering layer of its own.

## Scope fences

We build: the framework (LLM Management + Voice modules), the embedded app, the Electron app, docs, one reference hardware build guide.
LangChain owns: agent execution, provider clients, tool-call mechanics, logs/traces, callbacks.
Ingredients we consume: Whisper-class STT, Piper/Kokoro-class TTS, openWakeWord-class wake word, Ollama for local models.
Out of scope: our own device protocol, microcontroller firmware, training models, selling hardware, cloud services. Integrations like Home Assistant are just tools exposed to the LLM (an HA tool package ships as an example skill — "turn on the TV" flows out through it).

## Phases

Assuming ~10–15 h/week alongside job search and studies.

### Phase 0 — Setup & spikes (weeks 1–3)
Name, license, monorepo (`framework/`, `app-embedded/`, `app-desktop/`, `docs/`). Two throwaway spikes to de-risk the stack: (a) LangChain agent with Ollama + one tool + Anthropic fallback, measuring where its abstractions help vs. fight you (also evaluate LangGraph, LangChain's own agent-orchestration layer — it may be the right base for the agent part); (b) faster-whisper + Piper round-trip latency on your laptop and on a Pi-class CPU. Write findings into `DECISIONS.md`.
Exit: stack validated, interfaces of the two modules sketched.

### Phase 1 — Framework: LLM Management module (weeks 4–10)
Text-only, tested via CLI chat. Config schema (YAML) → assembled LangChain agent: model selection + fallback chains, system-prompt/persona composition, tool registry (native + MCP), skill loader (manifest + prompt fragments + tools), behavior settings (timeouts, long-request hooks), and a clean typed API the app will consume. Logs/traces surfaced from LangChain's callbacks into our own local store.
Exit: change the YAML, restart nothing, the assistant's brain reconfigures.

### Phase 2 — Framework: Voice module + embedded app v0 (weeks 11–18)
STT engine interface (faster-whisper first), TTS engine interface (Piper first), wake word, VAD/end-of-speech, barge-in, streaming (LLM tokens → TTS by sentence — this is the latency make-or-break). Embedded app: a systemd-run process wiring mic → framework → speaker, exposing a local REST/WebSocket API for configuration and live status.
Exit: wake word → question → spoken answer on a Pi/mini-PC, fully offline, tcpdump-clean.

### Phase 3 — Desktop app (weeks 19–26)
Electron app: device discovery (mDNS) + pairing, then the control panel — model & routing settings, persona editor showing the final composed prompt, skill install/manage, tool/MCP config, behavior settings, live logs & trace viewer, voice settings (engines, voices, wake word), offline-mode switch. This is where "premium" lives in software.
Exit: a user configures everything meaningful without touching a text file.

### Phase 4 — Reference build + launch (weeks 27–32)
One documented hardware build (doc 03) with photos, the mic-kill verification page, install script/image. Launch: HN, r/selfhosted, r/LocalLLaMA, demo video.
Success year one: strangers running it, 3–5 external contributors merged, at least one third-party assistant built on the framework alone.

Total: ~7–8 months. The LangChain decision is what buys back the time versus building the agent layer in-house.

## Risks

**LangChain dependency risk** — its APIs churn and its abstractions occasionally fight you. Mitigation: the framework's public API never exposes LangChain types; it's an implementation detail we could swap (this is also just good wrapper hygiene). Pin versions, upgrade deliberately.
**"Why not Home Assistant?"** — answer must be visible in 5 minutes of the desktop app: assistant-first, LLM-first, no smart-home platform required. Keep a fair comparison page (doc 04).
**Latency UX** — voice feels dead above ~1.5–2 s to first audio; streaming TTS and long-request behaviors are core features, not polish.
**Solo burnout** — publish at end of Phase 1; the framework alone (text assistant construction kit on LangChain) is already a useful, shareable artifact.

## Licensing & workflow

License: Apache-2.0 (framework) — maximizes use; app can match or go AGPL if you want capture-resistance. DCO, no CLA. GitHub monorepo, Actions CI (framework tests need no hardware), MkDocs, semver, conventional commits, public roadmap board, `DECISIONS.md` from day one.

## Portfolio note

This project doubles as a job-search asset: LangChain agent orchestration, streaming audio pipelines, Electron, and product thinking in one repo. Write the README like a case study from the start.
