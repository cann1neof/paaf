# Phase 7: paaf-voice Ports & Fakes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-08
**Phase:** 07-paaf-voice-ports-fakes
**Areas discussed:** Port Interfaces & Fake Double Design, Sentence Aggregation & Multilingual Rules, First-Chunk Emission & Threshold Strategy, Text Sanitization & WAV Test Fixtures

---

## Port Interfaces & Fake Double Design

| Option | Description | Selected |
|--------|-------------|----------|
| `typing.Protocol` with `@runtime_checkable` | Structural subtyping allowing lean imports without rigid inheritance hierarchies | ✓ |
| `abc.ABC` Abstract Base Classes | Explicit inheritance enforcing `@abstractmethod` implementation on all adapter subclasses | |
| Pydantic BaseModel Interfaces | Schema-validated method signatures for strict payload parsing | |

**User's choice:** `typing.Protocol` with `@runtime_checkable`

| Option | Description | Selected |
|--------|-------------|----------|
| `paaf_voice.testing` | Public test doubles module shipped in package for downstream paaf-session and external testing | ✓ |
| `paaf_voice.fakes` | Standalone top-level submodule for test doubles | |
| `paaf_voice.adapters.fake` | Grouped inside an adapters subpackage alongside future real engines | |

**User's choice:** `paaf_voice.testing`

| Option | Description | Selected |
|--------|-------------|----------|
| Virtual playhead with sample-count tracking & speed options | Deterministic position reporting and reference taps for CI | ✓ |
| Real-time `asyncio.sleep` ticker | Strict wall-clock playback timing matching audio duration | |
| Passive frame collector | Simple append-only audio frame list without playhead or timing state | |

**User's choice:** Virtual playhead with sample-count tracking

| Option | Description | Selected |
|--------|-------------|----------|
| Async generator yielding fixed-size PCM audio frames | Supports both WAV file playback and canned byte streams | ✓ |
| Pull-based `read(num_bytes)` method | Synchronous/asynchronous byte read contract | |
| Callback-based event stream | Subscriber push queue for incoming audio frames | |

**User's choice:** Async generator yielding fixed-size PCM audio frames

---

## Sentence Aggregation & Multilingual Rules

| Option | Description | Selected |
|--------|-------------|----------|
| Python `unicodedata` + regex rules | Zero external dependencies, Unicode sentence terminators (Latin, Cyrillic, Hebrew Sof Pasuq ׃) | ✓ |
| `pyicu` (ICU BreakIterator) | C++ wrapper providing standard Unicode UAX #29 sentence boundary segmentation | |
| Custom state machine | Manual character stream parser handling punctuation, quotes, and whitespace boundaries | |

**User's choice:** Python `unicodedata` + regex rules

| Option | Description | Selected |
|--------|-------------|----------|
| Treat script transitions as normal text | Split only on sentence terminators so mid-sentence script switches remain intact within one chunk | ✓ |
| Split chunks on script boundaries | Emit separate chunks whenever text transitions between Latin, Cyrillic, or Hebrew script | |
| Buffer script blocks | Collect text until either punctuation or a script change occurs | |

**User's choice:** Treat script transitions as normal text

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `flush()` method / sentinel on stream end | Immediately yields remaining buffer as final sentence chunk regardless of trailing punctuation | ✓ |
| Timeout-based auto-flush | Flush buffer if no new token arrives within a configurable idle window | |
| Punctuation requirement | Raise or append default period if stream ends without punctuation | |

**User's choice:** Explicit `flush()` method / sentinel on stream end

| Option | Description | Selected |
|--------|-------------|----------|
| Built-in regex guards | Match numeric decimals (`\d+\.\d+`) and common multi-script abbreviation patterns (`Dr.`, `e.g.`, etc.) | ✓ |
| Configurable abbreviation dictionary | Pass custom set of abbreviation strings to aggregator instance | |
| Post-processing chunk merge | Re-combine short chunks if previous chunk ends with an abbreviation pattern | |

**User's choice:** Built-in regex guards matching numeric decimals and abbreviations

---

## First-Chunk Emission & Threshold Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit dual thresholds | `first_chunk_min_chars=20` vs `subsequent_min_chars=60`, allowing clause punctuation to trigger early chunk 1 emission | ✓ |
| Fixed rule | Chunk 1 splits on first clause or sentence end; subsequent chunks split only on sentence end | |
| Adaptive rate-based threshold | Dynamic length adjustment based on token arrival velocity | |

**User's choice:** Explicit dual thresholds (`first_chunk_min_chars=20` vs `subsequent_min_chars=60`)

| Option | Description | Selected |
|--------|-------------|----------|
| Clause punctuation for chunk 1 ONLY | Clause punctuation triggers emission ONLY for chunk 1; subsequent chunks strictly require sentence terminators or EOF | ✓ |
| Clause punctuation for all chunks | Clause punctuation can trigger emission for any chunk if min length is met | |
| Sentence terminators only for all chunks | Strict sentence terminators for all chunks, chunk 1 simply has lower char count requirement | |

**User's choice:** Clause punctuation triggers emission ONLY for chunk 1

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic benchmark test | Compare 1st chunk emission time/token-count across short vs long 1st-chunk threshold configs on same stream | ✓ |
| Unit test | Validate emitted chunk 1 text content and length bounds under different threshold settings | |
| Integration test | Timing event callbacks from a simulated streaming pipeline | |

**User's choice:** Deterministic benchmark test comparing short vs long thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Safety fallback | Emit chunk 1 if max token count (15 tokens) or sentence boundary is reached, even if `first_chunk_min_chars` isn't met | ✓ |
| Flush on any sentence boundary | Min chars only applies when searching for clause punctuation | |
| Buffer until `min_chars` reached | No fallback | |

**User's choice:** Safety fallback on max token count (15 tokens)

---

## Text Sanitization & WAV Test Fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| Comprehensive `TTSSanitizer` | Strip code blocks, inline code, links (keep text, drop URL), headings, and formatting symbols | ✓ |
| Spoken placeholder replacement | Replace code blocks with spoken placeholder ("code snippet omitted") while stripping formatting symbols | |
| Basic character strip | Remove markdown syntax symbols without structural block removal | |

**User's choice:** Comprehensive `TTSSanitizer`

| Option | Description | Selected |
|--------|-------------|----------|
| Strip emojis and raw URLs completely | Strip emoji Unicode categories and raw URLs completely from text sent to TTS engines | ✓ |
| Translate common emojis | Translate common emojis to spoken descriptions via mapping dictionary, strip raw URLs | |
| Pass emojis through as-is | Pass emojis through as-is, strip only URLs | |

**User's choice:** Strip emoji Unicode categories and raw URLs completely

| Option | Description | Selected |
|--------|-------------|----------|
| `packages/paaf-voice/tests/fixtures/wav/` + generators | Programmatic WAV frame generators in `paaf_voice.testing` for zero-dependency CI test execution | ✓ |
| Repository-level `tests/fixtures/wav/` | Shared fixtures directory across packages | |
| Pure in-memory synthetic frame generation | Generation strictly during pytest fixture execution | |

**User's choice:** `packages/paaf-voice/tests/fixtures/wav/` + programmatic WAV frame generators in `paaf_voice.testing`

| Option | Description | Selected |
|--------|-------------|----------|
| Integrated into sentence aggregator | Sanitizes text automatically as chunks are yielded before reaching TTS ports | ✓ |
| Inside TTS port adapters | Each TTS adapter sanitizes text directly before engine processing | |
| Standalone utility | Called explicitly by `paaf-session` or caller prior to calling `TTS.speak()` | |

**User's choice:** Integrated into sentence aggregator

---

## Agent Discretion

None — all decisions were explicitly reviewed and confirmed with the user.

## Deferred Ideas

None — all items discussed fell cleanly into Phase 7 scope.
