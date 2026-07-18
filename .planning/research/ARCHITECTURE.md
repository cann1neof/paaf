# Architecture Research

**Domain:** Local-first streaming LLM voice assistant — Python framework (2 modules) + embedded device process + Electron control panel
**Researched:** 2026-07-13
**Confidence:** HIGH on the realtime pipeline (cross-verified against Pipecat + LiveKit Agents). MEDIUM on hot-reload, skills loading, packaging (design synthesis grounded in cited patterns, not a single citable reference implementation).

---

## Verdict on the Sketched Architecture

The sketch in `project-docs/02-core-software.md` is **directionally right and structurally incomplete**. It gets the big call right (build on an existing agent framework; keep its types out of the public API; two independent modules) and it correctly identifies sentence-streaming TTS as the latency make-or-break.

It has **one structural omission that will cost weeks if not fixed now**, plus six underspecifications that each map to a real, predictable bug.

### Defect 1 — THE BIG ONE: there is no component that owns the realtime loop

The sketch says *"the embedded app wires them"* and treats the mic→wake→STT→LLM→TTS→speaker loop as glue.

**It is not glue. It is the hardest component in the system.** Both reference implementations name it and give it a package:

| System | The thing the sketch calls "wiring" |
|---|---|
| Pipecat | `Pipeline` — a linked graph of `FrameProcessor`s, each with its own asyncio task and a `FrameProcessorQueue` (an `asyncio.PriorityQueue` that lets `SystemFrame`s, including interruption, preempt queued audio and text) |
| LiveKit Agents | `AgentSession` — the orchestrator that unified their older `VoicePipelineAgent` + `MultimodalAgent`; it owns streaming, turn detection, and interruption |

Neither treats it as app glue. Both treat it as *the* framework primitive.

**Fix:** add a third framework package — **`paaf-session`** — that depends on `paaf-llm` and `paaf-voice`, while neither depends on the other. This is the *only* way to satisfy the "Module 1 and Module 2 know nothing about each other" rule while still shipping barge-in and streaming TTS (see Defect 3). Everything below assumes this component exists.

### Defect 2 — The diagram contradicts the decoupling rule

The picture draws `mic ─► wake word ─► [FRAMEWORK: Module 1 / LangChain / Module 2] ─► spk`, i.e. one box with data flowing *through* both modules in series, with LangChain sitting between them. But the prose says LangChain is a Module-1 implementation detail and the modules know nothing about each other. The picture also puts wake word *outside* the framework while the prose puts it *inside* Module 2.

Both modules are **libraries the session calls**, not stages in a wire. Redraw before anyone reads it as a spec.

### Defect 3 — Barge-in is listed as a Module-2 feature. It cannot be one.

The sketch lists barge-in under Module 2 ("Supporting pieces inside the module: VAD, wake word, barge-in"). But barge-in is a **cross-cutting cancellation protocol**:

> LiveKit: "when VAD fires on the user's track while the agent is speaking, TTS is cancelled, **the interrupted LLM turn is rolled back**, and the user's new input is processed."

That rollback is the killer. To be correct, barge-in must truncate the assistant's conversation history to **what was actually spoken out of the speaker**, not what the LLM generated. That requires simultaneously cancelling an LLM stream and reaching into the LLM's turn history — which Module 2, by the project's own rule, knows nothing about.

**So the project's own decoupling rule *forces* barge-in up into `paaf-session`.** This is a strong argument, not a nitpick: the sketch's module list is internally inconsistent, and the resolution is the missing orchestrator.

### Defect 4 — AEC has no home, and the sketch's hardware stance guarantees it will bite

"Mic/speaker are whatever the user plugs in" + barge-in = the assistant hears its own voice, VAD fires on it, playback kills itself, or the wake word self-triggers.

Pipecat **does not implement AEC** — it delegates to the transport (Daily does AEC at the media-server level). LiveKit does the same (WebRTC gives it AEC for free). **PAAF has no media server and no WebRTC transport, so PAAF must own AEC.** No cited reference implementation solves this for you. This is the single most under-appreciated risk in the doc. Design below.

### Defect 5 — The behaviors executor and the reply will fight over the speaker

`long_request: after 6s → say: "Still working on it…"` and the first reply sentence can become ready in the same 100ms window. The sketch has no arbitration. You will ship an assistant that talks over itself.

**Fix:** a priority-laned `AudioOutputBus` (design below). Cheap to build, impossible to retrofit gracefully.

### Defect 6 — "Change the YAML, restart nothing" is under-scoped as a Phase-1 exit criterion

Not all config is equally reloadable. An audio device change or a 4GB model swap is not the same operation as a persona edit. Shipping this criterion as written means either lying about it or blocking the process for 30s on a model load. **Split config keys into hot / warm / cold / restart-only tiers** (table below) and scope the exit criterion to hot+warm.

### Defect 7 — "One YAML tree, the API edits it" is a lost-update and corruption hazard

Two desktop clients, or one client plus a hand edit, and you have silent overwrite. There is no revision, no atomic write, no conflict signal. And "secrets in an encrypted file" contradicts "config is one YAML tree" — reconcile explicitly.

---

## Standard Architecture

### System Overview

```
┌──────────────────────── THE DEVICE (one Linux process) ───────────────────────┐
│                                                                               │
│  ┌──────────────────────── app-embedded ─────────────────────────────────┐   │
│  │  FastAPI: REST (config/skills) + WS (state, logs, chat, PTT)          │   │
│  │  mDNS advertise · PIN pairing · LAN-only guard · systemd · GPIO shim  │   │
│  └────────────┬──────────────────────────────────────▲───────────────────┘   │
│               │ owns ConfigStore, drives reload       │ state snapshot+deltas │
│  ┌────────────▼──────────────────────────────────────┴───────────────────┐   │
│  │                    paaf-session  ◄── THE MISSING COMPONENT            │   │
│  │  TurnStateMachine  ·  AudioOutputBus (priority lanes)                 │   │
│  │  BargeInController ·  BehaviorsExecutor  ·  cancellation scopes       │   │
│  │  the ONLY place that knows LLM tokens become TTS speech               │   │
│  └──────┬─────────────────────────────────────────────────────┬──────────┘   │
│         │ calls                                       calls   │              │
│  ┌──────▼───────────────────────┐        ┌────────────────────▼──────────┐   │
│  │  paaf-llm    (Module 1)      │        │  paaf-voice  (Module 2)       │   │
│  │  ── PUBLIC PORTS ──          │        │  ── PUBLIC PORTS ──           │   │
│  │  Agent.stream() -> Events    │        │  WakeWord · VAD               │   │
│  │  ModelProfile · Fallbacks    │        │  STT: audio -> transcripts    │   │
│  │  ToolRegistry (+tiers)       │        │  TTS: tokens -> audio         │   │
│  │  Persona (verbatim)          │        │  SentenceAggregator           │   │
│  │  SkillLoader · MCP           │        │  AudioSource / AudioSink      │   │
│  │  ── ADAPTERS (private) ──    │        │  ── ENGINES (private) ──      │   │
│  │  langgraph/ │ fake/          │        │  whisper│piper│oww│silero│    │
│  │  ↑ ONLY place langchain      │        │  remote/ (wyoming/http)       │   │
│  │    is importable (CI-gated)  │        │  KNOWS NOTHING ABOUT LLMs     │   │
│  └──────┬───────────────────────┘        └───────────────────────────────┘   │
│         │                                                                     │
│  ┌──────▼────────────┐   ┌──────────────────────────────────────────────┐    │
│  │ paaf-trace        │   │ paaf-core                                    │    │
│  │ SQLite (WAL)      │   │ ConfigStore[T] · atomic write · revision     │    │
│  │ queue → 1 writer  │   │ SecretStore (encrypted) · LAN/offline guard  │    │
│  │ NEVER on hot path │   │ knows nothing about llm OR voice             │    │
│  └───────────────────┘   └──────────────────────────────────────────────┘    │
└───────────────────────────────────────▲───────────────────────────────────────┘
                       LAN only · bearer token · mDNS _paaf._tcp
                                        │
                          ┌─────────────┴──────────────┐
                          │  app-desktop (Electron)     │
                          │  device = source of truth    │
                          │  holds only: device tokens   │
                          └──────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `paaf-core` | Config file IO (validate → atomic write → revision), secret store, LAN/offline validators, shared errors. **Knows nothing about LLMs or voice.** | Pydantic v2 models, `ConfigStore[T]` generic, tmp+fsync+rename writes |
| `paaf-llm` (Module 1) | Model profiles, fallback chains, routing rules, persona composition, tool registry + permission tiers, skill loader, MCP client, declarative behaviors *table*. **Pure text. Zero audio. Zero framework types in the public API.** | Ports (Protocols) + a `langgraph/` adapter + a `fake/` adapter |
| `paaf-voice` (Module 2) | Wake word, VAD/end-of-speech, STT, TTS, **sentence aggregation**, audio device I/O, AEC filter hook. **Zero knowledge of LLMs, tools, agents.** | Engine Protocols + local engines + `remote/` (HTTP/Wyoming) engines |
| **`paaf-session`** | The realtime loop. Turn state machine, cancellation scopes, barge-in, audio output arbitration, behaviors *execution*. **The only component that knows a token stream becomes speech.** | `anyio`/`asyncio.TaskGroup` structured concurrency over bounded queues |
| `paaf-trace` | SQLite trace store. Runs, spans, LLM calls, tool calls, composed prompts, **time-to-first-audio**. | WAL + in-memory queue + one dedicated writer task |
| `app-embedded` | FastAPI REST+WS, mDNS, PIN pairing, offline enforcement, reload driver, systemd unit, optional GPIO. **Owns the config lifecycle; does NOT own the pipeline.** | FastAPI + `python-zeroconf` |
| `app-desktop` | Control panel. Renders device state. Stores only pairing tokens. | Electron + TS + React |

---

## The Realtime Voice Pipeline

### How the reference implementations do it

Verified (MEDIUM-HIGH, two independent sources agreeing):

- **Pipecat** = typed frames flowing through a linked list of `FrameProcessor`s. Each processor has its own asyncio task and a `FrameProcessorQueue` — an `asyncio.PriorityQueue` that separates `SystemFrame`s (Start/End/Cancel/**Interruption**) from `DataFrame`s and `ControlFrame`s, so interruption preempts a queue full of audio. Frames flow DOWNSTREAM and UPSTREAM via `push_frame()`. Lifecycle per processor: `start(StartFrame)` → `process_frame()` → `stop(EndFrame)` / `cancel(CancelFrame)` → `cleanup()`.
- **LiveKit** = `AgentSession` with pluggable STT/LLM/TTS. **Streaming pipeline overlaps stages**: STT emits partials, LLM streams tokens into TTS, TTS emits audio before the reply is finished. A *sequential* pipeline (wait for each stage) yields 2–4s and "makes conversation feel unnatural"; a streaming one gets under 1s end-to-end.

### Recommended concurrency model — steal Pipecat's *shape*, not Pipecat

**Long-lived asyncio tasks connected by BOUNDED queues, wrapped in structured concurrency, with control signals out-of-band.**

```python
# The turn is a structured-concurrency scope. Cancel the scope = the whole turn dies.
async def run_turn(self, user_audio: AsyncIterator[AudioChunk]) -> None:
    async with anyio.create_task_group() as tg:          # or asyncio.TaskGroup (3.11+)
        self._turn_scope = tg.cancel_scope
        tokens  = stream_queue(maxsize=64)               # LLM TextDelta -> aggregator
        audio   = stream_queue(maxsize=8)                # TTS chunks   -> output bus
        tg.start_soon(self._run_llm, user_text, tokens)
        tg.start_soon(self._run_tts, tokens, audio)      # aggregation lives INSIDE voice
        tg.start_soon(self._run_playback, audio)
        tg.start_soon(self._watch_for_barge_in)          # cancels the scope
```

Design calls, with reasons:

1. **Bounded queues, always.** Unbounded queues are how you get a memory leak *and* unbounded latency: a fast LLM will run 40 sentences ahead of a slow TTS, and a barge-in then has to flush 40 sentences. `maxsize` gives you backpressure for free.
2. **Do NOT copy Pipecat's PriorityQueue for control frames.** Pipecat needs it because it supports *arbitrary user-authored pipelines*. PAAF has exactly one pipeline shape. Use structured concurrency instead: an `anyio.CancelScope` per turn plus an `asyncio.Event` for interrupt. It is dramatically easier to reason about and it is *impossible to leak a task*. This is a place where PAAF should be simpler than its reference.
3. **Never run inference on the event loop.** Whisper, Piper, openWakeWord, Silero, and a local llama all block. `await anyio.to_thread.run_sync(...)` with a **per-engine bounded limiter** (one Whisper at a time; two concurrent Whispers on a Pi 5 will thrash and blow your latency budget). Most native runtimes (ctranslate2, onnxruntime, llama.cpp bindings) release the GIL, so threads are correct here; pure-Python CPU work needs a process pool.
4. **The audio device callback is a C thread.** PortAudio/`sounddevice` calls you back off-loop. In that callback: **no `await`, no allocation, no asyncio object access.** Write into a preallocated ring buffer; signal the loop with `loop.call_soon_threadsafe`. Violating this is the classic cause of buffer underruns (clicks, dropouts).
5. **`AudioSink` must expose a playhead.** Barge-in truncation is only correct if you know how many milliseconds have actually left the DAC. The sketch's `AudioSink` has no such concept, and without it you will commit three sentences to conversation history that the user never heard. **This is a concrete missing API.**

### Latency budget (target: ≤1.5s time-to-first-audio)

| Stage | Realistic cost | Lever |
|---|---|---|
| Wake word detect | 50–150 ms | small |
| **End-of-speech decision** | **300–700 ms** (VAD hangover) | **BIGGEST controllable chunk.** LiveKit ships a ~135M SmolLM-v2 fine-tune that runs locally and predicts "is this a finished thought", combined with acoustic VAD. Pure-VAD hangover is where most of your budget silently goes. |
| STT final | 200–500 ms (faster-whisper small, ~3s utterance) | streaming partials hide most of it |
| **LLM TTFT** | **300–800 ms** cloud; **500–1500 ms** local 7B on CPU | **Second-biggest lever.** This is the real justification for the routing rules feature. |
| First sentence completes | +100–400 ms of generation past TTFT | short first sentence |
| TTS TTFB (Piper, short sentence) | 50–150 ms | small |
| Buffer → DAC | 20–100 ms | small |
| **Total** | **~1.0 – 2.5 s** | |

Three roadmap consequences:

- **TTFA must be measured from the LLM phase, not the voice phase.** With a fake TTS that just timestamps its first chunk, you can measure TTFA before any audio hardware exists. `paaf-trace` must therefore precede `paaf-voice` in build order.
- The "first sentence" trick only pays if the first sentence is *short*. A legitimate, honest way to get this: a **default-on, visible, removable persona fragment** ("open with a brief first sentence"). PROJECT.md forbids hidden instructions — so it must be visible in the composed-prompt viewer and deletable. That constraint makes it a *feature* rather than a cheat.
- Optimizing TTS is mostly wasted effort. Optimize end-of-speech and TTFT.

### Sentence chunking for TTS — where PAAF should diverge from Pipecat

Pipecat's TTS services own a pluggable text aggregator (`TextAggregationMode.SENTENCE` buffers to boundaries, costing ~200–300ms/sentence; `TOKEN` streams raw). Boundary detection uses **NLTK's `sent_tokenize`** plus a hardcoded `UNAMBIGUOUS_SENTENCE_ENDING_PUNCTUATION` set for scripts NLTK can't disambiguate (CJK, Arabic/Urdu `؟ ؛ ۔`, Devanagari `। ॥`, Thai, Khmer, Armenian, Ethiopic).

**PAAF must not use NLTK.** NLTK's punkt is per-language, requires a downloaded model, and needs to be told which language it's reading. PAAF's founding rule is **no language configuration anywhere in the pipeline**. Using NLTK would violate it, and Pipecat itself flags the weakness: *"NLTK may return a single sentence for text that's a single word. In the case of LLM tokens, it's common for text to be single words."*

**Use a rules-based Unicode terminator matcher instead — language-agnostic by construction.** English, Russian, Hebrew and Spanish all terminate with `. ! ?`, so a union set covers 100% of the user's languages, and the CJK/Arabic/Devanagari marks come free.

Aggregator spec:

```
EMIT the buffer when ANY of:
  A. it ends with a terminator from  { . ! ? … 。 ！ ？ ؟ ۔ । ॥ ։ ။ ។ }
     AND len(buffer) >= MIN_CHARS
     WHERE MIN_CHARS = 6 for the FIRST chunk of a turn   ← this is your TTFA
                       25 for every chunk after           ← this is your prosody
  B. it ends with '\n'                (list items carry no terminator)
  C. len(buffer) > 200 and it ends with a soft break { , ; : — } (model never punctuated)
  D. the turn finished  (always flush)

SUPPRESS a '.' as a terminator when it is:
  - preceded by a single capital letter        ("J. R. R.")
  - between digits                             ("3.14", "1.5s")
  - inside a URL or email                      (regex guard)
  - immediately followed by a non-space
  - part of a short abbreviation list          (English-only; accept the imperfection)

SANITIZE before handing to TTS:
  - strip markdown (** ` # > -), which TTS reads aloud as symbols
  - strip emoji, which TTS reads as "smiling face"
  - SUPPRESS code blocks entirely -> emit a behavior instead ("I've printed that for you")
```

The **asymmetric MIN_CHARS is the whole trick**: emit the first chunk aggressively (that is literally your time-to-first-audio), then relax so later sentences aren't chopped.

**Where does this live?** In `paaf-voice`, owned by the TTS service — exactly as Pipecat does it. Not in the app, not in the session. Reasons: it must know the engine's preferred chunk size; it must know whether the engine supports mid-stream continuation; and a developer using Module 2 *alone* as a voice-I/O library wants it. Public API: `TTS.speak(tokens: AsyncIterator[str])` — voice does the aggregation internally.

### Barge-in — the actual sequence

```
0. PRECONDITION: full-duplex audio. Mic capture NEVER stops, including during playback.
   The VAD runs on the AEC-CLEANED mic signal, always.

1. VAD reports SpeechStart while state == SPEAKING.

2. Debounce: require 120–250 ms of continuously voiced audio before acting.
   Without this, a cough, a door, or residual echo kills playback. Buffer that
   audio — you will need it in step 4d.

3. session.interrupt():
   a. playhead_ms = output_bus.flush_all()      # stop the DAC NOW, learn what was heard
   b. turn_scope.cancel()                       # kills LLM stream + aggregator + TTS tasks
   c. spoken = tts.spoken_text_up_to(playhead_ms)
   d. agent_turn.commit(assistant_text=spoken)  # HISTORY REFLECTS REALITY, not generation
   e. trace.record(interrupted=True, spoken_chars=len(spoken))

4. state -> LISTENING:
   the 120–250 ms of PRE-ROLL audio captured during debounce is PREPENDED to the new
   STT stream. Skip this and you clip the user's first word, every single time.
```

Step 3d is the coupling that forces `paaf-session` to exist. Step 4's pre-roll is the detail nearly everyone forgets.

Pipecat's own current behavior is an abrupt hard stop (`InterruptionFrame` → transport resets audio, TTS cancels immediately), and there is an open proposal to soften it. PAAF should ship the hard stop first — it is correct, just slightly harsh — and consider a 30–60ms fade-out later.

### AEC — where it lives (nobody solves this for you)

Pipecat and LiveKit both get AEC free from their transport (Daily's media server / WebRTC). PAAF has neither. Three tiers, in order of preference:

| Tier | Approach | Cost | Verdict |
|---|---|---|---|
| **1. Hardware DSP** | ReSpeaker mic array, or any USB conference speakerphone (Jabra/Anker class) that does AEC in firmware | $ | **Recommend as the documented reference config.** Zero code. Just say "buy a mic with AEC." |
| **2. OS layer (Linux)** | PipeWire / PulseAudio `module-echo-cancel` (webrtc-audio-processing under the hood) | zero code | **The Linux-native answer. Ship a setup snippet.** This is where the "Linux is the product" decision pays off. |
| **3. In-process** | An `AudioFilter` Protocol on the mic path: `process(mic_frame, reference_frame) -> frame`, so `speexdsp` / `webrtc-audio-processing` bindings can plug in | real work | Provide the *interface* from day one; implement it only if tiers 1–2 prove insufficient |

Tier 3 imposes a second concrete API requirement the sketch is missing: **`AudioSink` must expose a reference tap** (what was actually sent to the DAC), because AEC needs it as the reference signal.

Fallback if none of the above: **partial ducking** — drop mic gain 10–20 dB during playback. Loud intentional barge-in still fires; quiet echo doesn't. Do **not** ship full mic mute during playback ("half-duplex"): that disables barge-in entirely, which is one of the project's stated requirements.

> **Dev-harness warning, state this in the README:** barge-in over a MacBook's built-in speakers + built-in mic will be flaky, because macOS gives you no `module-echo-cancel` and the laptop has no AEC on that path. **Develop barge-in with headphones**, or with the scripted fake audio harness below. Do not burn a week thinking your state machine is broken when it's the acoustics.

### Model warm-up — four places it bites

1. **Ollama unloads models after `keep_alive` (default 5 min).** The first question after an idle period pays a multi-second model load. **This is the #1 latency surprise in local voice assistants and the sketch never mentions it.** Fix: set `keep_alive: -1` for the primary local profile, or ping it on a timer. Make it a first-class config field with a sane default, not a footnote.
2. **First-inference JIT.** onnxruntime and ctranslate2 are measurably slower on call #1. Put `async def warmup(self) -> None` on **every** engine Protocol and run all warmups concurrently at boot, before mDNS advertises and before the wake word arms.
3. **After a hot reload.** A new model profile must be *loaded and warmed before the swap*, or the first post-reload turn takes 10s. This is why config has a "warm" tier (below).
4. **Memory.** Whisper + Piper + a 7B local model will not comfortably co-reside on a Pi 5. **Architectural consequence: engines must be able to live out-of-process.** Design the engine Protocols so an implementation can be a *remote client* (`remote/http`, `remote/wyoming`) from day one. It costs nothing now and saves a rewrite when the target hardware arrives. It also buys instant compatibility with the entire Home Assistant Wyoming ecosystem (whisper/piper/openwakeword servers already exist and speak a TCP protocol) — a distribution win, and it is HA-as-a-tool, not HA-as-a-dependency.

---

## Module Boundaries — Does Streaming TTS Force Coupling?

**No. The boundary holds, and it holds cleanly.** Here is the exact argument.

The feared coupling is "the LLM's token stream must feed the TTS's text stream." That is satisfied by a **type from the standard library**:

```python
# ---------------- paaf.llm.api (Module 1) — knows NOTHING about audio ----------------
@dataclass(frozen=True) class TextDelta:        text: str
@dataclass(frozen=True) class ToolCallStarted:  name: str; args: dict; tier: PermissionTier
@dataclass(frozen=True) class ToolCallFinished: name: str; result: Any; error: str | None
@dataclass(frozen=True) class TurnFinished:     text: str; usage: Usage
AgentEvent = TextDelta | ToolCallStarted | ToolCallFinished | TurnFinished

class AgentTurn(Protocol):
    def __aiter__(self) -> AsyncIterator[AgentEvent]: ...
    def commit(self, assistant_text: str) -> None: ...   # ← the barge-in seam
    def abandon(self) -> None: ...

class Agent(Protocol):
    def turn(self, user_text: str, *, ctx: RuntimeContext) -> AsyncContextManager[AgentTurn]: ...
    def composed_prompt(self, *, ctx: RuntimeContext) -> str: ...   # verbatim, a requirement

# ---------------- paaf.voice.api (Module 2) — knows NOTHING about LLMs ---------------
class TTS(Protocol):
    def speak(self, tokens: AsyncIterator[str]) -> AsyncIterator[AudioChunk]: ...
    def spoken_text_up_to(self, playhead_ms: int) -> str: ...   # ← the barge-in seam
    async def warmup(self) -> None: ...

class STT(Protocol):
    def transcribe(self, audio: AsyncIterator[AudioChunk]) -> AsyncIterator[Transcript]: ...

class AudioSink(Protocol):
    async def write(self, chunk: AudioChunk) -> None: ...
    def playhead_ms(self) -> int: ...          # ← required for correct barge-in
    def reference_tap(self) -> AsyncIterator[AudioChunk]: ...   # ← required for AEC
    async def flush(self) -> int: ...          # stop now, return the playhead
```

**The only type that crosses the module boundary is `str`, inside an `AsyncIterator`.** Neither module imports a type from the other. `paaf-session` does the adaptation in ~5 lines:

```python
# paaf-session — the ONLY place the two worlds meet
async def _to_token_stream(turn: AgentTurn) -> AsyncIterator[str]:
    async for ev in turn:
        if isinstance(ev, TextDelta):
            yield ev.text                       # LLM events -> plain str
        elif isinstance(ev, ToolCallStarted) and ev.tier is PermissionTier.CONFIRM:
            yield from await self._confirm_out_loud(ev)

audio = tts.speak(_to_token_stream(turn))       # voice aggregates internally
```

**A developer using Module 1 alone** gets a text agent. **A developer using Module 2 alone** gets a voice-I/O library — and gets sentence-streaming TTS *for free*, because `TTS.speak()` takes any `AsyncIterator[str]`, LLM or not. That is a better standalone library than a version where the aggregator lives in the app.

**So: streaming TTS does not break the boundary. Two other things do — and both resolve to `paaf-session`:**

| Force | Why it crosses the boundary | Resolution |
|---|---|---|
| **Barge-in** | Must cancel an LLM stream *and* truncate LLM history to the spoken prefix | `AgentTurn.commit(assistant_text=...)` — the caller decides what to commit. Module 1 never learns *why* it was truncated. |
| **Behaviors** | "Say 'still working on it'" must synthesize speech *because an LLM call is slow* | The behaviors *table* is Module-1 config (declarative data). The behaviors *executor* is in session. Module 1 emits timing events; session decides to speak. |
| **`confirm` tier tools** | "Ask out loud before executing" is an LLM concept that requires a voice | Module 1 surfaces `ToolCallStarted(tier=CONFIRM)` and awaits an approval callback. Session wires that callback to TTS+STT. A text-only user wires it to stdin. |

Note what all three have in common: the cancellation/approval primitives are **`asyncio`/`anyio` stdlib types**, not PAAF types. That is what keeps the boundary from leaking.

---

## The Wrapper Boundary — Making Swappability Real

### Structure

```
packages/paaf-llm/src/paaf/llm/
├── api/          PUBLIC. Agent, ModelProfile, ToolSpec, Skill, Persona, AgentEvent.
│                 May import: paaf.core, stdlib, pydantic. NOTHING ELSE.
├── ports/        Protocols the adapters implement: AgentRuntime, ChatModel, ToolExecutor.
├── adapters/
│   ├── langgraph/   ← the ONLY directory in the repo allowed to import langchain*
│   └── fake/        ← a deterministic scripted model
├── tools/        registry, @tool decorator, MCP client, permission tiers
├── skills/       manifest, loader, permission review
└── persona/      layered composition + verbatim inspection
```

### The thing that makes it genuinely swappable rather than aspirationally so

**A CI-enforced import contract.** Discipline does not survive month four of a solo project. Add [`import-linter`](https://import-linter.readthedocs.io) with a *forbidden* contract and wire it into CI:

```toml
[[tool.importlinter.contracts]]
name    = "Agent framework never leaks into the public API"
type    = "forbidden"
source_modules    = ["paaf.llm.api", "paaf.llm.ports", "paaf.llm.tools", "paaf.llm.persona"]
forbidden_modules = ["langchain", "langchain_core", "langgraph", "pydantic_ai"]

[[tool.importlinter.contracts]]
name    = "Voice never learns about LLMs, and vice versa"
type    = "forbidden"
source_modules    = ["paaf.voice"]
forbidden_modules = ["paaf.llm"]
```

That second contract is what turns "Module 1 and Module 2 know nothing about each other" from a wish into a **build failure**. It's ~20 lines of config. Do it on day one — retrofitting it after six months of accidental imports is a miserable week.

### The second implementation, and the realistic cost

A port with one implementation is a fiction. **But the second implementation should NOT be a full Pydantic-AI adapter** — that doubles the work to prove a point.

**Write a `fake/` adapter instead.** A deterministic scripted model that replays canned token streams and tool calls. It is simultaneously:
- **the proof the port is real** (if the fake fits the port, the port isn't LangChain-shaped),
- **the CI test double** for every golden test in Module 1,
- **the thing that lets you measure TTFA before any real model exists**,
- **the thing that lets you build and test `paaf-session` with zero hardware and zero GPU.**

Realistic cost of the LangGraph adapter: **~800–1500 LOC**, concentrated in four places that the framework does not give you for free at the boundary:
1. **Streaming event normalization** — the framework's stream events → PAAF's `AgentEvent` union. The single largest and most churn-prone piece.
2. **Tool schema translation** — PAAF `ToolSpec` (name, description, JSON schema, permission tier) → the framework's tool object. Permission tier is PAAF-only and must ride alongside, never inside, the framework's schema.
3. **Fallback chains** — `.with_fallbacks()` exists in LangChain, but its failure semantics are the framework's, not yours. Wrap and normalize the errors.
4. **Callbacks → traces** — the framework's callback objects must be converted to PAAF trace records *at the adapter boundary*. Do not let a `LangChainTracer` type reach `paaf-trace`.

Two extra leak vectors to guard: **LangGraph's checkpointer/state** (if you expose "conversation memory," define your own type) and **exception types** (wrap them; a `langchain_core` exception escaping to a user is a leak).

---

## Configuration and Hot Reload

### The reload primitive: build-new + atomic-swap. Never mutate live objects.

```python
class AgentHolder:
    def __init__(self, spec: LLMConfig):
        self._agent = build(spec)                    # immutable object graph

    @property
    def current(self) -> Agent:
        return self._agent                           # readers grab a REFERENCE

    async def reload(self, new_spec: LLMConfig) -> None:
        new = await build_and_warm(new_spec)         # slow work OFF the hot path
        self._agent = new                            # atomic rebind (GIL-atomic)
```

A turn in flight took `agent = holder.current` at turn start, so it **finishes on the old graph** and the old graph is GC'd afterwards. No mid-turn persona swap, no half-configured agent. This also means the trace's `config_revision` never lies.

### Config tiers — this is the part the sketch is missing

| Tier | Keys | Reload mechanics | Time |
|---|---|---|---|
| **HOT** | persona, tools, skills (enable/disable), behaviors, permission tiers, routing rules, model profile *selection* | Rebuild the agent graph, swap at next turn boundary | <100 ms |
| **WARM** | model *weights* (new Ollama model), STT engine, TTS engine/voice | Build new → `warmup()` → swap at next turn boundary. **Old one keeps serving until the new one is ready.** | 1–30 s, invisible |
| **COLD** | audio device, sample rate, wake-word engine swap | Tear down and rebuild the *audio task group* while the process lives. Requires the pipeline to be a supervised, restartable task group. Assistant is deaf for ~1–2 s. | 1–2 s, visible |
| **RESTART** | API bind address/port, offline-mode toggle (it gates *startup* validation) | Process restart. **Be honest that this tier exists.** | seconds |

**Scope the Phase-1 exit criterion to HOT+WARM.** The desktop app should show, per field, which tier it is ("changing this briefly interrupts listening"). Claiming "restart nothing" for every key is a promise you'd have to break.

### What breaks if a reload lands mid-conversation

Everything, if you apply it immediately. So don't:

```python
async def request_reload(self, spec):
    self._pending = spec
    if self.state is SessionState.IDLE:
        await self._apply()          # apply now
    # else: apply on the next IDLE transition
```

Apply at the **turn boundary**, never mid-turn. Applying mid-turn means the persona changes mid-reply, the trace's `config_revision` becomes a lie, and a tool that was just revoked is already in flight. A pending reload should be visible in the WS state (`{"reload_pending": true}`) so the desktop can show "will apply after this reply."

**Skills are the one genuinely hard case.** Enabling/disabling an *installed* skill is HOT. *Installing* a new skill means `uv pip install git+<url>` into the live venv, which can (a) pull new dependencies, (b) conflict with existing ones, (c) require a native extension. Honest policy: **install → resolve → if resolution fails, refuse loudly and change nothing; if it succeeds, import and reload.** A skill with a native extension may still require a process restart; detect and say so rather than crashing.

### Config file safety — fix Defect 7

```
GET /api/config          -> 200 {revision: 42, config: {...}}   ETag: "42"
PUT /api/config          If-Match: "42"
                         -> 200 {revision: 43}
                         -> 409 {revision: 47, config: {...}}   "the device changed under you"
```

Write path: **validate (Pydantic) → serialize → write tmp → fsync → rename → bump revision → reload.** The rename is atomic on POSIX; a power cut can never leave a half-written config. If validation fails, nothing is written and the running config is untouched.

**Secrets do not live in the YAML.** The YAML holds `api_key: ${secret:anthropic}`; the secret store is a separate encrypted file. The API is **write-only** for secrets and returns `"set" | "unset"`, never the value. Never log them; the trace store must redact by key name at the *record* boundary, not at the *render* boundary.

---

## The Local API and the Desktop App

### Shape

| Concern | Recommendation |
|---|---|
| **Discovery** | `python-zeroconf`, service type `_paaf._tcp.local.`, TXT record: `{name, api_version, paired}` |
| **Pairing** | `POST /api/pair` → device displays a 6-digit PIN (console + status LED blink + WS broadcast); client posts the PIN; device returns a bearer token. Rate-limit to ~5 attempts, then a 60s lockout — a 6-digit PIN on a LAN is fine *with* a lockout and worthless without one. |
| **Token storage** | Electron `safeStorage` → OS keychain. Never `localStorage`. |
| **REST** | Settings, skills, models, secrets. ETag + `If-Match` on every mutation. |
| **WebSocket** | On connect: **a full state snapshot**. Then deltas. Every message carries a monotonic `seq` and the current `config_revision`. |
| **WS auth** | Browsers can't set WS headers, but Electron can. Simplest robust option: `POST /api/ws-ticket` (bearer) → short-lived single-use ticket → `GET /ws?ticket=...`. Avoids putting the long-lived token in a URL. |
| **LAN-only** | Bind `0.0.0.0` **and** run middleware rejecting any peer address that isn't RFC1918 / link-local / loopback. Binding to one interface is more fragile on multi-homed hosts than checking the peer. Also validate `Origin`. |
| **Offline mode** | This is **config validation, not a firewall**. At agent-build time, refuse any model/MCP/tool endpoint whose host doesn't resolve to a private address. Enforce it in the **port layer**, so every adapter gets it free and no adapter can forget. The `/api/privacy/connections` endpoint (`psutil.net_connections`) is the honest, cheap "verify" helper — and `tcpdump` remains the real proof, as PROJECT.md says. |

### State-sync pitfalls (device is truth, desktop must show live state)

1. **Optimistic UI is the #1 mistake.** The desktop must render *device* state, never its own prediction. Every mutation returns the new revision; the UI updates when the corresponding WS delta arrives. A toggle that flips instantly and then flips back is worse than one that takes 80ms.
2. **Reconnect must re-snapshot.** Never assume continuity across a dropped socket. Sequence-number every WS message; on a gap, force a full re-snapshot. Devices sleep, Wi-Fi drops, laptops close.
3. **The log firehose will kill the WebSocket.** Live logs are **best-effort**: ring buffer, coalesce, and **drop** under backpressure — never buffer unboundedly, or a paused Electron renderer will OOM the *device*. The durable record is `paaf-trace`; the WS is a tail, not a transport.
4. **Two clients editing** → 409 with the current revision → "the device changed; reload?" **Never attempt a bidirectional merge** of a config tree. There is no correct merge for a persona edit.
5. **Never return secrets over the API**, even to a paired client.
6. **The chat/PTT channel must be a distinct WS message class** with its own backpressure. It must not be starved behind a log burst — that would make the "test without speaking" panel feel broken exactly when it matters.

---

## Skills and Tools

### Loading: entry points, not path imports

**Skills are Python packages, installed into the app venv, discovered via `importlib.metadata.entry_points(group="paaf.skills")`.**

```toml
# a skill's own pyproject.toml
[project.entry-points."paaf.skills"]
weather = "paaf_skill_weather:SKILL"
```

`paaf skill add <git-url>` → `uv pip install git+<url>` → re-scan entry points → validate manifest → show permissions → user approves → reload.

Why entry points over `importlib.import_module` on a path:
- It is the standard mechanism (Python Packaging User Guide's documented approach).
- **You get dependency resolution for free.** A skill needs `httpx`? Declare it. Path-imported skills have no dependency story and you *will* reinvent one badly.
- Conflicts fail at install, loudly, changing nothing — rather than corrupting a running process.

Cost: a skill can, in principle, force a dependency downgrade. `uv`'s resolver refusing to install is the correct outcome, not a bug. Surface the resolver error verbatim to the user.

### Sandboxing: there is none, and the docs must say so in plain language

This is the most important honesty item in the whole architecture.

| Thing | What it actually is |
|---|---|
| Skill manifest permissions | **Reviewed at install, displayed, enforced at the tool-invocation layer.** They stop the *model* from calling a tool. |
| Permission tiers (`observe`/`act`/`confirm`) | **An LLM behavior control. NOT a security boundary.** They constrain what the model may invoke — not what the skill's Python code may do. |
| A skill's Python code | **Arbitrary code with full process privileges.** Filesystem, network, your API keys, everything. Exactly equivalent to `pip install`. |

Neither `entry_points()` nor `import_module()` sandboxes anything, and the official Python packaging guidance is blunt: never import from untrusted sources. Real isolation requires a separate process or container, which is a *different architecture*.

**So say it, in the README and in the install dialog:**

> Installing a skill runs its code with the same privileges as PAAF itself. Permission tiers control what the *assistant* is allowed to do, not what a *skill's code* can do. Install skills you trust, the same way you'd `pip install` a package.

Three things make this defensible rather than negligent:

1. **MCP is the actual isolation story.** MCP servers are separate processes by design. **Recommend MCP as the preferred extension path for anything the user hasn't audited**, and say so in the docs. This turns a weakness into a design position — and it's true.
2. **systemd hardening protects the host.** `ProtectSystem=strict`, `ProtectHome=`, `NoNewPrivileges=`, `PrivateTmp=`, a tight `DeviceAllow=` for the audio device, and a dedicated unprivileged user. This does not protect PAAF from a malicious skill; it protects *the machine* from PAAF. That's the realistic 80% and it costs one unit file.
3. **Permission review at install** is a real, useful UX even though it's not a sandbox — it makes intent visible.

Anything less honest than this gets torn apart on r/selfhosted, deservedly. Being first to say it is a credibility asset.

---

## Observability

### Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA wal_autocheckpoint = 0;     -- checkpoint explicitly, when IDLE

CREATE TABLE run (
  id INTEGER PRIMARY KEY, started_at_us INTEGER, ended_at_us INTEGER,
  trigger TEXT,               -- wake | ptt | chat | schedule
  config_revision INTEGER,    -- the audit trail: which config produced this
  interrupted INTEGER DEFAULT 0,
  -- the tracked number, promoted to a first-class column:
  time_to_first_audio_us INTEGER,
  wake_to_endpoint_us INTEGER, endpoint_to_stt_final_us INTEGER,
  stt_final_to_first_token_us INTEGER, first_token_to_first_audio_us INTEGER
);
CREATE TABLE span (                       -- narrow + hot: keep it small
  id INTEGER PRIMARY KEY, run_id INTEGER, parent_id INTEGER,
  kind TEXT,                              -- llm | tool | stt | tts | vad | wake | behavior
  name TEXT, started_at_us INTEGER, ended_at_us INTEGER,
  status TEXT, error TEXT
);
CREATE TABLE llm_call (                   -- wide + cold: separate table
  span_id INTEGER PRIMARY KEY, model_profile TEXT, provider TEXT, model TEXT,
  was_fallback INTEGER, prompt_json TEXT, response_text TEXT,
  prompt_tokens INTEGER, completion_tokens INTEGER, ttft_us INTEGER
);
CREATE TABLE tool_call (
  span_id INTEGER PRIMARY KEY, tool_name TEXT, source TEXT,   -- builtin|skill|mcp
  permission_tier TEXT, args_json TEXT, result_json TEXT, approved INTEGER
);
CREATE TABLE composed_prompt (            -- "inspectable verbatim" is a REQUIREMENT
  run_id INTEGER PRIMARY KEY, text TEXT
);
CREATE INDEX ix_span_run ON span(run_id);
CREATE INDEX ix_run_started ON run(started_at_us DESC);
```

**Design notes.** `span` is kept narrow so the hot table stays cache-friendly; prompts/responses (which can be tens of KB) live in separate tables. `time_to_first_audio_us` is a **column, not a derived query**, because PROJECT.md calls it "a tracked number" — the trace store is the thing that tracks it, so it must be queryable in one hop. `config_revision` on every run is what makes "why did it answer that way in March" answerable.

### Write path — never touch SQLite on the hot path

```
adapter callback / session event
        │  (a dataclass, ~microseconds)
        ▼
 asyncio.Queue(maxsize=4096)          ← bounded; drop-oldest for high-frequency
        │                                metrics, block-and-log for run/llm/tool
        ▼
 ONE dedicated writer task
        │  batches every 100 ms OR 64 records, whichever first
        ▼
 one BEGIN … COMMIT per batch
```

WAL means readers (the desktop's trace viewer) never block the writer and the writer never blocks readers — p99 write latency drops 30–60% versus rollback-journal mode. A **single dedicated writer draining an in-memory queue** is the canonical pattern; producers enqueue and return immediately.

**Disable autocheckpoint** (`wal_autocheckpoint = 0`) and checkpoint explicitly from the writer task when the session is IDLE. The default (every 1000 pages, opportunistically, on whichever connection notices) will fire *mid-conversation* and put a fsync spike squarely in your latency budget. This is a small, easily-missed detail with a direct TTFA cost.

Secrets must be redacted **at the record boundary**, not at the render boundary — otherwise the API key is on disk forever and only hidden in the UI.

Retention: cap by age and row count; `VACUUM` never runs on the hot path (use `auto_vacuum=INCREMENTAL` and step it when idle).

---

## Recommended Project Structure

```
paaf/
├── pyproject.toml               # uv WORKSPACE root — not published
├── uv.lock                      # ONE lockfile for the whole repo
├── packages/
│   ├── paaf-core/               # pip: paaf-core   — config, secrets, guards
│   ├── paaf-llm/                # pip: paaf-llm    ← THE STANDALONE ARTIFACT
│   │   └── src/paaf/llm/{api,ports,adapters/{langgraph,fake},tools,skills,persona}/
│   ├── paaf-voice/              # pip: paaf-voice
│   │   └── src/paaf/voice/
│   │       ├── api/             # STT, TTS, WakeWord, VAD, AudioSource, AudioSink
│   │       ├── text/            # the multilingual sentence aggregator
│   │       ├── engines/         # faster_whisper/ piper/ openwakeword/ silero/ remote/
│   │       ├── audio/           # device io, ring buffer, resample, AudioFilter (AEC)
│   │       └── testing/         # FileAudioSource, ScriptedAudioSource, FakeAudioSink
│   ├── paaf-session/            # pip: paaf-session ← THE MISSING COMPONENT
│   │   └── src/paaf/session/{pipeline,turn,barge_in,output_bus,behaviors}.py
│   └── paaf-trace/              # pip: paaf-trace
├── apps/
│   ├── embedded/                # FastAPI + mDNS + pairing + systemd + GPIO shim
│   │                            #   (AGPL candidate; NOT published to PyPI)
│   └── desktop/                 # Electron + TS + React
└── docs/                        # MkDocs
```

### Structure rationale

- **`paaf-session` is the fifth package and it's the one the sketch doesn't have.** It depends on `paaf-llm` + `paaf-voice`; neither depends on the other. This is precisely how you keep the decoupling rule *and* get streaming barge-in.
- **The install story maps to audiences:** `pip install paaf-llm` = a text-agent construction kit (the artifact you publish at end of Phase 1, which is the stated burnout mitigation). `pip install paaf-voice` = a voice-I/O library. `pip install paaf` = the umbrella that pulls all five and gives you an assistant.
- **`paaf-core` must not know about `llm` or `voice`.** It provides a generic `ConfigStore[T]`; each module owns its own Pydantic config section; the *app* composes `AppConfig = {llm, voice, session, api}`. If `paaf-core` ever imports either module, the boundary is dead.
- **`paaf-voice/testing/` is a first-class shipped subpackage**, not test-only code. It is what makes hardware-free development possible (below) — and it's what a downstream developer needs to test *their* voice app too.

### Python packaging for the monorepo

**Use `uv` workspaces.** One `uv.lock` and one `.venv` at the root; each member has its own `pyproject.toml`, version, and release cadence. Members depend on each other via `[tool.uv.sources]` with `workspace = true`, which resolves locally in dev but **becomes an ordinary PyPI dependency in the built wheel** — so `paaf-llm` is genuinely `pip install`-able standalone by a stranger who has never seen the monorepo. That is exactly the property PROJECT.md demands.

```toml
# packages/paaf-session/pyproject.toml
[project]
dependencies = ["paaf-llm>=0.1", "paaf-voice>=0.1", "anyio>=4"]
[tool.uv.sources]
paaf-llm   = { workspace = true }     # dev: local  ·  wheel: PyPI
paaf-voice = { workspace = true }
```

`uv build --package paaf-llm` builds one member. Per-package release automation exists (`python-semantic-release`, `uv-release-monorepo`). **Verify the standalone install in CI**: a job that `pip install`s the built `paaf-llm` wheel into a *clean* venv with no workspace present and runs the smoke tests. Without that job, "independently installable" rots within two months.

`apps/embedded` is a workspace member but is **not published to PyPI** (`[tool.uv] package = false` / no publish job) — it ships as a systemd service and, per PROJECT.md, may be AGPL while the framework packages are Apache-2.0. Keeping the license split at the *package* boundary is another reason `paaf-session` should sit in `packages/` (Apache-2.0, reusable) rather than inside the app.

---

## Data Flow

### Happy path (voice turn)

```
mic (C thread) ──ring buffer──► [AEC filter] ──► WakeWord ──► VAD/endpointer
                                     │                              │ SpeechEnd
                                     │                              ▼
                                     │                      STT ──partials──► (WS to desktop)
                                     │                       │ final transcript
                                     │                       ▼
                                     │           ┌── paaf-session.run_turn ───────────────┐
                                     │           │  agent.turn(text) ─► AgentEvent stream │
                                     │           │        │ TextDelta(str)                │
                                     │           │        ▼                               │
                                     │           │  tts.speak(AsyncIterator[str])         │
                                     │           │        │  (voice aggregates sentences) │
                                     │           │        ▼  AudioChunk                   │
                                     │           │  AudioOutputBus (priority lanes)       │
                                     │           └────────┬───────────────────────────────┘
                                     │                    ▼
                                     └──reference tap──► AudioSink ──► speaker
                                        (feeds AEC)       playhead_ms ─┘
```

The **reference tap → AEC** loop is what makes the mic path safe during playback; it's the arrow the sketch is missing.

### Audio output bus — priority lanes (fixes Defect 5)

Speaker output is a single scarce resource. Model it explicitly:

| Lane | Content | Rule |
|---|---|---|
| 0 | earcons (`on_wake` chime, error tone) | preempts everything, always short |
| 1 | **reply speech** | **preempts lane 2** — if a reply sentence is ready, the filler stops mid-word |
| 2 | behavior speech ("Still working on it…") | yields to lane 1; only speaks if lane 1 is empty |
| 3 | ambient / thinking loop | ducked −18 dB under any other lane; loops until cancelled |

`barge_in()` → `flush_all()` → every lane cleared, playhead returned. Without this arbiter, the behaviors executor and the reply talk over each other — a guaranteed bug given the sketch's own `after: 6s → say:` example.

### Config mutation flow

```
Desktop PUT /api/config (If-Match: 42)
  → Pydantic validate      (reject → 422, nothing written)
  → offline-mode guard     (reject non-LAN endpoints if enabled)
  → write tmp + fsync + rename       (atomic)
  → revision 42 → 43
  → session.request_reload(spec)
        → IDLE?  build_and_warm → atomic swap
        → BUSY?  queue as pending; apply at the next turn boundary
  → WS broadcast {seq, revision: 43, reload_pending: bool}
  → 200 {revision: 43}
```

---

## Build Order (dependency-ordered — this is the phase sequence)

Legend: **[NO-HW]** = fully buildable and CI-testable on the Mac with no audio hardware. **[MIC]** = needs a mic/speaker (a Mac + headphones suffices). **[TARGET]** = needs the real Linux device.

| # | Component | Depends on | HW | Notes |
|---|---|---|---|---|
| 0 | Repo skeleton: uv workspace, CI, **import-linter contracts**, DECISIONS.md, licenses | — | **NO-HW** | The import contracts must land here, not later. |
| 1 | **Spike A**: agent framework bake-off (LangGraph vs Pydantic AI) — throwaway, judged against the `ports/` sketch | 0 | **NO-HW** | The question isn't "which is nicer," it's "which is easier to hide behind a port." |
| 1b | **Spike B**: latency round-trip (whisper + piper) on the Mac | 0 | **NO-HW** (WAV in, WAV out) | Can be done entirely with files — no mic needed. |
| 2 | `paaf-core`: config schema, validate → atomic write → revision, secret store, LAN/offline guards | 0 | **NO-HW** | Everything depends on this. |
| 3 | `paaf-trace`: SQLite WAL + queue + single writer + schema | 2 | **NO-HW** | **Must precede voice.** It's how you measure TTFA, and TTFA is measurable with a fake TTS. |
| 4 | `paaf-llm` ports + **`fake/` adapter** | 2, 3 | **NO-HW** | Write the fake *first*. It defines the port and unlocks everything downstream. |
| 5 | `paaf-llm` `langgraph/` adapter: model profiles, fallback chains, routing rules | 4 | **NO-HW** | |
| 6 | `paaf-llm`: persona composition + verbatim inspection | 4 | **NO-HW** | |
| 7 | `paaf-llm`: tool registry, `@tool` decorator, permission tiers, MCP client | 4 | **NO-HW** | |
| 8 | `paaf-llm`: skill manifest + entry-point loader + permission review | 7 | **NO-HW** | |
| 9 | CLI `paaf chat` — proves Module 1 standalone | 4–8 | **NO-HW** | **Ship `paaf-llm` to PyPI here.** This is the "publish at end of Phase 1" burnout mitigation, and it's real. |
| 10 | `paaf-voice`: engine Protocols + **`testing/` fakes** + audio types + **sentence aggregator** | 2 | **NO-HW** | The aggregator is pure string logic — fully unit-testable, including all four languages. |
| 11 | `paaf-voice`: STT/TTS/WakeWord/VAD engines behind the Protocols | 10 | **NO-HW** (WAV fixtures → golden transcripts) | ~80% of Module 2 needs no microphone. |
| 12 | `paaf-voice`: live device I/O (`sounddevice`), ring buffer, AEC `AudioFilter` hook, reference tap | 11 | **MIC** | Thin (~200 LOC) — that's the point of the Protocol. |
| 13 | **`paaf-session`**: turn state machine, cancellation scopes, `AudioOutputBus`, **barge-in**, behaviors executor | 4, 10, 3 | **NO-HW** ⭐ | **See below — this is the most important finding in the build order.** |
| 14 | `app-embedded`: FastAPI REST+WS, mDNS, PIN pairing, offline enforcement, reload driver | 2, 13 | **NO-HW** | GPIO is a no-op impl behind a Protocol. |
| 15 | Real device bring-up: systemd unit + hardening, `tcpdump` verification, TTFA on target | 12, 14 | **TARGET** | |
| 16 | `app-desktop`: Electron, discovery, pairing, the eight pages | 14 | **NO-HW** | Develop against the device running on the Mac. |
| 17 | Reference hardware build | 15 | **TARGET** | Deferred per PROJECT.md. |

### ⭐ The build-order finding that matters most

**You can build and test the entire barge-in state machine on a Mac with no microphone.**

`paaf-session` depends on the *Protocols* of both modules, not their implementations. So with `paaf-voice/testing/` you get:

- `ScriptedAudioSource` — emits a WAV of speech starting at t = 1.2 s, i.e. *while TTS is playing*.
- `FakeAudioSink` — accepts chunks, advances a virtual playhead in simulated realtime, reports `playhead_ms`.
- `FakeSTT` / `FakeTTS` — deterministic, instant, with configurable latency.
- `paaf.llm.adapters.fake` — a scripted model with a configurable TTFT and token cadence.

With those, a **pytest** run asserts: barge-in fires within 250 ms; playback stops; the LLM stream is cancelled; **the committed assistant message equals exactly the text spoken before the playhead**; the pre-roll audio is prepended; the trace records `interrupted=1`. Deterministic. Fast. In CI. No audio hardware anywhere.

**Consequence for the roadmap:** the hardest component (`#13`) is not gated on hardware and does **not** need to wait for the target device. It can and should be built and hardened before the user ever buys a Pi. The only things that genuinely need hardware are AEC *quality*, far-field wake-word *accuracy*, real-device latency *numbers*, and GPIO — all of which are tuning, not architecture.

This also means the sketch's phase plan ("Phase 2 = voice module + embedded app, exit: works on a Pi") can be **substantially de-risked and front-loaded onto the Mac.**

---

## Anti-Patterns

### 1. "The orchestrator is just wiring"
**What people do:** Treat mic→LLM→speaker as glue code in `main.py`.
**Why it's wrong:** It is the hardest component. Both Pipecat (`Pipeline`) and LiveKit (`AgentSession`) give it a name, a package, and a lifecycle. Left as glue, it becomes an untestable 900-line file with the barge-in logic tangled into the audio callback.
**Instead:** `paaf-session` is a package, with its own tests, buildable against fakes.

### 2. Putting the sentence aggregator in the app
**What people do:** The app reads LLM tokens, splits sentences, calls `tts.say(sentence)`.
**Why it's wrong:** Duplicated by every consumer; strands `paaf-voice` as a worse standalone library; and it puts TTS-engine-specific chunking knowledge outside the TTS.
**Instead:** `TTS.speak(tokens: AsyncIterator[str])`. Voice aggregates internally, exactly as Pipecat's TTS services do.

### 3. Speaking from two places at once
**What people do:** The behaviors executor calls TTS directly while the reply is also calling TTS.
**Why it's wrong:** "Still working on it…" and the first reply sentence overlap. Given the sketch's own `after: 6s` example, this is not hypothetical.
**Instead:** A single `AudioOutputBus` with priority lanes and preemption.

### 4. Using NLTK for sentence boundaries
**What people do:** Copy Pipecat's `sent_tokenize` approach.
**Why it's wrong:** NLTK's punkt is per-language and needs a model download — a direct violation of PAAF's "no language configuration anywhere" rule. Pipecat itself notes it degrades on single-word LLM tokens.
**Instead:** A rules-based Unicode terminator matcher. Language-agnostic by construction, and simpler.

### 5. Mutating live config objects on reload
**What people do:** `agent.persona = new_persona`.
**Why it's wrong:** A turn in flight sees a half-swapped configuration; the trace's `config_revision` becomes a lie.
**Instead:** Build a new immutable graph, warm it, atomically rebind. Apply at the turn boundary.

### 6. Writing traces synchronously in a callback
**What people do:** `INSERT` from inside the LLM streaming callback.
**Why it's wrong:** An fsync lands directly in the TTFA budget. So does an autocheckpoint.
**Instead:** Bounded queue → one writer task → batched transactions. `wal_autocheckpoint=0`; checkpoint when IDLE.

### 7. Relying on discipline to keep framework types out of the public API
**What people do:** "We just won't import LangChain in `api/`."
**Why it's wrong:** Month four, a type annotation leaks, and the swappability claim quietly dies.
**Instead:** `import-linter` forbidden contracts in CI. 20 lines. Non-negotiable.

### 8. Treating permission tiers as a sandbox
**What people do:** Imply the manifest constrains skill code.
**Why it's wrong:** It doesn't. An imported plugin has full process privileges. Implying otherwise is a security misrepresentation, and this audience will find it.
**Instead:** Say it in plain language; point at MCP as the real isolation path; harden the systemd unit to protect the host.

### 9. In-process-only engines
**What people do:** `STT` is hardcoded to `faster-whisper` in the same process.
**Why it's wrong:** Whisper + Piper + a 7B model won't co-reside comfortably on a Pi 5. You will re-architect at exactly the worst moment.
**Instead:** Engine Protocols that a `remote/` (HTTP or Wyoming) client can satisfy. Costs nothing now. Also buys compatibility with the existing HA Wyoming server ecosystem.

### 10. Half-duplex ("mute the mic while speaking")
**What people do:** Stop capture during playback to avoid self-hearing.
**Why it's wrong:** It disables barge-in, which is a stated requirement.
**Instead:** AEC (hardware → OS → in-process, in that order). Partial ducking (−10 to −20 dB) as the degraded fallback.

### 11. Ignoring Ollama's `keep_alive`
**What people do:** Nothing — the default is 5 minutes.
**Why it's wrong:** Every first question after an idle period pays a multi-second model load. A voice assistant is *idle by definition*. This will look like a mysterious, intermittent 8-second latency and it will cost you a week.
**Instead:** `keep_alive: -1` on the primary local profile, exposed as a real config field.

### 12. Optimistic UI in the desktop app
**What people do:** Flip the toggle immediately, then reconcile.
**Why it's wrong:** The device is the source of truth (PROJECT.md says so). A toggle that flips and then flips back is worse than one that takes 80 ms.
**Instead:** Render device state. Update on the WS delta.

---

## Scaling Considerations

This is a **single-user appliance**, so the usual axis (concurrent users) is the wrong one. The real axes:

| Axis | What breaks | Response |
|---|---|---|
| **Concurrent turns** | 1. There is exactly one mic and one speaker. | Don't build for concurrency. A turn is a mutex. |
| **Hardware tier** ⚠️ **the real one** | Laptop / mini-PC: everything in-process, fine. **Pi 5 (8 GB): Whisper + Piper + a 7B model do not comfortably co-reside.** | Engine Protocols that admit `remote/` implementations. Offload the LLM (Ollama already is a separate process) and, if needed, STT. **Design for this on day one; it is free then and expensive later.** |
| **Devices per home** | Nothing shared — each device is independent. | Per PROJECT.md, multi-room = run multiple devices, don't invent a protocol. Correct. |
| **Trace store growth** | A year of daily use → hundreds of MB; the desktop's trace viewer gets slow. | Age + row-count retention; index `run(started_at DESC)`; `auto_vacuum=INCREMENTAL` stepped when idle. |
| **Skill count** | Prompt bloat: 20 skills × a persona fragment + tool schemas → a 4k-token system prompt → TTFT climbs, small local models degrade. | **This is a real latency risk nobody expects.** Show the composed-prompt *token count* in the desktop app (you already show the prompt verbatim — show its size). Consider tool-subset selection by routing rule later. |

**First bottleneck you will actually hit:** end-of-speech latency (VAD hangover), not model speed.
**Second:** LLM TTFT on a local model — which is exactly what the routing-rules feature exists to solve, and is the strongest argument for shipping it early rather than deferring it.

---

## Integration Points

### External

| Service | Integration pattern | Gotchas |
|---|---|---|
| Ollama | HTTP, behind the `ChatModel` port | `keep_alive` (see Anti-Pattern 11). Model pull is slow — do it out-of-band, never during a reload. |
| MCP servers | Subprocess (stdio) or HTTP, behind the `ToolExecutor` port | **The only real isolation boundary in the system.** A hanging MCP server must not hang a turn — enforce a per-tool timeout in the port, not the adapter. |
| Home Assistant | An example *skill* wrapping the HA REST/WS API. **A tool, never a dependency.** | Correct as sketched. Don't waver. |
| Wyoming (whisper/piper/openwakeword servers) | An optional `remote/` engine implementation | Unlocks the Pi offload story *and* instant reuse of the HA ecosystem's existing servers. Cheap, high leverage. |

### Internal Boundaries

| Boundary | Communication | Notes |
|---|---|---|
| `paaf-llm` ↔ `paaf-voice` | **NONE. CI-enforced.** | The whole point. `import-linter` forbidden contract. |
| `paaf-session` → `paaf-llm` | Direct calls to `Agent` / `AgentTurn` Protocols | `AsyncIterator[AgentEvent]` out; `commit(assistant_text)` in. |
| `paaf-session` → `paaf-voice` | Direct calls to STT/TTS/VAD/WakeWord Protocols | `AsyncIterator[str]` in; `AsyncIterator[AudioChunk]` out. Only `str` crosses. |
| `paaf-llm` → agent framework | `ports/` → `adapters/langgraph/` | The only place `langchain*` is importable. |
| `app-embedded` → `paaf-session` | Owns the lifecycle; calls `request_reload()`, `push_to_talk()`, `chat()` | The app owns config; the session owns the pipeline. Don't blur it. |
| `app-desktop` ↔ `app-embedded` | REST (ETag/If-Match) + WS (snapshot then deltas, seq-numbered) | Device is truth. No optimistic UI. No merge. |
| everything → `paaf-trace` | Fire-and-forget onto a bounded queue | **Never blocks. Never on the hot path.** |

---

## Confidence

| Claim | Confidence | Basis |
|---|---|---|
| Streaming overlap (STT partials → LLM tokens → TTS chunks) is the production pattern; sequential = 2–4 s | **HIGH** | LiveKit + Pipecat, independently, both explicit |
| Interruption must be an out-of-band/preempting signal, not a queued message | **HIGH** | Pipecat's `PriorityQueue`/`SystemFrame` design; LiveKit's runtime cancellation |
| Barge-in requires rolling the LLM turn back to what was *spoken* | **HIGH** | LiveKit states this explicitly; it is the load-bearing argument for `paaf-session` |
| Sentence aggregation belongs in the TTS service, and is pluggable | **HIGH** | Pipecat's `TextAggregationMode` / `LLMTextProcessor` design |
| PAAF should use Unicode terminators rather than NLTK | **MEDIUM-HIGH** | Pipecat uses NLTK + an unambiguous-punctuation fallback and documents its weakness; the "no language config" rule is PAAF's own and forbids the NLTK path. Reasoned, not cited. |
| AEC is not solved by any framework — the transport supplies it | **HIGH** | Pipecat delegates to Daily; LiveKit to WebRTC. Verified. |
| Ducking / partial ducking / echo-aware detection are the three real options | **MEDIUM** | Multiple practitioner sources agree; no single authority |
| `run_in_executor` + never-block-the-loop for inference | **HIGH** | Standard, well-documented |
| SQLite WAL + single queued writer + disabled autocheckpoint | **MEDIUM-HIGH** | WAL semantics are from SQLite docs; the writer-queue pattern is a widely-cited practitioner pattern |
| uv workspaces give independently-publishable members | **MEDIUM-HIGH** | Astral docs + multiple 2026 write-ups |
| Entry points are the standard plugin mechanism; **no sandboxing exists** | **HIGH** | Python Packaging User Guide |
| Config tiers (hot/warm/cold/restart) and the reload protocol | **MEDIUM** | Design synthesis from the constraints, not a cited reference implementation. **Worth a spike.** |
| The latency budget numbers | **MEDIUM** | LiveKit's LLM-TTFT (300–800 ms) and TTS-TTFB (100–200 ms) are cited; the VAD-hangover and local-Whisper figures are estimates and **must be measured in Spike B, not trusted.** |

### Gaps needing a phase-specific spike

1. **Measure the real end-of-speech latency.** It's the biggest chunk of the budget and the least documented. Decide whether a semantic turn detector (LiveKit ships a ~135M local model for exactly this) is worth adding — and whether one exists that is language-agnostic, which PAAF's no-language-config rule demands.
2. **Prove AEC on a real cheap USB speakerphone**, with `module-echo-cancel`. If it fails, the reference hardware config must mandate a mic with hardware AEC — a *hardware* decision driven by a *software* finding.
3. **Hot-reload of a live audio task group.** The COLD tier (device change) is the one path with no reference implementation to copy. Spike it before promising it in the UI.
4. **The composed-prompt token-count ceiling.** How many skills before TTFT on a local 7B degrades unacceptably? Nobody has published this; measure it.

---

## Sources

- [Voice Agent Architecture: STT, LLM, and TTS Pipelines Explained — LiveKit](https://livekit.com/blog/voice-agent-architecture-stt-llm-tts-pipelines-explained)
- [Sequential Pipeline Architecture for Voice Agents — LiveKit](https://livekit.com/blog/sequential-pipeline-architecture-voice-agents)
- [Adaptive interruption handling — LiveKit Docs](https://docs.livekit.io/agents/logic/turns/adaptive-interruption-handling/)
- [livekit/agents — GitHub](https://github.com/livekit/agents)
- [Custom FrameProcessor — Pipecat Docs](https://docs.pipecat.ai/guides/fundamentals/custom-frame-processor)
- [pipecat.processors.frame_processor — Pipecat API reference](https://reference-server.pipecat.ai/en/latest/api/pipecat.processors.frame_processor.html)
- [Text to Speech — Pipecat Docs](https://docs.pipecat.ai/guides/learn/text-to-speech) (TextAggregationMode)
- [pipecat.utils.string / end-of-sentence detection — pipecat-ai GitHub](https://github.com/pipecat-ai/pipecat) (NLTK + `UNAMBIGUOUS_SENTENCE_ENDING_PUNCTUATION`)
- [Proposal: graceful interruption release for TTS/output transports — pipecat #3985](https://github.com/pipecat-ai/pipecat/issues/3985)
- [Voice AI Echo Cancellation: Causes, Fixes, and Best Practices — Coval](https://www.coval.ai/blog/voice-ai-echo-cancellation/)
- [Handling barge-in: What happens when users interrupt your AI mid-sentence — Sayna](https://sayna.ai/blog/handling-barge-in-what-happens-when-users-interrupt-your-ai-mid-sentence)
- [Developing with asyncio — Python docs](https://docs.python.org/3/library/asyncio-dev.html)
- [Running Blocking ML Operations Asynchronously — apxml](https://apxml.com/courses/fastapi-ml-deployment/chapter-5-async-operations-performance/running-blocking-ml-operations)
- [Creating and discovering plugins — Python Packaging User Guide](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/)
- [Using workspaces — uv (Astral) Docs](https://docs.astral.sh/uv/concepts/projects/workspaces/)
- [How to set up a Python monorepo with uv workspaces — pydevtools](https://pydevtools.com/handbook/how-to/how-to-set-up-a-python-monorepo-with-uv-workspaces/)
- [Write-Ahead Logging — SQLite](https://sqlite.org/wal.html)
- [A SQLite Background Job System — Jason Gorman](https://jasongorman.uk/writing/sqlite-background-job-system/)
- [Wyoming Protocol — Home Assistant](https://www.home-assistant.io/integrations/wyoming/)
- [OHF-Voice/wyoming — GitHub](https://github.com/OHF-Voice/wyoming)

---
*Architecture research for: local-first streaming LLM voice assistant (framework + embedded app + Electron control panel)*
*Researched: 2026-07-13*
