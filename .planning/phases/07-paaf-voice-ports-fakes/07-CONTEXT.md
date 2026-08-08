# Phase 7: paaf-voice Ports & Fakes - Context

**Gathered:** 2026-08-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 delivers the `paaf-voice` package interface ports (STT, TTS, Wake Word, VAD, AudioSource, AudioSink) and their test doubles (fakes in `paaf_voice.testing`), along with a streaming token-to-sentence text aggregator and TTS text sanitizer. It establishes test doubles and streaming contracts for voice before any real engine integration (Phase 8), with zero external ML/NLTK/hardware dependencies and ~80% tests runnable from WAV fixtures.

</domain>

<decisions>
## Implementation Decisions

### Port Interfaces & Fake Double Design
- **D-01:** Define core port interfaces (STT, TTS, Wake Word, VAD, AudioSource, AudioSink) using Python `typing.Protocol` with `@runtime_checkable` — **Reversibility:** costly — preserves structural subtyping and lean imports without enforcing inheritance hierarchies across real adapters and test fakes.
- **D-02:** Place test doubles in public module `paaf_voice.testing` — **Reversibility:** costly — ships fakes as part of the public package so `paaf-session` and external consumers can import them.
- **D-03:** `FakeAudioSink` tracks playback using a virtual playhead based on sample-count and configurable speed (instant / 1x / stepped) — **Reversibility:** reversible — enables deterministic playhead position reporting and reference taps in CI tests without hardware audio output.
- **D-04:** `FakeAudioSource` streams audio frames using an `asyncio` generator yielding fixed-size PCM frames (e.g., 20ms / 320 samples @ 16kHz) — **Reversibility:** reversible — supports both WAV file playback and canned byte streams.

### Sentence Aggregation & Multilingual Rules
- **D-05:** Sentence boundary segmentation uses Python standard `unicodedata` categories + regex rules for Unicode sentence terminators (including Hebrew Sof Pasuq `׃`, Cyrillic, and Latin) — **Reversibility:** costly — zero external dependencies (no NLTK, no pyicu) and no per-language configuration.
- **D-06:** Mid-sentence script transitions (e.g. English phrase inside Cyrillic or Hebrew sentence) are treated as normal text and split only on Unicode sentence terminators — **Reversibility:** reversible — prevents premature chunking mid-phrase for single-voice multilingual synthesis.
- **D-07:** Token aggregator provides an explicit `flush()` method / sentinel on stream end — **Reversibility:** reversible — immediately yields any remaining text buffer on stream completion even without trailing punctuation.
- **D-08:** Abbreviation and decimal protection uses built-in regex guards matching numeric decimals (`\d+\.\d+`) and common multi-script abbreviations (`Dr.`, `e.g.`, `i.e.`, `vs.`, etc.) — **Reversibility:** reversible — prevents premature sentence splits.

### First-Chunk Emission & Threshold Strategy
- **D-09:** Dual character thresholds for aggregator (`first_chunk_min_chars=20` vs `subsequent_min_chars=60`) — **Reversibility:** reversible — enables early emission of chunk 1 to optimize Time-To-First-Audio (TTFA).
- **D-10:** Clause punctuation (`,`, `;`, `:`) triggers chunk emission ONLY for chunk 1 (if `first_chunk_min_chars` met); subsequent chunks strictly require sentence terminators or stream EOF — **Reversibility:** reversible — minimizes initial latency while preserving natural sentence phrasing for subsequent chunks.
- **D-11:** Test harness demonstrates TTFA reduction via deterministic benchmarks comparing short vs long first-chunk thresholds on identical token streams — **Reversibility:** reversible — validates TTFA performance gains empirically in CI.
- **D-12:** Safety fallback emits chunk 1 if max token count (15 tokens) or sentence boundary is reached, even if `first_chunk_min_chars` is not yet reached — **Reversibility:** reversible — prevents stalling on short-token LLM outputs.

### Text Sanitization & WAV Test Fixtures
- **D-13:** `TTSSanitizer` strips code blocks (```...```), inline code (`...`), headings, markdown syntax, and transforms links `[text](url)` -> `text` — **Reversibility:** costly — prevents TTS engines from speaking literal code or formatting symbols.
- **D-14:** Emojis (Unicode categories `So`, `Symbol, Other`) and raw URLs are stripped completely from text sent to TTS engines — **Reversibility:** reversible — avoids TTS engine reading out long URLs or emoji code points.
- **D-15:** WAV test fixtures and programmatic WAV frame generators live in `packages/paaf-voice/tests/fixtures/wav/` and `paaf_voice.testing` — **Reversibility:** reversible — provides zero-dependency hardware-free CI testing (VOICE-11).
- **D-16:** `TTSSanitizer` is integrated directly into the sentence aggregator / stream chunker — **Reversibility:** costly — automatically cleans text as chunks are yielded before passing to TTS ports.

### Agent Discretion
None — all 16 implementation decisions were explicitly selected and aligned with the user.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & Requirements
- `.planning/ROADMAP.md` § Phase 7 — Scope, goals, and success criteria for paaf-voice ports & fakes
- `.planning/REQUIREMENTS.md` — Requirements VOICE-01, VOICE-02, VOICE-06, VOICE-11
- `ARCHITECTURE.md` — Package boundaries, paaf-voice responsibility, and import-linter contracts

### Governance & Boundaries
- `.importlinter` — Contract `voice-and-llm-are-independent` (paaf_voice and paaf_llm must never import each other) and `no-network-client-in-framework`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `packages/paaf-voice/src/paaf_voice/__init__.py` — Package entrypoint (currently stub exposing `__version__`)
- `packages/paaf-llm/src/paaf_llm/fake/` — Established pattern for shipping test double adapters inside framework packages

### Established Patterns
- `typing.Protocol` with `@runtime_checkable` for framework ports
- Public `paaf_voice.testing` submodule for fake implementations
- Async generator streams for audio frame processing
- `pytest` suite with zero network/hardware requirements in CI

### Integration Points
- `paaf_voice.ports` — Core Protocol definitions (STT, TTS, Wake Word, VAD, AudioSource, AudioSink)
- `paaf_voice.testing` — Fake implementations (`FakeSTT`, `FakeTTS`, `FakeWakeWord`, `FakeVAD`, `FakeAudioSource`, `FakeAudioSink`)
- `paaf_voice.aggregator` — `SentenceAggregator` & `TTSSanitizer`

</code_context>

<specifics>
## Specific Ideas

No specific custom requirements — standard zero-dependency Python Unicode and async generator approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 7 scope.

</deferred>

---

*Phase: 07-paaf-voice-ports-fakes*
*Context gathered: 2026-08-08*
