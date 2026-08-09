# Scope Boundaries & Roadmap

PAAF maintains strict transparency regarding feature availability.

## Current Delivered Scope (Phases 1 - 8)

- Monolithic Python framework & packages (`paaf-core`, `paaf-llm`, `paaf-trace`, `paaf-voice`).
- Multi-model profiles, fallback chains, and reload tiers.
- LLM-driven handoff agent mesh with observer guardrails.
- Unified Tool Registry (built-in, MCP, skills) with permission tiers.
- Skill packaging, autodiscovery loader, and staging installation.
- **Voice Subsystem (`paaf-voice`):** Engine registry, dual STT (`FasterWhisperSTT` & `WhisperCppSTT`), multilingual `ChatterboxTTS`, real wake word (`OpenWakeWordEngine`), continuous Silero VAD (`SileroVADEngine`), live audio I/O (`SoundDeviceAudioSource`/`Sink`), `soxr` resampler, and explicit CLI model weight management (`paaf voice download-models`).

## Explicit Non-Existent Scope (Scheduled for Phases 9 - 13)

The following components **do NOT exist yet** and are scheduled for upcoming development phases:

- **Turn Loop & Barge-in (`paaf-session`):** Asynchronous turn management and session interruption (Phase 9).
- **Appliance Background Service:** Process daemon, mDNS, hot reload, and enforced offline mode (Phase 10).
- **Desktop UI Application:** Graphical desktop app wrapper (Phases 11 - 12).
- **Bring-up & Final Launch:** Hardware bring-up and public distribution (Phase 13).
