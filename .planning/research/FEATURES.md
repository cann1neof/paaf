# Feature Research

**Domain:** Local-first, LLM-native personal voice assistant (framework + embedded app + desktop control panel)
**Researched:** 2026-07-13
**Confidence:** MEDIUM-HIGH (competitor *state* verified against primary sources — GitHub API, official HA blog, project READMEs. Absence claims — "nobody else has X" — are inherently MEDIUM.)

---

## Executive Verdict on the Wedge

The stated wedge — **user-facing LLM management is the product** — is still live in 2026, but it is **narrower than `project-docs/04-landscape-research.md` assumes**, and that document is now materially stale in three ways:

1. **Rhasspy is dead** (formally archived), and **Willow is near-dormant** (maintenance-only). Two "competitors" in the doc are non-competitors. Good news.
2. **Home Assistant's voice push has decelerated.** The last Voice Chapter is #11 (Oct 2025). There is **no Voice Chapter 12** as of 2026-07 — HA's 2026 releases shipped only incremental voice work. HA's LLM management is still a single dropdown. The wedge against HA holds and has, if anything, *widened*.
3. **A new competitor the doc completely misses is the real threat: Row-Bot** (1.4k stars, active, formerly "Thoth"). It markets itself as **"Personal AI Sovereignty"** — the same words, the same privacy stance (no accounts, no telemetry, keys in OS keychain), and it *already ships* provider-aware model routing, Agent Profiles (personas), a Skills Hub, a plugin system, per-tool approval gating, and realtime voice, in a cross-platform desktop app. **It erodes several claimed differentiators.**

The honest surviving wedge is not "user-facing LLM management" in the abstract — Row-Bot has that. It is:

> **An always-on, far-field, headless voice appliance you own, whose LLM behavior is fully user-configurable and fully inspectable — including what it does while it thinks.**

Row-Bot is a *desktop app you sit in front of*. HA is a *smart home that listens*. Nothing credible occupies the intersection of **appliance form factor + LLM-native + user-facing configuration + verifiable offline**. That intersection is the product.

---

## Competitor State — Verified 2026-07-13

| Project | State (verified) | What it actually is | Threat |
|---|---|---|---|
| **Home Assistant Assist / Voice PE** | **Very alive.** 89k stars, daily commits. Last Voice Chapter = #11 (2025-10). No voice chapter in 2026. | Smart-home platform with a voice feature. Pipeline: wake word → STT → *conversation agent* → TTS over Wyoming. | **#1 comparison.** But its LLM layer is stagnant. |
| **OHF-Voice/linux-voice-assistant** | **NEW & active** (523★, pushed 2026-07-12). Missed by prior scan. | Open Home Foundation's *official Linux voice satellite* (x64/ARM64, OWW/microWakeWord, ESPHome protocol). | **Kills the "HA needs a Pi/ESP32" argument.** HA now runs satellites on ordinary Linux boxes. Still requires HA as the brain. |
| **Row-Bot** (siddsachar) | **NEW & very active** (1.4k★, pushed 2026-07-12). **Missed by prior scan.** | Local-first *desktop* AI assistant. "Personal AI Sovereignty." Ollama + OpenAI/Anthropic/Google/xAI/OpenRouter/LM Studio/vLLM/llama.cpp/LiteLLM. Agent Profiles, Skills Hub, Plugin System v2, Custom Tools, MCP with destructive-tool approval, realtime voice, no accounts/telemetry. | **The real competitor.** Owns the same language. Not an appliance; not far-field; no wake word; no behaviors. |
| **isair/jarvis** | **NEW & active** (1.35k★, pushed 2026-06-26). Missed by prior scan. | "100% private AI voice assistant that lives on your computer." Offline, MCP, persistent memory, screen reading, evals, auto-redaction. macOS-primary, voice-only (no chat UI). | Direct overlap on *"private local voice assistant on a computer."* Weak on config surface — no control panel. |
| **OpenVoiceOS / Neon** | Alive but small (279★ / 207★, active). | Pre-LLM intent core; LLMs bolted on as the **Persona Pipeline** — a *fallback solver* for phrases skills didn't match. | Low. Confirms prior doc: cannot retrofit out of an intent-first core. |
| **Willow** | **Near-dormant.** 3.1k★ but last push **2026-02-13**, and only ESP-IDF plumbing commits (atomics, mutex guards). Not archived, not developed. | ESP32-S3-BOX firmware. | None. Confirms solo-maintainer risk thesis. |
| **Rhasspy** | **DEAD — formally archived** (rhasspy3, last push 2023-12). | Absorbed into HA/Wyoming; author now builds HA voice. | None. Remove from competitive set. |
| **Leon** | Alive (17k★, active). | Text/automation assistant, skills-based. Not serious far-field voice. | Keyword competitor only. |
| **SEPIA** | Stagnant. | Java-era, pre-LLM. | None. |
| **Pipecat** | **Very alive** (13.4k★, daily). | Developer framework for realtime voice pipelines. Smart Turn turn-detection model. | Not a product — an **ingredient / pattern source**. |
| **LiveKit Agents** | **Very alive** (11.3k★, daily). | Developer framework. **Ships `BackgroundAudioPlayer` with ambient + "thinking" sounds bound to the agent lifecycle.** | Not a product, but **partially erodes the behaviors claim** (see below). |
| **Dograh** | Very alive (4.8k★, daily). | Self-hosted **Vapi/Retell alternative** — commercial telephony voice agents, drag-drop workflow builder, cloud-first. | Different market (business call agents). Pattern source. |
| **ElatoAI** | Active (1.8k★). | ESP32 → cloud realtime APIs. Toy/companion devices. | Low. Cloud-dependent — opposite stance. |
| **OpenVoiceUI** | Tiny (60★). | Web voice UI + plugins. | Negligible. Prior doc overweights it. |
| **Others worth watching** | `fluxions-ai/vui` (721★, WebRTC + faster-whisper + local LLM), `Osmantic/ODS` (2.9k★, "turn your PC into an AI server"), `moltis` (2.8k★, Rust sandboxed personal agent server), `maxheadbox` (346★, tiny local voice LLM on a Pi), `CoreWorxLab/CAAL` (n8n-workflow skills). | — | The "local voice assistant" space got **crowded in 2026**. Speed matters. |

---

## Feature Landscape

### Table Stakes (Users Expect These)

Absent any of these, the assistant is not credible in 2026. Note the latency bar has moved: **~1.5 s voice-to-voice is the industry target**, and HA's streaming TTS delivered a claimed 9–13× improvement in one release — users have felt it.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Wake word detection** | Every competitor has it. openWakeWord/microWakeWord are commodity. HA now runs wake word on *Android phones*. | LOW | openWakeWord first. Community-trainable is a cheap premium touch, not a differentiator. |
| **Streaming STT** | Whisper-class is commodity. faster-whisper is the default. | LOW-MED | Multilingual for free. Don't over-engineer. |
| **Streaming TTS, sentence-by-sentence** | **No longer optional.** HA shipped it; users experienced the 10× perceived-latency jump. Whole-reply TTS now reads as broken. | MEDIUM | The single highest-leverage latency feature. Must be in the first voice phase. |
| **VAD / end-of-speech** | Baseline. | LOW | Consider Pipecat's Smart Turn model as prior art — VAD alone under-performs. |
| **Barge-in** | Baseline in 2026. Users interrupt. | MEDIUM | Requires playback control + capture arbitration. |
| **A conversation loop with an LLM** | The product. | MEDIUM | Delegated to the agent framework. |
| **Tool / skill mechanism** | Baseline. An assistant that can't *do* anything is a chatbot. | MEDIUM | — |
| **MCP client support** | **Now table stakes, not a differentiator.** HA integrated MCP immediately on release; Row-Bot, isair/jarvis, and most 2026 entrants ship it. | MEDIUM | Was a differentiator in 2024. Is not one now. |
| **Local model support (Ollama)** | The 2026 community default. Qwen3 family sized to VRAM is the consensus. | LOW | — |
| **Cloud model support (OpenAI/Anthropic/OpenAI-compatible)** | Users want the hybrid option. | LOW | — |
| **Some config UI** | HA has one; Row-Bot has one. Config-file-only is a non-starter for the self-hoster audience. | MEDIUM | *Which* UI is where PAAF competes — see differentiators. |
| **Conversation continuation without re-waking** | HA shipped this ("if the LLM asks a question, it keeps listening"). Users now expect it. | LOW-MED | Cheap. Do not skip. |
| **Timers / alarms / basic built-ins** | Users test with these on day one. "Set a timer" failing = product feels fake. | LOW | Ship 4–6 built-in tools. |
| **Runs as a service, survives reboot** | Appliance expectation. | LOW | systemd. |
| **~1.5 s time-to-first-audio** | The bar. Above ~2 s reads as dead. | HIGH | Not a feature — a *budget* enforced across all of the above. |

### Differentiators — Honestly Assessed

Each claim checked against the actual competitive set. **Three of the eleven have been eroded.**

| Feature | Verdict | Value Proposition | Complexity | Honest Assessment |
|---------|---------|-------------------|------------|-------------------|
| **Named model profiles across providers, no code** | ⚠️ **ERODED** | Pick local/API/hybrid by name. | MEDIUM | **Row-Bot already ships this** (Ollama, OpenAI, Anthropic, Google, xAI, OpenRouter, LM Studio, vLLM, llama.cpp, LiteLLM, custom endpoints — with explicit capability labels and context limits). LiteLLM does it as infrastructure. **Necessary, not sufficient.** Do not lead the pitch with it. |
| **Ordered fallback chains (cloud down → local → smaller local)** | ✅ **HOLDS (narrowly)** | Assistant keeps working when the internet doesn't. | MEDIUM | **No voice assistant has this.** HA's only "fallback" is intent-engine-first-then-LLM — a different axis entirely. LiteLLM has fallback chains but is infrastructure (YAML, no assistant). Row-Bot has "chat-only fallbacks" — a capability-degradation concept, not a health-based provider chain. **Genuinely novel in this form factor.** Strong demo: unplug the WAN mid-sentence. |
| **Simple intent-based model routing rules** | ⚠️ **PARTIALLY ERODED** | Fast local model for home control; big model for reasoning. | MEDIUM | Row-Bot has "provider-aware model routing." `guaardvark` advertises "3-tier neural routing." HA's "prefer handling commands locally" is a crude version of the same intuition. **The idea is in the water.** Rules-first is still fine — but this is a feature, not a wedge. |
| **Layered persona with the FINAL COMPOSED PROMPT inspectable verbatim** | ✅ **HOLDS** | "No hidden instructions, ever." Trust through verifiability. | MEDIUM | Row-Bot has the *architecture* (a documented named-section prompt contract: `agent.root`, `agent.profile`, `skills.tool_guides`…) but it is a **caching** contract, not a user-inspection feature — and Row-Bot **does inject instructions the user didn't write** (ReAct scaffolding, self-knowledge, prompt-injection defense). HA composes a prompt from exposed entities that the user cannot see verbatim. **Nobody surfaces the literal final string.** The *radical* part is the commitment: **we add nothing the user can't see.** That is a values claim competitors structurally cannot copy — Row-Bot's injection defense *requires* hidden instructions. **This is the strongest differentiator and the cheapest.** |
| **Unified tool registry: built-ins + user Python + MCP** | ⚠️ **ERODED** | One registry, three sources. | MEDIUM | Row-Bot: native tools + plugin-packaged MCP + custom tools, namespaced. isair/jarvis: "unlimited MCPs and tools." **Standard 2026 architecture.** Table stakes, not a differentiator. |
| **Per-tool permission tiers (observe / act / confirm-out-loud)** | ✅ **HOLDS (the voice part)** | The assistant asks *out loud* before unlocking the door. | MEDIUM | Row-Bot gates "destructive MCP tools" behind approval — but in a *desktop dialog*. **The out-loud spoken confirmation in a hands-free far-field context is unclaimed**, and it's the only workable consent surface for an appliance with no screen. Ship the three-tier model; the *voice confirmation* is the novel bit. |
| **Skills as git repo + manifest, permissions reviewed at install** | ⚠️ **ERODED** | Install a skill from a URL. | MEDIUM | Row-Bot has a **Skills Hub** + Plugin System v2. Dograh ships a `skills` repo. OVOS has had skill manifests for a decade. Agent-Skills-as-a-folder is now an industry pattern. **The install-time permission review is the only part that's distinctive** — and it's really an extension of the permission-tier feature above. **Steal OVOS's manifest design; don't claim novelty.** |
| **Declarative "behaviors" table** (thinking sound @2s, "still working" @6s, ambient music @12s; + model-unavailable / tool-error / on-wake) | ✅ **HOLDS — but reframe** | The assistant never feels frozen, and *the user decides* what waiting sounds like. | MEDIUM | **Partially anticipated.** LiveKit Agents ships `BackgroundAudioPlayer` with **ambient + "thinking" sounds bound to the agent lifecycle** — so "play a sound while it thinks" is *not* a new idea; it's a documented API in a 11k-star framework. HA ships "non-verbal confirmations" and an on-wake chime. **But:** LiveKit's is a *binary* thinking state, in *code*, for *developers*. Nobody has: (a) a **timed escalation ladder** (2s→6s→12s), (b) **user-editable declarative config**, (c) coverage of **failure modes** (model unavailable, tool error). **Reframe the claim from "we invented thinking sounds" to "we made waiting a thing the user configures, not a thing the developer hardcodes."** That claim is true and defensible. Do not overclaim in the launch post — a LiveKit user *will* call it out. |
| **Local SQLite trace store + trace viewer** | ⚠️ **WEAK** | See every prompt, model choice, tool call. | MEDIUM | HA has pipeline debug traces. Langfuse/Phoenix own LLM tracing. Row-Bot keeps "local run history." **The observability itself is unremarkable.** Its *value here is as the delivery mechanism for prompt inspectability* — which is the real differentiator. Frame it as evidence, not as a feature. |
| **Verifiable offline mode (enforced, packet-capture-clean, no accounts, no telemetry)** | ✅ **HOLDS STRONGLY** | Not "we promise" — "here's how you check." | MEDIUM | **Everyone claims privacy. Nobody lets you verify it.** Row-Bot says "no telemetry pipeline" (a promise). isair/jarvis says "100% local" (a promise). HA requires trusting a large codebase. **Enforcement** (refuse to start any component with a non-LAN endpoint) **+ a "verify" panel showing current open connections** converts a marketing claim into a testable property. **This is the second-strongest differentiator and it is cheap.** It is also *the* r/selfhosted and HN pitch. |
| **Native multilingual code-switching (understands AND speaks mixed EN/RU/HE/ES, never told which)** | ✅ **HOLDS STRONGLY** | Speak how you actually speak. | **HIGH** | **Verified against HA's own words:** HA's "multilingual assistants" (Voice Chapter 11) means **up to two wake words, each bound to a separate per-language pipeline** — "'Okay Nabu' runs English, 'Hey Jarvis' runs French." That is language *switching by wake word*, the literal opposite of code-switching. **No competitor does intra-sentence code-switching.** STT is free (Whisper). **The entire risk is TTS** — a multilingual engine that can voice a mixed-script sentence without changing voice identity. **This is the highest-risk, highest-differentiation feature. Spike it before promising it** (Hebrew is the likely failure point). |
| **Polished Electron control panel as the primary config surface** | ⚠️ **ERODED as a claim, ESSENTIAL as an asset** | Every tweak, from your computer. | HIGH | Row-Bot **is** a polished cross-platform desktop app with model/skill/tool management. HA has a mature web UI. **"We have a desktop app" is not a differentiator in 2026.** But the *combination* — a desktop control panel that is a **remote control for a headless appliance**, holding no state, deletable without breaking the assistant — is unclaimed. **The differentiator is the topology, not the Electron.** |

**Net:** of eleven claims, **five hold strongly or narrowly** (fallback chains, verbatim prompt, out-loud confirm, verifiable offline, code-switching), **one holds if reframed** (behaviors), and **five are eroded** (model profiles, routing, tool registry, skills-as-repo, "we have a desktop app"). Lead with the five. Ship the rest because they're table stakes.

### Anti-Features (Deliberately NOT Built)

Already excluded by PROJECT.md: own device protocol, microcontroller satellites, model training, hardware sales, cloud services, accounts, telemetry, own content-filtering layer, HA as a dependency. **All correct — keep them.** Additions, based on what has actually hurt comparable projects:

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **An intent/NLU engine of our own** | "LLMs are slow and expensive for 'turn on the lights'." HA's fuzzy matcher + Speech-to-Phrase exist precisely for this. | **This is exactly the trap that killed OVOS's LLM story.** An intent core becomes the center of gravity and the LLM becomes a fallback bolt-on. Building one contradicts "LLM-native from day one" and doubles the surface area. | A **fast local model profile** routed by rule. Same latency win, no second brain. If a user wants intents, HA is a tool. |
| **Multi-room / satellite orchestration** | The #1 request the moment one device works. | Requires a protocol, discovery, arbitration ("which device heard it best"), and session handoff. HA spent years on this. It is a whole product. | Already out of scope — hold the line. Honest answer: run multiple devices. |
| **Persistent long-term memory / knowledge graph** | isair/jarvis leads with "never forgets"; Row-Bot has "durable memory." It will be demanded. | Memory is a **research problem masquerading as a feature**. It creates a privacy surface, a retrieval-quality problem, an eviction-policy problem, and unbounded prompt growth — all of which fight the latency budget. It also *directly contradicts* "the final prompt is inspectable" once retrieval starts injecting things. | v2, if ever. If shipped: it must be a **skill with a tool**, and retrieved context must appear **verbatim in the inspectable prompt**. |
| **A skills marketplace / registry with ratings** | "Skills Hub" energy. Feels like a platform. | A registry is a moderation, security, and hosting obligation for a **solo maintainer**. Row-Bot can afford it; PAAF cannot. Also creates a supply-chain attack surface on a device with `act` permissions. | `git clone` from a URL + permission review. Curated links in the docs. No hosting, no ratings, no server. |
| **A drag-and-drop workflow/flow builder** | Dograh and n8n-style tools make it look inevitable. | It is a second programming language with a GUI. Enormous surface, endless edge cases, and it competes with the LLM itself — the whole premise is that the model plans, not a flowchart. | The LLM plus tools. Behaviors table is *declarative config*, deliberately not a flow engine. Resist scope creep here. |
| **Voice biometrics / speaker identification** | "Only I should be able to unlock the door." | Unreliable, spoofable, a biometric-data privacy nightmare on a device that promises no data leaves — and it invites a personalization/profiles rabbit hole. | The `confirm` permission tier. Physical mute switch. Accept that a household device is a household device. |
| **Emotion / sentiment detection, avatars, "personality" theatrics** | Companion-device trend (ElatoAI, Live2D assistants). | Pure differentiation theater; adds latency; drifts the product from *tool you own* to *toy*. | A persona the user writes. That's it. |
| **Wyoming / ESPHome protocol compatibility** | "Just be an HA satellite, you'd get their whole ecosystem." | **This is the sneakiest anti-feature.** It looks like free distribution, but it inverts the architecture: you become a peripheral to HA's brain, and the LLM management layer — *the entire product* — becomes irrelevant. OHF-Voice/linux-voice-assistant already fills that slot. | HA as an outbound **tool**, exactly as planned. Never as an inbound protocol master. |
| **Supporting macOS/Windows for end users** | "Your dev machine is a Mac; users have Macs." | Cross-platform audio (CoreAudio/WASAPI/PulseAudio) is a tax paid forever, and Row-Bot/isair-jarvis already own the desktop-assistant niche. | Linux is the product. Mac is the harness. Already decided — **hold it.** |
| **Our own STT/TTS models** | Hebrew TTS quality may disappoint. | Model training is already out of scope, correctly. | Evaluate and *select* engines. If Hebrew fails, that's a **scoping decision**, not a training project. |
| **Telemetry — even "anonymous, opt-in, for our own good"** | Every maintainer eventually wants usage data. | It is a **founding commitment**. The moment there's a flag, the claim "verifiably nothing leaves the device" dies, and the packet-capture demo becomes a lie. | Nothing. Ask users in GitHub issues like a human. |

---

## Feature Dependencies

```
[Model profiles + provider abstraction]   <-- FOUNDATION, everything hangs off this
    ├──requires──> [Config tree on disk (YAML) + hot-reload]
    │
    ├──enables──> [Ordered fallback chains]
    │                 └──requires──> [Health/failure detection per provider]
    │                 └──feeds────> [Behavior: model_unavailable]
    │
    └──enables──> [Intent-based routing rules]

[Unified tool registry]
    ├──requires──> [Model profiles]  (tools need a model that can call them)
    ├──enables──> [Per-tool permission tiers]
    │                 ├──requires──> [TTS + capture]  for the `confirm` (out-loud) tier
    │                 └──enables──> [Skills: install-time permission review]
    └──feeds────> [Behavior: tool_error]

[Layered persona composition]
    ├──requires──> [Model profiles]
    ├──requires──> [Skills]  (skills contribute prompt fragments)
    └──enables──> [VERBATIM PROMPT INSPECTOR]  <-- the flagship
                      └──requires──> [Trace store]  (the delivery mechanism)

[Trace store (SQLite)]
    ├──requires──> [Agent-framework callback hooks]
    └──enables──> [Logs & Traces page]
    └──enables──> [Verbatim prompt inspector]

[Streaming STT] ──┐
[VAD]           ──┼──requires──> [Audio capture pipeline]
[Wake word]     ──┘
                        └──enables──> [Barge-in] (also requires playback control)

[Streaming TTS (multilingual)]  <-- HIGHEST RISK, SPIKE FIRST
    ├──requires──> [Sentence segmentation of the LLM token stream]
    ├──enables──> [Sentence-by-sentence streaming]  (the latency win)
    ├──enables──> [Behaviors that SAY things] ("still working on it")
    ├──enables──> [`confirm` permission tier]  (asking out loud)
    └──GATES────> [Multilingual code-switching]   <-- the differentiator dies without it

[Behaviors executor]
    ├──requires──> [A run lifecycle with observable timing]  (start/thinking/tool/done)
    ├──requires──> [Audio playback that can mix/interrupt]  (sounds under/over speech)
    ├──requires──> [TTS]  for say-behaviors
    └──requires──> [Config tree]  for the declarative table

[Local config API (REST + WS)]
    ├──requires──> [Config tree + hot-reload]
    └──enables──> [Electron control panel]  (ALL of it)
                      └──requires──> [mDNS discovery + PIN pairing]

[Offline mode enforcement]
    ├──requires──> [Every component to declare its endpoint]  <-- ARCHITECTURAL. Retrofitting this is painful.
    └──enables──> [Privacy page + "verify connections" helper]

[Electron control panel] ──enhances──> everything (it is the config *surface*, not the config *system*)

[Intent routing] ──conflicts──> [Verbatim prompt inspectability]
    (routing that silently rewrites the prompt breaks the "no hidden instructions" promise)
```

### Dependency Notes

- **Multilingual TTS gates the single strongest differentiator.** Code-switching is the one thing no competitor has and cannot easily add. If the TTS engine can't voice a mixed-script sentence in one voice, that differentiator is gone. **This must be spiked in Phase 0/1, before the roadmap commits to it.** Hebrew is the expected failure point.
- **Offline-mode enforcement is architectural, not a toggle.** If components are allowed to open sockets without declaring endpoints, enforcement becomes a whack-a-mole audit later. Build the endpoint-declaration discipline into the component interface **from the first phase**, even if the toggle ships later.
- **The `confirm` permission tier depends on TTS + capture.** It cannot ship in an LLM-only phase. Plan the permission *model* early, the *out-loud* tier after voice.
- **The behaviors executor depends on an observable run lifecycle.** The agent-framework wrapper must expose timing events (run start, thinking, tool call, first token, done) as *our* concepts. If the wrapper hides them, behaviors can't be built. **This constrains the LangChain/LangGraph-vs-Pydantic-AI spike** — make "can I observe run-phase timing cleanly?" an explicit spike criterion.
- **Fallback chains and the `model_unavailable` behavior are the same feature seen twice.** Build health detection once; the behavior table is its user-facing face. Great combined demo.
- **Trace store must exist before the prompt inspector.** The inspector isn't a UI feature — it's a *query* over recorded runs.
- **Routing conflicts with prompt inspectability** if routing mutates prompts implicitly. Rule: routing may select a *model*; it must never edit the *prompt*. Enforce in the API design.

---

## MVP Definition

### Launch With (v1)

The bar is "credible against HA Assist on day one, with a reason to switch."

- [ ] **Model profiles + fallback chains** — the reason to switch; and fallback is the demo.
- [ ] **Layered persona + verbatim final-prompt inspector** — the trust claim; cheap; nobody has it.
- [ ] **Unified tool registry (built-ins + Python + MCP) with permission tiers** — table stakes plus the out-loud `confirm`.
- [ ] **Full voice loop**: wake word → streaming STT → LLM → **sentence-streaming multilingual TTS** → barge-in, under a tracked ~1.5 s TTFA budget.
- [ ] **Behaviors table** (long_request ladder + model_unavailable + tool_error + on_wake) — the signature feature; reframed honestly.
- [ ] **Trace store + Logs/Traces page** — the evidence layer.
- [ ] **Electron control panel** (Models, Persona, Skills, Tools & MCP, Behaviors, Voice, Logs, Privacy + chat panel) — the config surface.
- [ ] **Verifiable offline mode + Privacy page** — the pitch.
- [ ] **Home Assistant tool package** — neutralizes the #1 objection ("but I already have HA") by making HA a *feature*, not a competitor.
- [ ] **A handful of built-in tools** (timers, alarms, weather, music control) — or day-one testers conclude it's a demo.

### Add After Validation (v1.x)

- [ ] **Intent-based routing rules** — trigger: users complain "turn on the light" takes 2 s.
- [ ] **Skills installable from git + permission review** — trigger: a third party wants to publish one. (Ship the *manifest format* in v1 so it's not a breaking change.)
- [ ] **Scheduled / event hooks in skills** — trigger: "can it tell me the weather every morning?"
- [ ] **Community-trainable custom wake word** — trigger: branding moment / cheap delight.
- [ ] **Assistant-initiated conversation** — HA has it; users will ask. Needs a proactivity model.
- [ ] **GPIO mute switch / status LED** — trigger: hardware milestone.

### Future Consideration (v2+)

- [ ] **Long-term memory** — defer: research problem, privacy surface, and it fights prompt inspectability. Only as a skill.
- [ ] **Sophisticated LLM-based routing** — defer: already decided; rules first.
- [ ] **Multi-room** — defer: it's a protocol project. Currently out of scope; keep it there.
- [ ] **Speech-to-speech / realtime-API model support** — watch: it collapses STT→LLM→TTS into one model and would obsolete the latency architecture. **Track it; it is the biggest strategic risk to the whole design.** Local open speech-to-speech models are not there yet, but if they arrive, PAAF's differentiators (config, permissions, behaviors, offline) survive while its *pipeline* does not. Keep the Voice module's interface abstract enough to swap.

---

## Feature Prioritization Matrix

| Feature | User Value | Impl. Cost | Priority |
|---------|------------|------------|----------|
| Streaming multilingual TTS (sentence-by-sentence) | HIGH | HIGH | **P1** — gates a differentiator AND the latency bar |
| Model profiles + provider abstraction | HIGH | MEDIUM | **P1** — foundation |
| Ordered fallback chains | HIGH | MEDIUM | **P1** — surviving differentiator |
| Verbatim composed-prompt inspector | HIGH | LOW | **P1** — best value/cost ratio in the whole project |
| Verifiable offline mode + Privacy page | HIGH | MEDIUM | **P1** — the pitch; architectural, so early |
| Behaviors table + executor | HIGH | MEDIUM | **P1** — signature feature |
| Wake word / STT / VAD / barge-in | HIGH | MEDIUM | **P1** — table stakes |
| Tool registry + permission tiers | HIGH | MEDIUM | **P1** — table stakes + out-loud confirm |
| Trace store (SQLite) | MEDIUM | MEDIUM | **P1** — enables the inspector |
| Electron control panel | HIGH | HIGH | **P1** — no config surface, no product |
| Config API + hot-reload + mDNS/PIN | MEDIUM | MEDIUM | **P1** — enabling infrastructure |
| Home Assistant tool package | MEDIUM | LOW | **P1** — cheap objection-killer |
| Built-in tools (timers/weather/music) | MEDIUM | LOW | **P1** — credibility |
| Intent-based routing rules | MEDIUM | MEDIUM | **P2** — idea is commoditized |
| Skills from git + permission review | MEDIUM | MEDIUM | **P2** — ship manifest format in v1 |
| Custom wake word training | LOW | MEDIUM | **P3** |
| Long-term memory | MEDIUM | HIGH | **P3** — anti-feature risk |
| Multi-room | HIGH | HIGH | **P3** — out of scope; a whole product |

---

## Competitor Feature Analysis

| Feature | Home Assistant Assist | Row-Bot | OpenVoiceOS | Our Approach |
|---|---|---|---|---|
| **Model selection** | One "conversation agent" dropdown (Ollama / OpenAI / Anthropic / OpenRouter 400+) | Named providers w/ capability labels, context limits, OS-keychain keys | Persona plugin wraps one solver | Named profiles, first-class, no code |
| **Fallback** | Intent engine → LLM (a *different axis*) | "Chat-only fallbacks" (capability degradation) | Skill → LLM fallback solver | **Ordered health-based provider chain** |
| **Routing** | "Prefer handling commands locally" toggle | "Provider-aware model routing" | Intent confidence matchers | Rules: intent → profile |
| **Persona** | A single instructions text box; composed prompt not shown | Agent Profiles; named prompt sections (a *cache* contract, not user-facing); **injects hidden instructions** | Persona plugins | **Layered + FINAL PROMPT SHOWN VERBATIM; we inject nothing hidden** |
| **Tools** | Intents + MCP (client & server) | Native + custom + MCP, namespaced | Skill intents | Built-ins + `@tool` + MCP, one registry |
| **Permissions** | None per-tool | Destructive MCP tools need **desktop-dialog** approval | Skill manifest permissions | **observe / act / confirm-OUT-LOUD** |
| **Skills** | Custom sentences + automations | Skills Hub + Plugin System v2 | Mature skill store (decade-old) | Git repo + manifest, review at install |
| **Long-request behavior** | Non-verbal confirmation sounds; on-wake chime | — | — | **User-editable timed escalation ladder + failure behaviors** |
| **Multilingual** | **2 wake words → 2 separate per-language pipelines** (Ch. 11) | — | Per-language configs | **Code-switching, no language config anywhere** |
| **Offline** | Possible; trust a large codebase | "No telemetry pipeline" (a promise) | Strong local stance | **Enforced + user-verifiable (packet capture, connections panel)** |
| **Config surface** | Mature web UI (part of HA) | Polished cross-platform desktop app | YAML + web UI | Electron **remote control for a headless appliance**; deletable, no state |
| **Form factor** | Smart-home platform + satellites (now incl. **Linux** satellites) | Desktop app you sit at | Assistant OS | **Headless far-field appliance** |

---

## Strategic Warnings for the Roadmap

1. **Do not lead the launch post with "user-facing LLM management."** Row-Bot occupies that phrase. Lead with **"an assistant appliance you own, that shows you its own mind, and proves it's offline."**
2. **Spike multilingual TTS before the roadmap commits to code-switching.** It is the #1 differentiator and the #1 technical risk. Hebrew is the likely break point. (`project-docs/04` already flags this — it is right.)
3. **Make run-lifecycle observability a spike criterion** for the agent-framework choice. Behaviors cannot be built on a framework that hides run-phase timing.
4. **Bake endpoint declaration into the component interface from phase 1**, or offline-mode enforcement becomes an unwinnable audit later.
5. **Watch local speech-to-speech models.** If an open local S2S model becomes viable, the STT→LLM→TTS pipeline stops being the right architecture. The Voice module's interface must be abstract enough to absorb that.
6. **The space got crowded in 2026.** Five 1k+ star local-voice-assistant projects appeared since the prior scan. Publishing the framework early (already the plan, as burnout mitigation) is now *also* a competitive necessity.

---

## Sources

**Primary (verified 2026-07-13):**
- GitHub REST API repo state — `HeyWillow/willow` (pushed 2026-02-13, not archived, maintenance-only commits), `rhasspy/rhasspy3` (**archived**, 2023-12), `OpenVoiceOS/ovos-core`, `NeonGeckoCom/NeonCore`, `leon-ai/leon`, `pipecat-ai/pipecat`, `livekit/agents`, `home-assistant/core`
- GitHub search API — voice-assistant repos created since 2025, ranked by stars (surfaced Row-Bot, isair/jarvis, OHF-Voice/linux-voice-assistant, vui, ODS, moltis, CAAL, maxheadbox)
- home-assistant.io — Voice Chapter 11 (2025-10-22), full text; blog sitemap (confirming **no Voice Chapter 12** through 2026-07); release notes 2026.1 / 2026.3 / 2026.5 / 2026.7
- home-assistant.io — "Building the AI-powered local smart home" (2025-09-11): AI Tasks, MCP client+server, OpenRouter/400+ models, streaming TTS, "personas", intent-first fallback
- READMEs — `siddsachar/row-bot`, `isair/jarvis`, `OHF-Voice/linux-voice-assistant`, `dograh-hq/dograh`
- `siddsachar/row-bot` `docs/PROMPT_CONTEXT_AND_CACHE.md` — named prompt-section contract
- LiveKit Agents docs — `BackgroundAudioPlayer`: ambient + thinking sounds bound to agent lifecycle

**Secondary:** Pipecat docs/releases (Smart Turn, latency targets); 2026 local-voice-stack write-ups (Qwen3 as community default; ~1.5 s voice-to-voice bar).

**Internal:** `.planning/PROJECT.md`, `project-docs/02-core-software.md`, `project-docs/04-landscape-research.md` (**now partially stale — see Competitor State table**).

---
*Feature research for: local-first LLM-native personal voice assistant*
*Researched: 2026-07-13*
