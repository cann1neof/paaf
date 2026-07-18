# Pitfalls Research

**Domain:** Local-first, LLM-native personal voice assistant (Python framework + headless Linux appliance + Electron control panel), solo-maintained, open source
**Researched:** 2026-07-13 (research), 2026-07-18 (written)
**Confidence:** MEDIUM-HIGH. Post-mortems (Mycroft, Willow) and competitor/library behavior verified against primary sources. Latency budgets and AEC claims are from framework docs and reference implementations (Pipecat, LiveKit) — MEDIUM. Chatterbox-specific claims are **UNVERIFIED** and marked as such throughout; they are the Phase-0 spike.

> **Phase references** use the build-order numbering in `ARCHITECTURE.md` ("Build Order — dependency-ordered — this is the phase sequence"), steps 0–17. Where a pitfall maps to a broader stage I name it (Phase 0 spikes / Module 1 / Module 2 / Session / App / Launch).

---

## Severity Triage — Read This First

Not all pitfalls are equal. Four of these can end the project. The rest are cost.

| # | Pitfall | Severity | Why |
|---|---|---|---|
| 1 | **Hebrew/code-switching TTS doesn't work** | 🔴 **PROJECT-KILLER** | It is the #1 surviving differentiator (FEATURES.md) and it is **unverified**. If it fails, the founding language promise is unimplementable and the pitch collapses. |
| 2 | **Latency lands at 4–5s instead of 1.5s** | 🔴 **PROJECT-KILLER** | A slow voice assistant is not a worse product, it is a *non*-product. Nobody uses it twice. HA already shipped streaming TTS; users have felt the bar move. |
| 3 | **Solo-maintainer collapse** | 🔴 **PROJECT-KILLER** | Mycroft folded; Willow's bus factor was literally 1. This is the modal outcome for projects in this exact space. |
| 4 | **Privacy claim publicly falsified** | 🔴 **PROJECT-KILLER** | The entire pitch is "verifiable, not promised." One HN commenter's `tcpdump` showing an outbound packet destroys the project's only unassailable differentiator, permanently. |
| 5 | AEC / barge-in never works acceptably | 🟠 SEVERE | Table stakes in 2026. Degrades product to a demo. Recoverable via hardware recommendation. |
| 6 | Wrapper boundary leaks the agent framework | 🟠 SEVERE | Converts a two-way door into a one-way door. Discovered only when you need to swap — i.e. at the worst moment. |
| 7 | Plugin security theater | 🟠 SEVERE | A manifest that implies sandboxing it doesn't provide is a reputational + actual security liability on a device with `act` permissions. |
| 8 | The HA comparison is lost at launch | 🟠 SEVERE | Launch is a single-shot event. Losing the framing means the project reads as "worse HA." |
| 9 | Electron/device state desync | 🟡 MODERATE | Annoying, erodes trust in the config surface. Fixable. |
| 10 | Untestable audio pipeline | 🟡 MODERATE | Silent killer of velocity and of the solo maintainer's morale. Compounds #3. |
| 11 | Skill dependency hell | 🟡 MODERATE | Bites later, at ecosystem scale, which may never arrive. |

---

## Critical Pitfalls

### Pitfall 1: Promising code-switched multilingual speech before proving the TTS can do it

**What goes wrong:**
The README, the launch post, and the roadmap all commit to "understands AND speaks mixed English/Russian/Hebrew/Spanish, no language configuration." Then, six months in, you discover that Chatterbox Multilingual V3 takes a **per-call `language_id`** — it is *per-utterance language selection, not documented intra-sentence code-switching* — and that Hebrew output is unintelligible to a native ear. The single strongest differentiator in FEATURES.md is gone, after the architecture has been built around it.

**Why it happens:**
`PROJECT.md` states "STT is a non-issue here (Whisper-class models are natively multilingual and handle code-switching)." **This is overconfident and STACK.md formally corrects it.** Whisper runs language ID on only the **first 30s window** and emits **one language token per window** — on clips under a few seconds it often guesses wrong, and on bilingual audio it commits to one language early and then transliterates or silently *translates* the other. The standard mitigation is to pass an explicit ISO-639-1 code — which is exactly what a no-language-config design forbids. So the input side is *degraded*, not free.

The output side is worse. Modern Hebrew is orthographically opaque: vowels and stress are unmarked, so pronunciation is ambiguous even *with* nikud. Real-time Hebrew TTS conventionally needs a grapheme-to-phoneme front-end (Phonikud, arXiv 2506.12311, emits fully-specified IPA with stress and runs on a Pi; HebTTS takes a diacritic-free LM approach). **Generic multilingual TTS models generally mispronounce Hebrew without such a front-end.** Chatterbox listing `he` among 23 languages is a *coverage* claim, not a *quality* claim.

The root cause of the mistake is that language coverage is checkable by reading a model card in 30 seconds, so it *feels* verified — while quality and code-switching behavior are only checkable by running the model, which nobody does before writing the roadmap.

**How to avoid:**
1. **Phase 0, before any architecture code.** 20 real mixed-language sentences (en+ru+he+es mixed *within* the sentence). Vary `language_id`. Measure: does mixed script render intelligibly, or does it garble/skip the non-tagged span? Native-ear judgement on Hebrew — the maintainer has one; use it.
2. **Same 20 sentences through Whisper.** Measure WER and whether it locks onto one language. Get the number *before* it appears in a README.
3. **Decide the Hebrew fallback ladder position now, not at launch.** STACK.md's option A (a per-language *engine override* as a config escape hatch, e.g. cloud TTS for Hebrew only, refused in offline mode) costs nothing architecturally today and converts "Hebrew is broken" into "Hebrew has a documented tradeoff you control."
4. **Evaluate adding a Hebrew G2P front-end (Phonikud) behind the TTS Protocol** if raw Chatterbox Hebrew fails. This is a real, open, Pi-capable option that STACK.md's ladder doesn't list.
5. **Write the language claim in the README at the level you have measured**, not the level you hoped for. "Understands and speaks four languages including mid-sentence switching, with measured quality per language" beats a claim a user disproves in one sentence.

**Warning signs:**
- The roadmap contains the phrase "code-switching" but no phase contains a measurement.
- You catch yourself reasoning "the backbone is an LLM-style model so `language_id` is probably just a prior." That is hope, not evidence — STACK.md flags exactly this reasoning as unverified.
- Hebrew is tested with a single short phrase rather than sentences with mixed script.

**Phase to address:** **Phase 0 spikes (before build step 0/1).** This is the first thing measured in the entire project. STACK.md's Spike #1, #3, #4.

---

### Pitfall 2: Building a sequential pipeline and discovering the latency budget is already spent

**What goes wrong:**
Each stage waits for the previous one to complete. Wake word fires, capture runs, VAD waits out a conservative hangover, Whisper transcribes the whole utterance, the LLM generates the *entire* reply, TTS synthesizes the *entire* reply, playback begins. Every stage is individually reasonable. The total is **4–5 seconds** and the assistant is dead on arrival. LiveKit's docs are blunt: sequential wait-for-each-stage pipelines produce **2–4s**; overlapped streaming pipelines reach sub-1s.

**Why it happens:**
Latency is an *emergent* property of the whole system, so no single commit is where it goes wrong, and there is no moment at which anyone is obviously making a mistake. It is also invisible until voice exists — by which time the architecture is set.

**Realistic per-stage budget (target ≤1.5s time-to-first-audio):**

| Stage | Realistic cost | Lever size |
|---|---|---|
| Wake word detect | 50–150 ms | small |
| **End-of-speech decision (VAD hangover)** | **300–700 ms** | 🔴 **BIGGEST controllable chunk** |
| STT final (faster-whisper, ~3s utterance) | 200–500 ms | streaming partials hide most |
| **LLM time-to-first-token** | **300–800 ms cloud / 500–1500 ms local 7B on CPU** | 🔴 **second-biggest** |
| First sentence completes past TTFT | +100–400 ms | short first sentence |
| TTS time-to-first-byte (short sentence) | 50–150 ms streaming | small |
| Buffer → DAC | 20–100 ms | small |
| **Total** | **~1.0 – 2.5 s** | |

**The five specific mistakes that turn 1.5s into 5s:**

1. **Conservative VAD hangover.** Waiting 700–900ms of silence to be *sure* the user finished. This is the single largest self-inflicted cost and it's a one-line constant. LiveKit's answer is acoustic VAD **plus** a ~135M SmolLM-v2 fine-tune running locally that predicts "is this a finished thought." Pure-VAD hangover is where most budgets silently go.
2. **Waiting for the full LLM reply before speaking.** Sentence-by-sentence TTS streaming is not an optimization, it is the architecture. HA's streaming TTS release claimed a **9–13× perceived latency win** — users have already experienced this, so whole-reply TTS now reads as *broken*, not as *slower*.
3. **Ollama's `keep_alive` (default 5 min).** The first question after an idle period pays a multi-second model *load*. ARCHITECTURE.md calls this "the #1 latency surprise in local voice assistants." For a home assistant — which is idle by definition almost all of the time — **this is the common case, not the edge case.** Set `keep_alive: -1` for the primary local profile or ping on a timer, and make it a first-class config field with a sane default.
4. **Cold-start JIT.** onnxruntime and ctranslate2 are measurably slower on call #1. Every engine Protocol needs `async def warmup(self) -> None`, run concurrently at boot *before* mDNS advertises and *before* the wake word arms. Also: after a hot config reload, a new model profile must be **loaded and warmed before the swap**, or the first post-reload turn takes 10s.
5. **CPU inference contention.** Two concurrent Whispers on a Pi 5 thrash. Every engine needs a **bounded per-engine limiter** (one Whisper at a time). And nothing may run inference on the event loop — asyncio is single-threaded and any blocking call freezes the audio path. Use `anyio.to_thread.run_sync` (native runtimes release the GIL) and a process pool for pure-Python CPU work.

Plus one hardware-shaped trap: **Chatterbox is a 500M autoregressive model that will not run realtime on a Pi-class CPU.** `project-docs/03` targets Pi-class hardware. These are in direct conflict. **[UNVERIFIED — this is Spike #2 and it must run before hardware is purchased.]**

**How to avoid:**
- **Measure TTFA from the LLM phase, not the voice phase.** With a fake TTS that timestamps its first chunk, TTFA is measurable before any audio hardware exists. This is why `paaf-trace` (build step 3) must precede `paaf-voice` in build order.
- **Track TTFA as a number in CI from step 3 onward**, with a regression threshold. Not a note in a doc — a failing test.
- Record per-stage timings in the trace store from day one so a regression is attributable, not just visible.
- Optimize end-of-speech and TTFT. **Optimizing TTS is mostly wasted effort** — it's 50–150ms of a 1500ms budget.
- The "short first sentence" trick works, but do it honestly: a **default-on, visible, removable persona fragment** ("open with a brief first sentence"). PROJECT.md forbids hidden instructions, so it must appear in the composed-prompt viewer and be deletable. That constraint turns a cheat into a feature.

**Warning signs:**
- No TTFA number exists in CI at build step 9.
- The word "optimize later" appears near the voice pipeline.
- Latency is measured only warm, never after 30 minutes idle. (Measure the *cold* path — it's the real user experience.)
- The audio device callback contains an `await` or touches an asyncio object. PortAudio calls back on a C thread; that callback must only write to a preallocated ring buffer and signal via `loop.call_soon_threadsafe`. Violating this is the classic cause of clicks and dropouts.

**Phase to address:** Budget design in **Phase 0 Spike B** (build step 1b, WAV-in/WAV-out, no mic needed). Enforcement from **build step 3 (`paaf-trace`)** onward. Regression gate in CI from step 9.

---

### Pitfall 3: Solo-maintainer collapse — the modal outcome in this exact space

**What goes wrong:**
The project stalls. Not dramatically — it just stops. Commits become dependency bumps. Issues accumulate unanswered. It joins Willow and Mycroft on the list of open voice assistants that people cite as cautionary tales.

**Why it happens — the two verified case studies:**

**Mycroft (wound down Feb 2023):** A patent-troll suit (Voice Tech Corp) drained cash, and **hardware killed it**. The Mark II BOM went from ~$99 to ~$300; ~$100k went into injection molds; COVID wrecked the supply chain. The company shrank to 2 devs + 1 support + 1 attorney and could not fulfill Kickstarter rewards. Kathy Reid's post-mortem adds four structural lessons: (a) no music service — incumbents vertically integrate and Spotify revoked API access in 2020; (b) incumbents sell hardware as a **loss leader**, so you cannot win on hardware price; (c) the **skill-discovery problem** — users don't know what an assistant can do, and proactive suggestion is experienced as intrusive; (d) **privacy is friction**, not a feature most users will trade convenience for.

**Willow (stalled):** Its founder, Kristian Kielhofner, **died unexpectedly** (announced ~Dec 2024). The community later revived it under the HeyWillow org. As of 2026-02-13 the repo is not archived but shows only low-level ESP-IDF maintenance commits — no product development. **Bus factor of 1 is literal, not metaphorical.**

The generalizable failure modes:
- **Scope creep into hardware.** This is what actually killed Mycroft. `PROJECT.md` has already deferred the reference build — that is the single most important decision in the document.
- **Launching before it's installable.** A project that requires the maintainer to help each user install it converts every new user into a support ticket. Attention then flows to Discord/issues instead of code, which feels productive and is not.
- **No contributor on-ramp.** With no `CONTRIBUTING.md`, no architecture doc, and no tests that run without hardware, nobody can help even when they want to. `PROJECT.md`'s year-one success criterion is 3–5 merged external contributors — that requires a machine, not a wish.
- **Building the whole thing before shipping any of it.** Seven months of unshipped work with no external signal is exactly the burnout shape.

**How to avoid:**
- **Ship `paaf-llm` to PyPI at build step 9** (`paaf chat` CLI proves Module 1 standalone). The user's own stated mitigation. **Assessment: it is necessary but NOT sufficient.** It's a real, shareable artifact — a text-agent construction kit — and it front-loads external validation. But: it lands into the most crowded library category in open source, where "another LangChain wrapper" has near-zero attention. It will not produce meaningful users or contributors on its own.
  **Strengthen it three ways:** (i) publish it with the *one thing nobody else has* already working — the verbatim composed-prompt inspector, which FEATURES.md rates the best value/cost ratio in the whole project and which is a genuinely novel demo in a text-only package; (ii) pair the release with a written artifact (the architecture doc, or the "what I learned choosing an agent framework in 2026" writeup — STACK.md's LangChain-vs-Pydantic-AI reversal is genuinely publishable and would land on HN independently); (iii) treat it as a **dated commitment**, not "when it's ready."
- **Hold every anti-feature in FEATURES.md.** Multi-room, memory, a skills marketplace, a flow builder, macOS support — each is individually reasonable and collectively fatal. The skills marketplace is the most dangerous: it is a **moderation, security, and hosting obligation for a solo maintainer**. Row-Bot can afford one; PAAF cannot.
- **`CONTRIBUTING.md` + hardware-free CI at build step 0.** ARCHITECTURE.md's finding that even the barge-in state machine is testable with no microphone is the enabler here: a contributor can run the full test suite on any laptop.
- **Write down, publicly, what you will not build.** It's a defense against your own future enthusiasm and against issue-tracker pressure.
- **Set a support-time cap before launch** (e.g. one hour/day, batched). Decide it while calm.

**Warning signs:**
- Two weeks where all commits are dependency bumps or issue replies.
- The phrase "while I'm in there" appearing in scope discussions.
- Any hardware purchase before Spike #2 tells you what hardware is actually required.
- Reading GitHub notifications more often than the editor is open.
- No external human has run the code by month 5.

**Phase to address:** `CONTRIBUTING.md` + CI at **build step 0**. Public `paaf-llm` release at **build step 9** — treat as a hard, dated milestone. Anti-feature list in `DECISIONS.md` at step 0.

---

### Pitfall 4: Accidentally violating the offline claim — the differentiator that dies in one packet

**What goes wrong:**
Someone runs `tcpdump` during the launch thread and posts a screenshot of an outbound connection. FEATURES.md rates verifiable offline mode as the **second-strongest differentiator** precisely because everyone *claims* privacy and nobody lets you *check*. That asymmetry is the whole pitch — and it is asymmetric in the other direction too: the claim is binary, and one falsification is permanent.

**Why it happens:**
Nobody adds telemetry on purpose. It arrives through **defaults in the dependency tree**, and defaults change across versions. Verified examples from the ecosystem: **LangSmith tracing is opt-in** (via `LANGSMITH_TRACING` / `LANGSMITH_OTEL_ENABLED`) — fine — but **self-hosted Langfuse reports usage stats to PostHog by default unless `TELEMETRY_ENABLED=false`**. The posture across agent/observability libraries is *mixed*, which means it cannot be reasoned about; it must be measured.

**The specific leak sources for this stack:**

| Source | Leak | Notes |
|---|---|---|
| **Electron auto-updater** | Periodic HTTPS to the update host | Fires on app start by default in most `electron-builder` setups. The desktop app is on the user's *laptop*, not the device — but the claim will be read as covering both. **Decide and document the boundary explicitly.** |
| **Chromium itself** | Safe Browsing, variations/seed fetch, DNS prefetch, spellcheck dictionary download, OCSP | Electron ships a browser. Several of these fire without any app code. Needs explicit switches. |
| **Python deps with opt-out telemetry** | Varies by library *and by version* | Not enumerable by reasoning. Must be measured per lockfile update. |
| **First-run model downloads** | HuggingFace Hub, Ollama registry, openWakeWord model fetch, NLTK punkt (if used — ARCHITECTURE.md says don't) | Legitimate but must be a **separate, explicit, pre-offline provisioning step**, never lazy-on-first-use. A lazy download inside a "fully offline" session is the most likely accidental violation. |
| **mDNS / zeroconf** | Multicast chatter on the LAN | **LAN traffic is not a violation** — the device is *supposed* to be discoverable. But it will show up in a capture, so the Privacy page must explain what it is *before* someone asks. |
| **Crash reporters / Sentry** | Stack traces off-device | Never add one. Not even opt-in. |
| **NTP, DNS, OS updates** | Outbound from the host OS | Not the app's traffic, but will appear in a naive capture. The verification doc must scope the claim precisely. |
| **Cloud model profiles** | Intentional | The offline *enforcement* (refuse to start any component with a non-LAN endpoint) is what makes this honest. |

**How to avoid:**
- **Enforce at the network layer, not per-library config.** The cached research is explicit: *any offline claim must be enforced at the OS/network layer rather than trusted to per-library config, because dependency defaults vary and change across versions.* A config flag in each library is unauditable; a process-level egress denial is testable.
- **Endpoint declaration in the component interface from build step 2.** FEATURES.md flags this as architectural, not a toggle: if components can open sockets without declaring endpoints, enforcement becomes an unwinnable whack-a-mole audit later. Bake it into `paaf-core`.
- **A `tcpdump`-based CI job that fails the build on any non-LAN packet during a scripted offline session.** This turns the flagship claim into a test. It is the single highest-leverage item in this entire document relative to its cost.
- **Audit cadence — this is the "when":**
  - Every dependency addition or `uv.lock` update → run the capture job.
  - Every Electron/Chromium major bump → re-audit switches (new versions add new phone-homes).
  - Before every release → full manual capture, cold boot to idle to one turn.
- **Publish the verification recipe.** Not "we don't send data" — "here is the exact command; here is what you should see; here is what mDNS looks like and why it's there." That converts a marketing claim into a testable property, and it is *the* r/selfhosted and HN pitch.
- **Never ship telemetry, not even anonymous opt-in.** FEATURES.md is right: the moment there is a flag, the packet-capture demo becomes a lie.

**Warning signs:**
- A new dependency added without a capture run.
- The Privacy page lists claims but no reproduction commands.
- Anyone says "it's only the update check" or "that's just mDNS." Both may be fine — but only if *documented in advance*, never explained after a screenshot.
- A model download happens lazily inside a turn.

**Phase to address:** Endpoint declaration in **build step 2 (`paaf-core`)**. Capture CI job by **step 14 (`app-embedded`)**. Electron switches at **step 16**. Full audit gate before **step 15 (device bring-up)** and every release.

---

### Pitfall 5: Barge-in and AEC on a MacBook — the week you lose to acoustics

**What goes wrong:**
Barge-in "doesn't work." VAD fires constantly during playback. Or the assistant interrupts itself. Or it never interrupts. You spend a week debugging a state machine that is correct, because the problem is that the mic is hearing the speaker.

**Why it happens:**
In voice assistants the speaker is close to the mic, so the **echo-to-near-end-speech ratio is often below −10 dB**, making AEC mandatory for barge-in. Barge-in *is* the double-talk case — the hardest case for adaptive filters. And wake-word detection **does not tolerate nonlinear distortion**, which rules out residual echo suppressors and forces reliance on a linear adaptive filter alone.

The structural trap: **Pipecat and LiveKit both get AEC free from their transport** (Daily's media server / WebRTC does it at the media-server level). PAAF has no transport. Pipecat does not implement AEC at all. So every reference implementation you'll read from silently assumes a component you don't have.

**The MacBook-specific bite (this is the user's actual situation):**
Developing on a MacBook's built-in mic + built-in speakers, with no dedicated hardware:
- macOS gives you **no `module-echo-cancel`** — the Linux answer doesn't exist on the dev machine.
- The built-in mic/speaker path has no AEC available to your process.
- Built-in mics are near-field and beam-formed for a user sitting *at* the laptop — they are a poor proxy for far-field appliance behavior, so wake-word and VAD tuning done on the Mac **will not transfer** to a room-scale device.
- Result: barge-in will be flaky on the dev machine for reasons that have nothing to do with the code.

**How to avoid:**
- **Develop barge-in with headphones, or with the scripted fake-audio harness.** State this in the README. It is the cheapest possible mitigation and it saves a week.
- **Build the barge-in state machine with fakes, in CI, with no microphone.** ARCHITECTURE.md's most important build-order finding: `ScriptedAudioSource` (speech starting at t=1.2s, i.e. *during* playback), `FakeAudioSink` with a virtual playhead advancing in simulated realtime, `FakeSTT`/`FakeTTS`. A pytest run then asserts barge-in fires within 250ms, playback stops, the LLM stream cancels, and **the committed assistant message equals exactly the text spoken before the playhead**. Deterministic. Hardware-free.
- **Ship the AEC ladder as documentation, not code, first:** (1) hardware DSP — a ReSpeaker array or any USB conference speakerphone that does AEC in firmware; recommend this as the documented reference config, zero code; (2) Linux `PipeWire`/`PulseAudio` `module-echo-cancel` (webrtc-audio-processing underneath) — ship a setup snippet, this is where "Linux is the product" pays off; (3) in-process `AudioFilter` Protocol only if 1–2 prove insufficient.
- **Two concrete APIs the naive design misses:**
  - `AudioSink` must expose a **playhead** (ms actually out of the DAC). Without it, barge-in truncation is wrong and you commit sentences to history the user never heard.
  - `AudioSink` must expose a **reference tap** (what was actually sent to the DAC), because AEC needs it as the reference signal.
  Both cost nothing now and are painful to retrofit.
- **Do not ship half-duplex** (mute the mic while speaking). It disables barge-in entirely — one of the project's stated requirements. If AEC isn't available, use **partial ducking**: drop mic gain 10–20 dB during playback, so loud intentional barge-in still fires while quiet echo doesn't.
- **Debounce and pre-roll.** Require 120–250ms of continuously voiced audio before acting (a cough or a door otherwise kills playback), and **prepend that buffered pre-roll audio to the new STT stream** — skip it and you clip the user's first word every single time. ARCHITECTURE.md calls the pre-roll "the detail nearly everyone forgets."

**Warning signs:**
- VAD false-triggering during playback and the instinct is to raise the threshold. (Raising it breaks real barge-in; the problem is echo.)
- The word "AEC" does not appear in any phase.
- Wake-word thresholds tuned on the Mac and assumed to transfer.
- `AudioSink` has no playhead concept.

**Phase to address:** Protocols + fakes at **build step 10**; barge-in state machine at **step 13 (hardware-free)**; `AudioFilter` hook + reference tap at **step 12**; AEC *quality* tuning at **step 15 (target hardware only)**. README warning at step 12.

---

### Pitfall 6: The wrapper that leaks — where "never expose framework types" fails in practice

**What goes wrong:**
The rule "the public API never leaks the underlying agent framework's types" is stated in `PROJECT.md` and honored for three months. Then a `langchain_core.messages.AIMessage` appears in a return type because it was convenient. Then a callback signature takes a LangChain `Run`. Then the config schema mirrors LangChain's model-init string format. By the time Spike #5 says "switch to Pydantic AI," switching is a rewrite.

**Why it happens (and where the mitigation specifically fails):**
The mitigation fails in five places that discipline alone does not catch:

1. **Discipline is the mitigation.** ARCHITECTURE.md lists "relying on discipline to keep framework types out of the public API" as an explicit anti-pattern. Every leak is individually a five-minute convenience under deadline pressure.
2. **Type leaks are easy to spot; *semantic* leaks are not.** A wrapper can expose only its own dataclasses while its *lifecycle*, *error taxonomy*, and *streaming event shape* are a 1:1 mirror of the framework's. Then swapping requires reshaping the public API anyway. This is the failure mode wrappers most reliably hit.
3. **Streaming and callbacks are the hardest surface.** The whole reason STACK.md picks LangChain is that `AsyncCallbackHandler` is a near-perfect fit for draining runs into SQLite. That fit is *also* the strongest coupling in the codebase. Pydantic AI emits OTel spans instead — a structurally different event model. If `TraceEvent` is shaped like a LangChain callback, the port is fake.
4. **Exception types cross the boundary invisibly.** A `langchain_core` exception propagating to a user's `except` block is a leaked type nobody declared.
5. **Escaping into the framework's own escape hatches.** The moment a user-facing feature is implemented by exposing a LangGraph `interrupt()` or a raw checkpointer — which is exactly how STACK.md proposes implementing the `confirm` permission tier "nearly for free" — the free lunch is a coupling. **The `confirm` tier is where this project will most likely leak.** Treat LangGraph's `interrupt()` as an *implementation* of a PAAF-owned pause/resume concept, never as the concept itself.

There is also a versioning trap specific to the recommended stack: LangChain 1.0's no-breaking-changes-until-2.0 policy is verified and has held ~9 months — but **`langchain-mcp-adapters` is still `0.x`** and it carries a *core user-facing feature* (MCP). STACK.md names it the weakest link in the LangChain case. The stability promise does not extend to it. Additionally, a documented LangChain leaky-abstraction bug: `.bind(tools=...)` followed by `.with_structured_output(...)` **silently drops tools from the API payload** — the model gets no tools, hallucinates invocations, and the parser returns confidently-wrong structured data. That class of failure is exactly what a wrapper must not pass through.

**How to avoid:**
- **Mechanical enforcement from commit #1.** Confine all `langchain*` imports to a single `adapters/langgraph/` package; add a `ruff` `flake8-tidy-imports` banned-api rule **or import-linter contracts** that **fail CI** on any `langchain` import outside it. ARCHITECTURE.md puts import-linter contracts at **build step 0** — "must land here, not later." Not step 5, when the adapter is written.
- **Write the `fake/` adapter FIRST (build step 4, before the real one).** This is the highest-value structural decision in the build order. A port that a fake can satisfy is a real port; a port designed around one implementation is a mirror. It also unlocks everything downstream in CI.
- **The test that proves it's real:** the entire `paaf-llm` test suite passes against the fake adapter with zero framework installed. If any test needs LangChain, the boundary has a hole.
- **Own the trace event schema before writing the callback handler.** Design `TraceEvent` from the *product* requirement (what the Logs & Traces page must show), then map LangChain callbacks onto it. Never the reverse.
- **Own the run lifecycle vocabulary.** FEATURES.md notes the behaviors executor depends on run-phase timing (run start, thinking, tool call, first token, done) exposed as *our* concepts. Make "can I observe run-phase timing cleanly?" an explicit spike criterion.
- **Wrap and re-raise all framework exceptions** at the adapter boundary.
- **Accept the honest cost.** ARCHITECTURE.md is realistic that a second adapter implementation has a real price. The goal isn't a free swap; it's that the swap is *bounded and estimable* rather than a rewrite.

**Warning signs:**
- Any test in `paaf-llm` that imports `langchain`.
- A public dataclass whose fields are a 1:1 rename of a framework object.
- The `confirm` tier documented in terms of "checkpointers" or "interrupts."
- A user-reported traceback with `langchain_core` frames in it.
- The lint rule has an exception list, and the exception list is growing.

**Phase to address:** Import-linter contracts at **build step 0**. `fake/` adapter at **step 4, before the real adapter at step 5.** Spike A (step 1) judged specifically on "which is easier to hide behind a port," not "which is nicer."

---

### Pitfall 7: Plugin permission manifests as security theater

**What goes wrong:**
The skill system ships with a permission manifest, an install-time review screen, and per-tool `observe`/`act`/`confirm` tiers. It *looks* like a security boundary. It isn't. A skill is Python imported into the assistant process; it can `import os` and do anything the process can — including reading the config, the API keys, the trace database, and calling any tool directly, bypassing the tier system entirely. A user installs a skill from a random git repo believing the manifest constrains it.

**Why it happens:**
The manifest is genuinely useful for *disclosure* and *UX*, and it is easy to slide from "declares what it wants" into language that implies enforcement. Both prior-art ecosystems confirm there is no way out of this in-process:

- **Home Assistant / HACS:** custom integrations run **in-process with complete access to the HA installation**, and **HA does not claim a sandbox**. In Jan 2021, disclosures found multiple custom integrations allowing unauthenticated arbitrary file read, exposing stored credentials. HA's posture is warning + review, not enforcement.
- **Python packaging guidance generally:** *never import from untrusted sources.* Neither `importlib.metadata.entry_points()` (declarative, standard) nor `spec_from_file_location` (path-based) sandboxes anything. An imported plugin runs with full process privileges. **Real isolation requires a separate process or container — which is a different architecture.**
- **Mycroft/OVOS** have had skill manifests for a decade; FEATURES.md's advice is to steal OVOS's manifest *design* and not claim novelty. It's a packaging format, not a sandbox.

**The honest posture (state it in plain language in the docs):**
> "Skills are Python code that runs inside the assistant with full access to your machine. The permission manifest tells you what a skill *says* it will do — it is a disclosure and review mechanism, not a sandbox. Install skills only from sources you trust, exactly as you would with any `pip install`. MCP servers are different: they run out-of-process and can be isolated."

**How to avoid:**
- **Use `importlib.metadata` entry points, not path imports** (build step 8). Standard, declarative, registered in the skill's own `pyproject.toml`, and it makes the install step an explicit `pip install` — which correctly frames the trust decision in terms users already understand.
- **Put the real isolation where it's actually available: MCP servers.** They already run out-of-process by design. Subprocess/container isolation for MCP is achievable and honest; for in-process Python skills it is not.
- **Do not build a skills marketplace.** FEATURES.md is right that it is a moderation, security, and hosting obligation for a solo maintainer, *and* a supply-chain attack surface on a device with `act` permissions. `git clone` + review + curated links in the docs.
- **Ship the manifest format in v1 even if install-from-git is v1.x** so it isn't a breaking change later.
- **Keep permission tiers as a UX and intent mechanism** — they are genuinely valuable for constraining what the *LLM* does with tools (which is a real, different threat: prompt injection through tool results). Just never describe them as containing malicious *skill code*.

**Warning signs:**
- Any doc sentence containing "sandboxed," "isolated," or "restricted" about Python skills.
- The install review screen implies enforcement rather than disclosure.
- Someone proposes `RestrictedPython` or an import hook as "the sandbox." It isn't one.

**Phase to address:** Loader design + honest docs at **build step 8**. MCP out-of-process isolation at **step 7**. Security posture written into `DECISIONS.md` at step 0 so it can't drift.

---

### Pitfall 8: Losing the Home Assistant comparison at launch

**What goes wrong:**
The launch post goes up. The top comment is "why not just use HA Assist?" The answer is a paragraph of architecture. The thread concludes it's a worse HA. There is no second launch.

**Why it happens:**
Challengers to an incumbent open-source ecosystem lose on *distribution and completeness*, not on ideas. HA has 89k stars, daily commits, a mature web UI, and — since `OHF-Voice/linux-voice-assistant` (523★, active) — **official Linux voice satellites**, which kills the "HA needs a Pi or an ESP32" argument. The comparison will be made on HA's terms unless you set the terms first.

There is also a *positioning* trap. FEATURES.md's verdict: **do not lead with "user-facing LLM management."** Row-Bot (1.4k★, active) already occupies that phrase, markets itself as "Personal AI Sovereignty," and ships provider routing, agent profiles, a skills hub, per-tool approval, and realtime voice. Five of eleven claimed differentiators are already eroded. Leading with an eroded claim is how you lose the thread.

**But the wedge is real and it has widened.** Verified: HA's last Voice Chapter is **#11 (Oct 2025)**; there is **no Voice Chapter 12** as of 2026-07 and 2026 releases shipped only incremental voice work. HA's LLM layer is still a **single conversation-agent dropdown**, a **single instructions text box** for personas, and "prefer handling commands locally" (intent-engine-first, *not* model→model fallback). HA's "multilingual" means **two wake words bound to two separate per-language pipelines** — the literal opposite of code-switching. And there are real, documented HA pain points: with Ollama + Control Home Assistant enabled, community reports **2–7 minute responses on CPU**; exposing all entities inflates the prompt and prefill grows quadratically with context; no response streaming into the agent (core issue 149325).

**How to avoid:**
- **Lead with the framing FEATURES.md recommends:** *"an assistant appliance you own, that shows you its own mind, and proves it's offline."* Not "LLM management."
- **Ship the Home Assistant tool package in v1.** It is cheap and it converts the #1 objection into a *feature*: HA becomes something the assistant can drive, not a competitor. FEATURES.md rates it P1 at LOW cost — the best objection-per-hour ratio in the roadmap.
- **Refuse the Wyoming/ESPHome-compatibility trap.** FEATURES.md calls it "the sneakiest anti-feature": it looks like free distribution but inverts the architecture — you become a peripheral to HA's brain and the LLM management layer, *the entire product*, becomes irrelevant. `linux-voice-assistant` already fills that slot.
- **Have a fair comparison page ready at launch**, written honestly, including where HA wins (ecosystem, integrations, maturity). A comparison page that pretends the incumbent has no strengths is read as dishonest and costs more than it gains.
- **Lead the demo with the four things HA structurally cannot show:** (1) unplug the WAN mid-sentence and the assistant keeps talking (ordered fallback chains — *no voice assistant has this*); (2) the final composed prompt, verbatim, with nothing you didn't write; (3) `tcpdump` running live during a conversation; (4) a mixed-language sentence — **only if Spike #1 passed.**
- **Be installable.** A one-command install and a working demo video beat any argument.

**Warning signs:**
- The comparison page is drafted the week of launch.
- The launch post explains architecture before showing a demo.
- No answer prepared for "so it's Row-Bot with a wake word?" — the honest answer being that Row-Bot is a desktop app you sit in front of, not a far-field appliance.
- Anyone suggests Wyoming compatibility "just to get their users."

**Phase to address:** HA tool package by **build step 7–9**. Comparison page and positioning drafted at **step 0** and maintained. Launch readiness gate at **step 15–16**.

---

### Pitfall 9: Electron and the device disagree about the truth

**What goes wrong:**
The control panel shows a setting the device rejected. Or shows a model as active after a failed hot reload. Or two panels disagree. The user stops trusting the config surface — which, since the config surface *is* the product, is fatal to the value proposition.

**Why it happens:**
Optimistic UI. The panel updates local state on the click, fires the PUT, and doesn't reconcile with what the device actually accepted. ARCHITECTURE.md lists "optimistic UI in the desktop app" as an explicit anti-pattern. Config validation can legitimately reject or *transform* a value, and a hot reload can fail and roll back — in both cases the device's post-state differs from what the user typed.

Compounding it: `PROJECT.md` requires the desktop app hold **no state beyond device tokens**. That is the right call, and it means every screen must be a *view* of device state — but "no state" is easy to violate accidentally with a form's local state.

**How to avoid:**
- **TanStack Query, not Redux.** STACK.md is explicit: the device is the source of truth, so you need a server-state *cache*, not a client store. This is a structural fix, not a discipline fix.
- **Every mutation returns the resulting config revision**, and the client re-renders from the *response*, not from what it sent. Never render from the request body.
- **Config revisions are monotonic.** A WebSocket push carrying the new revision lets any stale panel invalidate itself. Concurrency: use compare-and-swap on the revision (`PUT` includes the revision it was editing; the device rejects on mismatch). ARCHITECTURE.md's Defect 7 flags "one YAML tree, the API edits it" as a **lost-update and corruption hazard** — validate → atomic write → new revision.
- **Reload failure must be a first-class UI state**, not a silent revert. "This change was rejected because X" with the offending field highlighted.
- **The device must work with the panel closed or deleted.** Test this explicitly: kill the Electron app mid-conversation; nothing should change.
- **Pairing/tokens:** PIN shown on the device, exchanged once for a token, stored in the OS keychain (not `localStorage`). Token must be revocable *from the device*, because the device is the thing the user physically owns. Bind the API to LAN only — and remember mDNS advertises it, so an unauthenticated endpoint is an open endpoint on the user's network.

**Warning signs:**
- A form field with local `useState` that isn't reconciled against a server response.
- Any client-side "current config" object that isn't a query cache.
- Two panels open produce different views and nobody noticed.
- The token lives in `localStorage`.

**Phase to address:** Config revisions + atomic write at **build step 2**. API + WS push at **step 14**. Desktop app at **step 16**.

---

### Pitfall 10: An audio pipeline nobody can test

**What goes wrong:**
The voice path has no automated tests because "the input is a microphone." Every change is validated by talking to the laptop. Regressions land silently. Latency drifts upward with no attribution. CI covers only the LLM module. Eventually the maintainer stops refactoring the voice code because they can't verify it — and stagnation in the hardest component is how the project dies quietly (see Pitfall 3).

**Why it happens:**
It genuinely *seems* untestable. And the reference implementations don't help — they're built around transports and live sessions.

**Why it's wrong — the key insight from ARCHITECTURE.md:**
**~80% of Module 2 and 100% of the session/barge-in logic need no microphone.** The pipeline components depend on *Protocols*, not devices:
- **Sentence aggregator** — pure string logic. Fully unit-testable, including all four languages and mixed script. This is the highest-risk-per-line component in the voice module and it is trivially testable.
- **STT/TTS engines** — WAV fixtures → golden transcripts. No mic.
- **Barge-in state machine** — `ScriptedAudioSource` emitting speech at t=1.2s (during playback), `FakeAudioSink` with a virtual playhead advancing in simulated realtime, `FakeSTT`/`FakeTTS`, and a fake LLM adapter with configurable TTFT and token cadence.
- **Only four things genuinely need hardware:** AEC quality, far-field wake-word accuracy, real-device latency numbers, and GPIO. All tuning, not architecture.

**How to avoid:**
- **Write the fakes/testing harness as part of the Protocol definition (build step 10), not after the real engines.** If the fakes come second, the Protocols will have been shaped by one implementation and the fakes won't fit.
- **Assert the hard invariants in CI:** barge-in fires within 250ms; playback stops; the LLM stream is cancelled; **the committed assistant message equals exactly the text spoken before the playhead**; pre-roll audio is prepended; the trace records `interrupted=1`.
- **Track TTFA as a CI metric with a regression threshold** from build step 3 onward, using a fake TTS that timestamps its first chunk. Latency regressions must fail a build, not surprise you at launch.
- **A golden-transcript corpus for the four languages**, including code-switched sentences, run on every change to STT config. This is also how you *keep* the language claim honest over time.
- **A small set of genuinely-hardware tests, clearly separated and manually run**, with a documented checklist for device bring-up.
- **CI must run with no audio hardware** — `PROJECT.md` already requires this. It is also the contributor on-ramp (Pitfall 3).

**Warning signs:**
- The test suite skips when no audio device is present.
- No latency number in CI.
- The sentence aggregator has no tests with Hebrew or Russian input.
- Refactoring the session module feels risky.

**Phase to address:** Testing fakes at **build step 10** (with the Protocols). TTFA metric from **step 3**. Barge-in test suite at **step 13**. Hardware checklist at **step 15**.

---

### Pitfall 11: Skill dependency hell and version skew

**What goes wrong:**
Two skills need incompatible versions of the same library. Or a skill pins an old `pydantic` and breaks the whole assistant on install. Or the framework upgrades and every third-party skill breaks silently — the assistant starts up, the skill's tools just aren't there, and the user thinks the *assistant* is broken.

**Why it happens:**
Entry-point-based plugins share one Python environment by construction. That's the tradeoff for the standard mechanism. It's a real cost, but it's the *right* tradeoff — the alternative (per-skill venvs or containers) is a different architecture with a large latency and complexity price.

**How to avoid:**
- **Version the skill manifest schema from v1**, with an explicit `paaf_api_version` field. A skill declaring an incompatible API version must **refuse to load loudly** — surfaced in the control panel and spoken via the `tool_error` behavior — never fail silently.
- **Skill load failures are first-class UI state.** "3 skills loaded, 1 failed: `weather-plus` requires paaf>=2.0" on the Skills page. Silent degradation is the specific failure that makes users distrust the whole system.
- **Keep the framework's own dependency surface small and its version floors low.** Every tight pin in `paaf-llm` is a constraint every skill author inherits.
- **Deprecate with a window.** As a solo maintainer, breaking the skill API casually is how you lose the few contributors you have.
- **Push heavy/conflicting integrations toward MCP**, which is out-of-process and therefore dependency-isolated by construction. This is a real architectural answer to dependency hell, not just a security answer.
- **`uv` workspaces** are the right monorepo shape: one `uv.lock` and one `.venv` at the root, each member with its own `pyproject.toml`, version and release cadence, depending on each other via `[tool.uv.sources] workspace = true` — which resolves locally in dev but becomes a normal PyPI dependency in the built wheel. **That's what keeps `paaf-llm` genuinely pip-installable standalone** (the Pitfall 3 mitigation). `uv build --package <name>` builds one member.

**Warning signs:**
- The manifest has no API version field.
- A skill failing to load produces only a log line.
- `paaf-llm` pins an upper bound on a common library.

**Phase to address:** Manifest schema + `paaf_api_version` at **build step 8**. Workspace layout at **step 0**. Skills page failure states at **step 16**.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Wire mic→LLM→speaker as glue in `main.py` | Working demo in a day | Becomes an untestable 900-LOC file with barge-in tangled into the audio callback. Both Pipecat (`Pipeline`) and LiveKit (`AgentSession`) give the orchestrator a name, package, and lifecycle — it's the hardest component, not wiring | **Never.** `paaf-session` is a package from day one |
| Put the sentence aggregator in the app | Feels like app-level policy | Module 2 becomes unusable standalone; the aggregator can't know the engine's preferred chunk size | **Never.** Lives in `paaf-voice`, owned by the TTS service |
| Use NLTK `sent_tokenize` for sentence boundaries | It exists, it's one line | Per-language punkt models, requires a **downloaded model**, and must be **told which language it's reading** — violating the founding no-language-config rule. Pipecat itself flags that it returns a single sentence for single-word inputs, which is exactly what LLM tokens look like | **Never.** Use a rules-based Unicode terminator set — `.!?` covers all four languages by construction |
| Write traces synchronously in the callback handler | Simple, obviously correct | SQLite write on the hot path; auto-checkpoint (default 1000 pages) causes a latency spike at an unpredictable moment | **Never.** WAL mode, in-memory queue, single dedicated writer task; producers enqueue and return. Disable `wal_autocheckpoint`, checkpoint explicitly when idle. `synchronous=NORMAL` |
| Mutate live config objects on hot reload | Avoids rebuild complexity | Torn reads mid-conversation; a half-applied config is unreproducible from the file | **Never.** Build-new + atomic-swap |
| Skip the `fake/` adapter, write LangGraph first | Faster to a working agent | The port is shaped by one implementation; the swappability guarantee is fiction; no hardware-free CI | **Never.** Fake first (build step 4) |
| Skip `AudioSink` playhead and reference tap | Simpler audio API | Barge-in truncation is wrong (history contains unspoken text); AEC has no reference signal | **Never.** Both cost nothing now |
| Half-duplex (mute mic during playback) | Barge-in "problem" disappears | Barge-in is a stated requirement; deleting it deletes a table-stakes feature | Only as a *documented user setting* for bad acoustics, never the default |
| One YAML file the API rewrites in place | Simple | Lost updates, corruption on crash mid-write | **Never.** Validate → atomic write → revision |
| Ollama default `keep_alive` | Nothing to configure | Multi-second model load on the first turn after idle — the common case for a home assistant | **Never.** First-class config field, sane default |
| Hardcode `language="en"` in Whisper "for now" | Fixes short-utterance misdetection instantly | Violates the founding rule and, once tests pass with it, it never comes out | Only in a spike, never in `main` |
| Ship the launch before a one-command install | Momentum | Every user becomes a support ticket; maintainer attention goes to Discord instead of code | **Never** — this is a documented Pitfall 3 mechanism |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| **Ollama** | Default `keep_alive` (5 min) → multi-second cold load on the first turn after idle | `keep_alive: -1` for the primary local profile, or a keep-warm ping. First-class config field |
| **Ollama** | Choosing the model on chat quality | **Select on tool-calling reliability.** An assistant that can't emit a well-formed tool call is useless regardless of prose quality. Benchmark it yourself — STACK.md marks the current community default **[UNVERIFIED]** |
| **Ollama via LangChain** | Assuming token counts arrive | Token counts commonly come back `None` for Ollama across frameworks. **Verify against your actual provider** (STACK.md Spike #5) — the trace store's token column depends on it |
| **LangChain** | `.bind(tools=...)` then `.with_structured_output(...)` | Documented bug: tools are **silently dropped** from the payload; the model hallucinates invocations and the parser returns confidently-wrong data. Don't compose these; test the combination |
| **`langchain-mcp-adapters`** | Treating it as covered by LangChain's 1.0 stability policy | It is **`0.x`** and carries a core user-facing feature. Pin exactly, upgrade deliberately, and keep MCP behind your own port |
| **faster-whisper on macOS** | Expecting GPU acceleration | **CTranslate2 has no Metal backend — it is CPU-only on the Mac.** Use `whisper.cpp` (Metal+CoreML) or `mlx-whisper` for the dev harness. This is the pluggable-STT-interface's first proof of value |
| **Whisper** | Trusting auto-detect on short utterances | Language ID runs on the first 30s window only; short clips guess wrong, bilingual audio commits early. Budget for it; measure it; never silently "fix" it with a hardcoded language |
| **Chatterbox** | Assuming `language_id` enables intra-sentence mixing | It is **per-utterance selection**. Intra-sentence code-switching is **not a documented feature of any engine found**. **[UNVERIFIED — Spike #1]** |
| **Chatterbox** | Shipping PerTh neural watermarking silently | It is embedded in every output by default. For a project whose commitment is "nothing hidden from the user," this must be an explicit, documented, user-visible decision — it's a removable pipeline step |
| **Piper** | Assuming it's a safe default | `rhasspy/piper` is **ARCHIVED**; the successor `piper1-gpl` is **GPL-3.0** — not bundleable as a default in an Apache-2.0 framework without thought |
| **openWakeWord** | Trusting baseline models' false-activation rate | Baseline false activations are often unacceptable. Documented remedies: **custom verifier models** plus a **VAD gate** to suppress non-speech false positives. Training a good custom wake word is genuinely hard (hyperparameters, sample generation), and phrases acoustically close to existing ones degrade. Also: PyPI frozen at 0.6.0 since 2024-02 — keep it behind a swappable interface; `sherpa-onnx` keyword-spotting is the escape hatch |
| **`sounddevice`/PortAudio** | Treating the device callback as normal Python | It fires on a **C thread**. No `await`, no allocation, no asyncio object access. Write to a preallocated ring buffer; signal via `loop.call_soon_threadsafe`. The classic cause of clicks and dropouts |
| **asyncio + ML inference** | Running inference inline in a coroutine | Single-threaded event loop → buffer underruns and missed interruptions. `run_in_executor`/`anyio.to_thread` with a **bounded per-engine limiter**; process pool for pure-Python CPU work |
| **SQLite trace store** | An ORM | It's an append-mostly event log. Raw SQL + `aiosqlite`, WAL, single writer |
| **mDNS/zeroconf** | Forgetting it advertises an endpoint | The API must be LAN-bound *and* authenticated. Discovery is not authorization |
| **Electron** | Leaving auto-update and Chromium network services on | Both fire without app code. Disable explicitly; document what remains; re-audit on every Chromium bump |
| **Home Assistant** | Implementing Wyoming/ESPHome compatibility | Inverts the architecture — PAAF becomes a peripheral to HA's brain and the product becomes irrelevant. HA is an **outbound tool package**, never an inbound protocol master |

---

## Performance Traps

Scale here is not users — it is **conversation length, idle time, uptime, and trace volume**.

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Prompt growth with conversation history | TTFT creeps up within a session; later turns noticeably slower | Bounded history window; measure TTFT vs. turn index. **Prefill latency grows quadratically with context length** — this is the documented HA/Ollama failure (2–7 min responses) | Long multi-turn sessions on local models |
| Exposing every tool/entity in the prompt | Same as above, but permanent | Curate the tool set; this is the real argument for routing rules (fast small model for home control). HA users work around it with RAG to shrink the prompt | As soon as the tool count grows |
| Trace store unbounded growth | Disk fills on an appliance that runs for months | Retention policy + index on timestamp from day one; the Logs page should never scan the whole table | Months of uptime |
| SQLite auto-checkpoint spike | Random ~100ms+ stalls with no attributable cause | Disable `wal_autocheckpoint`; checkpoint explicitly from the writer task when idle | Under sustained write load |
| Model memory co-residency | OOM or thrash on the target device | **Whisper + TTS + a 7B local model will not comfortably co-reside on a Pi 5.** Design engine Protocols so an implementation can be a **remote client** (`remote/http`, `remote/wyoming`) from day one — costs nothing now, saves a rewrite, and buys instant compatibility with existing Wyoming whisper/piper/openwakeword servers | Target hardware bring-up (step 15) |
| Cold-path latency measured only warm | Demo is fast; real use is slow | Always measure after ≥30 min idle. For a home assistant, **cold IS the common case** | Day one of real use |
| Concurrent inference contention | Latency doubles unpredictably under load | Bounded per-engine limiter (one Whisper at a time) | Two overlapping turns, or barge-in during synthesis |
| Behaviors executor competing with the reply for the speaker | Thinking sound plays over the answer | Priority-laned audio output bus, single owner of the sink | First time a behavior fires late |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Implying skills are sandboxed | Users install untrusted code believing it's constrained; reputational damage when disproven. **HA precedent: custom integrations run in-process with complete access; Jan 2021 disclosures found unauthenticated arbitrary file read exposing credentials** | Plain-language docs: the manifest is **disclosure, not enforcement**. Real isolation only for out-of-process MCP servers |
| Unauthenticated LAN API | mDNS advertises it; anyone on the network (incl. IoT devices) can reconfigure the assistant, read traces, and read prompts | PIN pairing → token; token in OS keychain; revocable **from the device**; LAN-bind only |
| API keys in the YAML config tree | The config is edited over the network and shown in a UI; keys leak into screenshots, backups, and issue reports | Separate secret store (`paaf-core`, step 2). Never returned by the API — write-only, with a masked display |
| Trace store contains everything ever said | It is a verbatim transcript of household conversation, on disk, unencrypted | Correct by design (local-first) — but retention policy, file permissions, and a **one-click purge** in the Privacy page are required. Redaction options worth considering (isair/jarvis ships auto-redaction) |
| Prompt injection via tool results | An MCP server or web-fetching tool returns text that instructs the model to call an `act` tool. **On a device that can unlock doors** | This is what permission tiers are genuinely for. `confirm` for anything physical/irreversible. **Note the tension:** Row-Bot defends with hidden injection-defense instructions; PAAF's "we add nothing you can't see" rule forbids that — so the defense must be the **permission model**, not a secret prompt. This is a real architectural constraint, not an oversight |
| Skills from arbitrary git URLs | Supply chain on a device with `act` permissions | No marketplace. `git clone` + explicit review + curated links. Frame install as `pip install` so the trust decision is familiar |
| Electron `nodeIntegration` / loose CSP | Standard Electron RCE surface | Context isolation on, `nodeIntegration` off, strict CSP, no remote content |
| Hot-reload endpoint accepting arbitrary config | Config that names an executable or an endpoint = remote code/exfil path | Strict Pydantic validation; offline mode **refuses** any non-LAN endpoint at validation time, not at connect time |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---|---|---|
| Silence while thinking | The user repeats themselves or walks away; the assistant feels broken | The behaviors table — but reframe the claim honestly. LiveKit ships `BackgroundAudioPlayer` with ambient + thinking sounds bound to the agent lifecycle. **The novel part is the timed escalation ladder (2s→6s→12s), user-editable declaratively, covering failure modes** — not "we invented thinking sounds." Overclaiming will be called out at launch |
| Timers/alarms missing at launch | Day-one testers conclude it's a demo | Ship 4–6 built-in tools (timers, alarms, weather, music control). FEATURES.md: P1, LOW cost |
| Requiring re-wake after every turn | Conversation feels transactional; HA already shipped continuation | If the assistant asks a question, keep listening. LOW-MED cost, high perceived quality |
| Wake word false-fires | The assistant talks to the TV. On a privacy-first device this is *especially* damaging — it reads as "always listening" | VAD gate + custom verifier model. Measure **false-accepts-per-hour on real ambient household audio**, the metric microWakeWord optimizes first |
| Wake word never fires from across the room | Reads as broken | Far-field accuracy needs real hardware — do not tune it on a MacBook |
| Barge-in clipping the user's first word | Every interruption starts mid-word; STT quality craters | Prepend the 120–250ms debounce pre-roll to the new STT stream |
| History containing text the user never heard | The assistant references things it didn't say; conversation becomes incoherent | Commit only `tts.spoken_text_up_to(playhead_ms)` on interrupt |
| TTS reading markdown and emoji aloud | "asterisk asterisk important asterisk asterisk", "smiling face" | Sanitize before synthesis: strip markdown and emoji; **suppress code blocks entirely** and emit a behavior instead ("I've printed that for you") |
| Right-to-left text broken in the Electron UI | Hebrew appears reversed or mis-ordered in the trace viewer, prompt inspector, and chat panel — **and the maintainer, being a Hebrew reader, will notice immediately while contributors won't** | Set `dir="auto"` on all user/model text containers (per-element, not on `<html>`), use logical CSS properties (`margin-inline-start`, not `margin-left`), and include a Hebrew string in every UI snapshot test. Mixed LTR/RTL in one line is the actual hard case — bidi isolation (`<bdi>`, or `unicode-bidi: isolate`) around each language run |
| Language claim overstated in the README | The first Hebrew-speaking user disproves it publicly | Claim exactly what was measured, per language |
| Config change with no visible effect | User doesn't know if it applied | Every mutation returns the resulting revision; the UI renders from the response and shows explicit rejection states |
| Skill silently fails to load | User blames the assistant | Loud, visible load failures on the Skills page + `tool_error` behavior |

---

## "Looks Done But Isn't" Checklist

- [ ] **Streaming TTS:** Often missing *asymmetric* first-chunk thresholds — verify `MIN_CHARS` is ~6 for the first chunk of a turn and ~25 after. The asymmetry *is* the TTFA win
- [ ] **Sentence aggregator:** Often missing suppression rules — verify `.` is not a terminator in "3.14", "J. R. R.", URLs, or emails; verify it emits on `\n`, on 200+ chars with a soft break, and always flushes at turn end
- [ ] **Sentence aggregator:** Often only tested in English — verify with Russian, Hebrew, Spanish, and **mixed-script** input
- [ ] **Barge-in:** Often missing the playhead — verify the committed assistant message equals *exactly* what left the DAC, not what was generated
- [ ] **Barge-in:** Often missing pre-roll — verify the debounce audio is prepended to the new STT stream
- [ ] **Barge-in:** Often missing debounce — verify a cough or door slam does not kill playback
- [ ] **Offline mode:** Often only a config flag — verify with an actual packet capture, cold boot → idle → one turn, and verify it *refuses to start* with a non-LAN endpoint configured
- [ ] **Offline mode:** Often broken by lazy model downloads — verify no model is fetched during a session
- [ ] **Hot reload:** Often missing warm-before-swap — verify the first turn after a model-profile change is not 10s slower
- [ ] **Hot reload:** Often untested mid-conversation — verify a reload landing during an active turn does not corrupt it
- [ ] **Wrapper boundary:** Often type-clean but semantically leaky — verify the full `paaf-llm` suite passes against the `fake` adapter with **no framework installed**
- [ ] **Trace store:** Often missing token counts for local models — verify they are non-`None` for Ollama, or the UI must handle absence gracefully
- [ ] **Trace store:** Often missing MCP tool args/results — verify they surface through the callback path (STACK.md Spike #5)
- [ ] **Prompt inspector:** Often shows a *reconstruction* — verify it shows the literal string sent to the model, byte for byte. This is the flagship claim; a reconstruction is a lie
- [ ] **Permission tiers:** Often bypassable — verify a tool called via a *skill's own code path* still hits the tier check, and document that a malicious skill can bypass it entirely
- [ ] **Fallback chains:** Often only tested by killing the process — verify against a *hung* provider (timeout) and an *overloaded* one, not just a refused connection. The demo is unplugging the WAN mid-sentence
- [ ] **Latency:** Often measured warm — verify after ≥30 min idle, with `keep_alive` in its shipped default
- [ ] **Desktop app:** Often holds hidden state — verify deleting the app entirely leaves the assistant fully working
- [ ] **RTL:** Often only checked in the chat panel — verify Hebrew renders correctly in the trace viewer, prompt inspector, persona editor, and logs
- [ ] **Install:** Often "works on the maintainer's machine" — verify on a clean Linux box, from the published artifact, following only the README

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Chatterbox can't code-switch / Hebrew unusable | **HIGH if late, LOW in Phase 0** | Invoke STACK.md's fallback ladder: (A) per-language engine override as a config escape hatch — architecture already supports it, offline mode refuses it, user chooses with full visibility; consider a Hebrew G2P front-end (Phonikud) behind the TTS Protocol; (B) ship Hebrew as explicitly experimental; (C) understand Hebrew, reply in English. **Never (D) per-language voice switching — it breaks on the exact case it was rejected for.** Rewrite the language claim to match measurement |
| Latency lands at 3s+ | MEDIUM | Attribute per-stage from the trace store — the whole reason `paaf-trace` precedes voice. Attack end-of-speech and TTFT first, in that order; ignore TTS. Consider a turn-detection model over pure VAD hangover. Consider a smaller local profile via routing rules |
| Chatterbox too slow for target hardware | MEDIUM (LOW if caught pre-purchase) | `sherpa-onnx` as the escape hatch (one ONNX runtime for STT+TTS+VAD+KWS, CPU-first, Apache-2.0, very active) — with an honest reassessment of language coverage. Or move engines out-of-process to a beefier box via the `remote/` engine implementations |
| Wrapper leaked; framework swap needed | **HIGH** | Identify leaks by deleting the framework and compiling against the fake. Re-port incrementally. **This is why the fake adapter must be written first** — it makes this recovery a bounded job instead of a rewrite |
| Telemetry found in a dependency | LOW if caught by CI, **CATASTROPHIC if found publicly** | If pre-launch: pin/patch/remove, add the capture test. If public: immediate, specific, unhedged public disclosure with the fix and the new automated test. A defensive response ends the project's credibility faster than the leak did |
| AEC never good enough in software | LOW | Document a hardware requirement — a USB conference speakerphone with firmware AEC. "Buy a $60 mic" is a legitimate answer for an appliance, and Tier 1 in ARCHITECTURE.md's ladder is *the recommended reference config* anyway |
| openWakeWord abandoned | LOW-MEDIUM | Swap to `sherpa-onnx` keyword-spotting behind the existing Protocol. This is the exact scenario the Protocol exists for |
| Maintainer burnout | **HIGH** | Reduce scope publicly and explicitly rather than going quiet. A documented "maintenance mode, PRs welcome, here is the architecture doc" is recoverable; silence is what makes a project dead |
| Launch lost to the HA comparison | HIGH | There is no second launch of the same kind, but there is a second *audience*. r/LocalLLaMA and the framework-developer audience respond to different claims than r/selfhosted. Stagger the launches deliberately rather than firing all channels at once |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase (build-order step) | Verification |
|---|---|---|
| Code-switching / Hebrew TTS unverified | **Phase 0 spikes — before step 0** | 20 mixed sentences measured; native-ear Hebrew judgement recorded in `DECISIONS.md`; README claim matches measurement |
| Whisper code-switched STT degradation | **Phase 0 spike** | WER on the same 20 sentences; does it lock to one language |
| Chatterbox compute vs. hardware | **Phase 0 spike — before any hardware purchase** | TTFA for one short sentence on Mac MPS / CPU / consumer GPU |
| Wrapper leaks framework types | **Step 0** (import-linter) + **step 4** (fake adapter first) | CI fails on `langchain` import outside `adapters/langgraph/`; full `paaf-llm` suite green against the fake with no framework installed |
| Framework choice is wrong | **Step 1 (Spike A)** | Judged on "easier to hide behind a port," not "nicer." Falsification test = STACK.md Spike #5 (callbacks → SQLite incl. MCP args/results and Ollama token counts) |
| Offline claim violated | **Step 2** (endpoint declaration) → **step 14** (capture CI) → every release | `tcpdump` CI job fails on any non-LAN packet during a scripted offline session |
| Config corruption / lost updates | **Step 2** | Validate → atomic write → monotonic revision; concurrent-edit test |
| Latency budget blown | **Step 3** (`paaf-trace` precedes voice) | TTFA in CI with a fake TTS, regression threshold, measured cold |
| Trace store on the hot path | **Step 3** | WAL + queue + single writer; no SQLite call in a callback; autocheckpoint disabled |
| Prompt inspector shows a reconstruction | **Step 6** | Byte-for-byte equality assertion against what the adapter sent |
| Prompt injection via tool results | **Step 7** | `confirm` tier on every irreversible/physical tool; documented that defense is the permission model, not a hidden prompt |
| Plugin security theater | **Step 8** | Docs contain no "sandbox" language; entry-point loading; MCP isolated out-of-process |
| Skill version skew / dep hell | **Step 8** | `paaf_api_version` in the manifest; incompatible skills refuse to load loudly |
| Solo-maintainer collapse | **Step 0** (CONTRIBUTING + HW-free CI) → **step 9** (dated PyPI release of `paaf-llm`) | An external contributor runs the full suite on a laptop with no audio hardware; the release ships on its date with the prompt inspector working |
| Sentence-boundary breakage on non-Latin scripts | **Step 10** | Unit tests in en/ru/he/es and mixed script; no NLTK dependency anywhere |
| Untestable audio pipeline | **Step 10** (fakes with the Protocols) | ≥80% of Module 2 tested without a microphone |
| AEC / barge-in | **Step 12** (filter hook + reference tap) → **step 13** (state machine, HW-free) → **step 15** (quality) | Committed message == text before playhead; pre-roll prepended; debounce holds; README warns about MacBook acoustics |
| Wake-word false activations | **Step 11**, tuned at **step 15** | False-accepts-per-hour on real ambient household audio |
| Behaviors fighting the reply for the speaker | **Step 13** | Priority-laned output bus; single sink owner |
| Electron/device state desync | **Step 14** (revisions + WS push) → **step 16** | Mutations render from the response; two open panels stay consistent; deleting the app leaves the assistant working |
| RTL / Hebrew rendering | **Step 16** | Hebrew string in every UI snapshot test; mixed LTR/RTL line renders correctly |
| Electron network chatter | **Step 16** | Auto-update and Chromium services disabled; re-audit on every Chromium bump |
| HA comparison lost | **Step 0** (positioning drafted) → **step 7–9** (HA tool package) → **step 15–16** (launch readiness) | Comparison page exists and concedes HA's real strengths; one-command install verified on a clean box; four demos rehearsed |

---

## Sources

**Post-mortems (HIGH confidence):**
- Mycroft AI wind-down (Feb 2023) — Voice Tech Corp patent suit; Mark II BOM $99→$300; ~$100k injection molds; reduced to 2 devs + 1 support + 1 attorney; unfulfilled Kickstarter
- Kathy Reid's Mycroft post-mortem — no music service (Spotify API revoked 2020), incumbent hardware loss leaders, skill discovery problem, privacy-as-friction
- Willow — founder Kristian Kielhofner's death (~Dec 2024, `toverainc/willow-inference-server` #161); community revival under HeyWillow; repo at 3,069★, last push 2026-02-13, ESP-IDF maintenance commits only
- `rhasspy/rhasspy3` — formally ARCHIVED, last push 2023-12-26

**Reference implementations (MEDIUM confidence):**
- LiveKit Agents — `AgentSession`; overlapped streaming vs. 2–4s sequential; LLM TTFT 300–800ms, TTS TTFB 100–200ms; turn detection = acoustic VAD + ~135M SmolLM-v2 local fine-tune; barge-in rollback to what was actually spoken
- Pipecat — `FrameProcessor` model; `TextAggregationMode.SENTENCE` (~200–300ms/sentence) vs `TOKEN`; NLTK `sent_tokenize` + `UNAMBIGUOUS_SENTENCE_ENDING_PUNCTUATION`; documented weakness on single-word LLM tokens; **does not implement AEC** (relies on transport); interruption is an abrupt hard stop
- Voice-agent latency decomposition — 1.4s = 280ms STT + 600ms LLM TTFT + 320ms TTS TTFB + 200ms transport; sub-800ms median industry target

**Domain-specific (MEDIUM confidence):**
- AEC in voice assistants — echo-to-near-end ratio often below −10dB; barge-in is the double-talk case; wake-word detection intolerant of nonlinear distortion, forcing linear adaptive filtering alone
- Whisper language ID — first-30s-window only; short-clip misdetection; early commitment on bilingual audio; standard mitigation is an explicit ISO-639-1 code
- Hebrew TTS — orthographic opacity; G2P front-end needed; Phonikud (arXiv 2506.12311, `thewh1teagle/phonikud`, Pi-capable, IPA with stress); HebTTS (`slp-rl/HebTTS`)
- openWakeWord false-activation remedies — custom verifier models + VAD gate; microWakeWord's false-accepts-per-hour-first optimization
- Home Assistant custom integrations — in-process, no sandbox claimed; Jan 2021 unauthenticated arbitrary-file-read disclosures
- Python plugin loading — `importlib.metadata.entry_points()` vs `spec_from_file_location`; neither sandboxes; "never import from untrusted sources"
- asyncio + realtime audio — event-loop blocking; `run_in_executor` with thread pool for GIL-releasing native runtimes; `call_soon_threadsafe` from device callbacks
- SQLite WAL — reader/writer non-blocking; single-writer queue pattern; autocheckpoint latency spike; `synchronous=NORMAL`
- Telemetry posture — LangSmith opt-in via env vars; **self-hosted Langfuse reports to PostHog by default unless `TELEMETRY_ENABLED=false`**; enforce at the OS/network layer
- LangChain leaky abstraction — `.bind(tools=...)` + `.with_structured_output(...)` silently drops tools
- `uv` workspaces — single lock/venv, per-member versioning, `[tool.uv.sources] workspace = true`, `uv build --package`

**Competitor state (verified 2026-07-13):**
- HA Assist 2026 — Voice Chapter 11 (2025-10) is the last; no Chapter 12; single conversation-agent dropdown; single instructions box; intent-first "prefer local"; two wake words → two per-language pipelines; community reports of 2–7 min Ollama responses on CPU; quadratic prefill growth; core issue 149325
- `OHF-Voice/linux-voice-assistant` (523★, active) — official Linux voice satellites
- Row-Bot (1.4k★, active), `isair/jarvis` (1.35k★) — competitive positioning

**Internal:**
- `.planning/research/STACK.md` — the recommended stack and the Phase-0 spike list this document is aligned to
- `.planning/research/ARCHITECTURE.md` — build order, latency budget, anti-patterns, AEC ladder, barge-in sequence, aggregator spec
- `.planning/research/FEATURES.md` — competitor state, eroded vs. surviving differentiators, anti-features
- `.planning/PROJECT.md`, `project-docs/01-project-management.md` — the user's own stated risks, extended here

**Explicitly UNVERIFIED (must be resolved by Phase-0 spikes):**
- Chatterbox intra-sentence code-switching behavior
- Chatterbox Hebrew output quality
- Chatterbox realtime feasibility on Pi-class / CPU-only hardware
- Ollama token counts surfacing non-`None` through LangChain callbacks
- MCP tool args/results surfacing through `langchain-mcp-adapters` callbacks
- Current best-in-class local model for tool-calling reliability

---
*Pitfalls research for: local-first LLM-native personal voice assistant (framework + appliance + control panel), solo-maintained*
*Researched: 2026-07-13 / Written: 2026-07-18*
