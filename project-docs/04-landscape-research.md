# 04 — Bullet Proof: Landscape

Purpose: know what exists, be ready for "why not just use X?", and note what's worth studying. Nothing here changes the architecture — the core is ours, on LangChain.

## Home Assistant Assist / Voice — the big one

The strongest existing open voice stack: local pipeline (wake word → Whisper → conversation agent → Piper), a $59 open-hardware puck (Voice PE), DIY ESP32 satellites, Ollama and cloud LLM options, MCP support. It will be the #1 comparison thrown at you at launch.

Why Sovereign still exists: HA is a smart-home platform with a voice feature — you must run all of Home Assistant, and the LLM is a single "conversation agent" dropdown, not a management framework. No user-facing model routing/fallbacks, no long-request behaviors, no LLM-native skill packaging, minimal persona control, and their own docs call LLM home control experimental. Sovereign is assistant-first: the LLM framework *is* the product, no smart-home install required — and HA itself becomes just a tool package our assistant can command ("turn on the TV" flows out through it). Full compatibility, zero dependency.

## OpenVoiceOS (ex-Mycroft)

The original open assistant, community-run since Mycroft folded in 2023. Mature skill system, real privacy focus — but pre-LLM DNA (intent parsing at the core, LLMs retrofitted as "persona" plugins) and momentum lost to the HA ecosystem. Study: their skill manifest/permission model. Lesson: an assistant whose core abstraction predates LLMs can't retrofit its way out — being LLM-native from day one (via LangChain) is the right call.

## Willow

ESP32-based, self-hosted, genuinely fast (<500 ms claims). Development largely stalled since ~2023–24. Lesson: solo-maintainer risk is real (publish early), and their latency write-ups are worth reading before Phase 2.

## Leon, SEPIA, Rhasspy

Leon: MIT self-hosted assistant, skills-based, more text/automation than serious far-field voice. SEPIA: self-hosted assistant framework, Java-era, pre-LLM, small community. Rhasspy: the offline pioneer whose author now builds HA's voice stack. All three compete for your launch keywords ("open source assistant"), none for your actual product (user-facing LLM management + polished desktop control panel).

## LLM-native newcomers (2024–2026)

OpenVoiceUI (MIT, desktop agent + skills), ElatoAI (ESP32 → cloud realtime APIs), Dograh (speech-to-speech orchestration for commercial voice agents), and developer frameworks Pipecat / LiveKit Agents (web/phone agents). None combines: home assistant form factor + local-first + user-facing configuration + a real settings app. They confirm demand and set a clock — watch Pipecat/Dograh for streaming-pipeline patterns worth learning from.

## Ingredients inventory (validated, ready to consume)

LangChain/LangGraph — agent loop, providers, tools, callbacks/tracing (the framework's engine). STT — faster-whisper (strong Hebrew/Russian/English). TTS — Piper (fast, Pi-class), Kokoro (82M, Apache 2.0, better quality), Chatterbox-Turbo (MIT); open TTS has essentially closed the gap with commercial APIs as of 2025–26, but per-language quality — especially Hebrew — needs your own hands-on evaluation early. Wake word — openWakeWord, community-trainable (a custom branded wake word is a cheap premium touch). Local models — Ollama; 2026 community default for home use is the Qwen3 family sized to available VRAM. Tools — the whole MCP server ecosystem.

## The elevator answer

*"Home Assistant is a smart home that can listen. Sovereign is an assistant you own completely: you pick the model — local, API, or hybrid — write its persona, give it skills and tools, and decide what it does while it thinks, all from a desktop app. It runs on any computer with a mic, works fully offline if you want, verifiably, and can drive your Home Assistant as one of its tools."*

## Pre-code validation (cheap, do before Phase 1)

1. A weekend living with HA Voice — journal every frustration; that's the backlog and the comparison page.
2. The Phase-0 LangChain/LangGraph spike — confirm the wrapper approach on real code before committing the architecture.
3. Hebrew + Russian TTS evaluation — before promising trilingual quality.
4. Post the concept one-pager to r/selfhosted and r/LocalLLaMA — read the objections; if nobody says "I'd run this," fix the pitch before the code.
