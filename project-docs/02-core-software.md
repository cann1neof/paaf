# 02 — Core Software

## The picture

```
┌───────────────────────── THE DEVICE ─────────────────────────┐
│                                                              │
│   EMBEDDED APP  (the assistant, a local Python process)      │
│   mic ─► wake word ─► ┌───────── FRAMEWORK ─────────┐ ─► spk │
│                       │                             │        │
│                       │  Module 1: LLM MANAGEMENT   │        │
│                       │  (config layer over         │        │
│                       │   LangChain: models, skills,│        │
│                       │   tools, prompts, behaviors)│        │
│                       │            │                │        │
│                       │        LangChain            │        │
│                       │  (agent loop, API calls,    │        │
│                       │   tool invocation, logs,    │        │
│                       │   tracing — out of the box) │        │
│                       │                             │        │
│                       │  Module 2: VOICE            │        │
│                       │  (STT + TTS engines,        │        │
│                       │   streaming, barge-in)      │        │
│                       └─────────────────────────────┘        │
│                                                              │
│   local config API (REST + WebSocket, LAN only)              │
└───────────────────────────────▲──────────────────────────────┘
                                │
                  DESKTOP APP (Electron)
        the control panel: every tweak and setting
```

The framework is a Python package (`pip install sovereign-framework`). The embedded app imports it directly — no network hop between assistant and framework. The desktop app never runs the assistant; it's a remote control for its configuration and a window into its logs.

## The Framework

### Design rule

The framework's public API exposes **our** concepts (models, skills, tools, personas, behaviors, voice engines) and never leaks LangChain types. LangChain is the engine under the hood — swappable in principle, invisible to framework users. This is standard wrapper hygiene and it's what makes the framework a stable product while LangChain churns underneath.

Note from the Phase-0 spike to resolve early: plain LangChain vs. **LangGraph** (LangChain's own graph-based agent runtime) as the execution layer. LangGraph is where their agent development has moved — likely the right base for the agent loop, with classic LangChain integrations for providers/tools. Decide once, in `DECISIONS.md`.

### Module 1 — LLM Management

What the user controls (via config file or desktop app), and what we translate into a configured LangChain agent:

**Models.** Named model profiles: provider (Ollama / OpenAI-compatible / Anthropic / anything LangChain supports), model name, endpoint, generation params. A primary + ordered fallback chain (cloud down → local; local overloaded → smaller local). Optional simple routing rules (e.g., a `home_control` intent goes to the fast local model) — start with rules, keep fancy routing for later.

**Persona / system prompt.** Layered composition: user's base prompt + fragments contributed by active skills + runtime context (time, device name, room). The composed final prompt is inspectable verbatim in the desktop app — no hidden instructions, ever.

**Tools.** Three sources, one registry: built-ins (timers, alarms, weather, music control), user's custom tools (a Python decorator away — the framework re-exports a clean `@tool` interface), and **MCP servers** (user pastes a server config; its tools appear in the registry). Per-tool permission tier: `observe` / `act` / `confirm` (confirm = the assistant asks out loud before executing — door locks, purchases). Home Assistant support is exactly this: a shipped example tool package wrapping the HA REST/WebSocket API, so "turn on the TV" flows out through it. HA is a tool, never a dependency.

**Skills.** An installable folder/git repo with a manifest: name, version, permissions, persona fragment, tools (code or MCP refs), optional scheduled/event hooks, optional sounds. `sovereign skill add <git-url>`. Permissions shown and approved at install.

**Behaviors.** The "what happens when a request runs long" settings, plus friends — a small declarative table the embedded app executes:

```yaml
behaviors:
  long_request:
    after: 2s   do: play_sound: thinking     # loop until done
    after: 6s   do: say: "Still working on it…"   once: true
    after: 12s  do: start_music: ambient          # user's choice: or stay silent
  model_unavailable:  say: "Cloud is unreachable — answering locally."
  tool_error:         say: "That didn't work: {error_short}"
  on_wake:            play_sound: chime
```

**Observability.** LangChain callbacks feed a local trace store (SQLite): every run's prompts, model choice, tool calls with args/results, timings, token counts. Surfaced in the desktop app's log viewer. Nothing leaves the device.

### Module 2 — Voice

Two engine interfaces, both streaming:

**STT**: `audio_stream → text` (+ partials). First engine: faster-whisper (great multilingual — covers your Hebrew/Russian/English). Interface allows API-based engines too for weak hardware.
**TTS**: `text_stream → audio_stream`. First engine: Piper (fast on Pi-class CPU); Kokoro next (better quality, needs more compute). Sentence-by-sentence streaming is mandatory: speech starts on the first completed sentence of the LLM's answer, not after the whole reply — worth 2–3 seconds of perceived latency and the difference between "wow" and "meh."

Supporting pieces inside the module: VAD / end-of-speech detection, wake-word engine interface (openWakeWord first), and barge-in (user speaks during playback → kill playback, capture).

Voice module and LLM module don't know about each other; the embedded app wires them. That keeps the framework honest: a developer can use Module 1 alone to build a text assistant, or Module 2 alone as a voice I/O library.

## The Embedded App (the assistant)

A single Python process (systemd service) on the device: audio capture → wake word → Voice module STT → LLM Management module → Voice module TTS → playback, plus the behaviors executor and a **local config API** (FastAPI: REST for settings/skills, WebSocket for live logs, state, and a push-to-talk/chat channel). mDNS announcement so the desktop app finds it. Config lives in one YAML tree on disk; the API edits it and hot-reloads the framework (Phase 1's exit criterion). Also runs: offline-mode enforcement (refuse to start any component with a non-LAN endpoint when enabled) and update checks that are manual/consented only.

Hardware interaction stays thin and optional: GPIO hooks for a mute-switch state read and a status LED, defined in config — so the same app runs identically on a laptop with zero GPIO.

## The Desktop App (Electron)

The control panel. Pages: **Devices** (discover, pair — first-connect PIN shown by the device, token stored), **Models** (profiles, fallbacks, routing, test button), **Persona** (editor + live view of the final composed prompt), **Skills** (install from git URL, permissions review, enable/disable), **Tools & MCP** (registry, permission tiers, MCP server configs), **Behaviors** (the long-request table as a friendly editor), **Voice** (engines, voices with preview, wake word, mic/speaker selection + level meters), **Logs & Traces** (live tail + per-conversation trace drill-down), **Privacy** (offline mode toggle + a "verify" helper that shows current open connections). Plus a chat panel for testing the assistant without speaking.

Electron + TypeScript + React. It holds no state of its own beyond device tokens — the device is always the source of truth, so the assistant works forever even if the desktop app is closed or gone.

## Security, minimal and honest

LAN-only API by default; pairing token per desktop client; config API refuses non-LAN origins; secrets (API keys) stored on-device in an encrypted file, entered via desktop app, never logged. No accounts anywhere.

## Testing

Module 1 is pure text → golden tests (config + transcript in, expected route/tool-calls/answer shape out) run in CI with a fake model. Module 2 → recorded-audio fixtures for STT/VAD, TTS smoke tests. Embedded app → an integration test driving the WebSocket chat channel. Latency budget (time-to-first-audio on reference config) as a tracked number from Phase 2 onward.
