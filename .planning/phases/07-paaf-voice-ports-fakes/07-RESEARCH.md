# Phase 7: paaf-voice Ports & Fakes — Research

**Gathered:** 2026-08-08  
**Status:** Complete  
**Target Package:** `packages/paaf-voice`  
**Requirements Addressed:** `VOICE-01`, `VOICE-02`, `VOICE-06`, `VOICE-11`  

---

## Executive Summary & Phase Boundary

Phase 7 establishes the foundation of `paaf-voice` by delivering pure Python interface ports (`typing.Protocol`), complete test doubles (`paaf_voice.testing`), a language-agnostic streaming `SentenceAggregator`, and a markdown/emoji `TTSSanitizer`.

Following PAAF's core principle of **fake-adapter-first architecture**, all 6 core voice interfaces are defined and backed by test doubles before any real ML engines (Whisper, Chatterbox, openWakeWord, Silero VAD) are integrated in Phase 8.

The implementation relies strictly on the **Python 3.12 Standard Library** (`unicodedata`, `re`, `wave`, `struct`, `asyncio`, `typing.Protocol`), with zero external dependencies (no NLTK, pyicu, numpy, soundfile, or pyaudio). ~80% of module tests run deterministically in CI from WAV fixtures without hardware microphones or speakers.

---

## Architecture & Package Structure

### Workspace Layout

```
packages/paaf-voice/
├── pyproject.toml                         # Package manifest (hatchling build, python >= 3.12)
├── src/
│   └── paaf_voice/
│       ├── __init__.py                    # Public entrypoint (version, top-level exports)
│       ├── ports.py                       # AudioFrame, STTResult, Protocols (@runtime_checkable)
│       ├── aggregator.py                  # SentenceAggregator & AggregatorConfig
│       ├── sanitizer.py                   # TTSSanitizer (markdown, code, emoji, link transformation)
│       └── testing/                       # Shipped public test double package
│           ├── __init__.py                # Exports FakeSTT, FakeTTS, FakeAudioSink, etc.
│           ├── fakes.py                   # Fake implementations of all 6 ports
│           └── generators.py              # Programmatic WAV and PCM byte generators
└── tests/
    ├── fixtures/
    │   └── wav/                           # Standard PCM WAV fixture files
    │       ├── silence_16k_1s.wav
    │       └── tone_440hz_16k_1s.wav
    ├── conftest.py                        # Shared test fixtures & helper factories
    ├── test_ports.py                      # Protocol compliance & runtime_checkable tests
    ├── test_fakes.py                      # Test doubles behavior & virtual playhead tests
    ├── test_sanitizer.py                  # TTSSanitizer rules validation
    ├── test_aggregator.py                 # Sentence boundary & multilingual chunking tests
    ├── test_ttfa_benchmark.py             # Empirical TTFA benchmark (short vs long first chunk)
    └── test_wav_fixtures.py               # WAV reading/writing and generator tests
```

### Import Independence Contract
Per `.importlinter` contract `voice-and-llm-are-independent`:
- `paaf_voice` MUST NOT import `paaf_llm` (and vice versa).
- `paaf_voice` MUST NOT import external LLM / network clients (`httpx`, `aiohttp`, `requests`).

---

## 1. Port Interface Definitions (`paaf_voice.ports`)

Core port interfaces are defined using Python `typing.Protocol` with `@runtime_checkable` (**D-01**). All data crossing the ports uses immutable PAAF value types (`dataclass(frozen=True, slots=True)`).

### Core Data Models

```python
# packages/paaf-voice/src/paaf_voice/ports.py
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterable, AsyncIterator, Protocol, runtime_checkable

@dataclass(frozen=True, slots=True)
class AudioFrame:
    """Fixed duration raw PCM audio frame container.
    
    Default parameters represent standard 16kHz mono 16-bit PCM audio.
    20ms frame @ 16kHz = 320 samples = 640 bytes.
    """
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM = 2 bytes per sample
    timestamp_ms: float = 0.0

    @property
    def duration_ms(self) -> float:
        bytes_per_ms = (self.sample_rate * self.channels * self.sample_width) / 1000.0
        return len(self.data) / bytes_per_ms if bytes_per_ms > 0 else 0.0

@dataclass(frozen=True, slots=True)
class STTResult:
    """Transcription result from speech-to-text engine."""
    text: str
    is_final: bool = True
    language: str | None = None
    confidence: float = 1.0

@dataclass(frozen=True, slots=True)
class WakeWordResult:
    """Detection result from wake word engine."""
    detected: bool
    keyword: str | None = None
    confidence: float = 0.0

@dataclass(frozen=True, slots=True)
class VADResult:
    """Voice activity detection result."""
    is_speech: bool
    confidence: float = 0.0
```

### Port Protocols

```python
@runtime_checkable
class AudioSource(Protocol):
    """Abstract interface for audio capture (microphone or fake stream)."""
    
    def read_frames(self, frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]:
        """Yield continuous audio frames of specified duration."""
        ...

    async def start(self) -> None:
        """Start audio capture hardware/stream."""
        ...

    async def stop(self) -> None:
        """Stop audio capture hardware/stream."""
        ...


@runtime_checkable
class AudioSink(Protocol):
    """Abstract interface for audio playback (speaker or fake playhead)."""
    
    async def write_frame(self, frame: AudioFrame) -> None:
        """Write an audio frame to the output device or virtual buffer."""
        ...

    def get_playhead_position(self) -> float:
        """Return current playhead playback position in seconds (D-03)."""
        ...

    def get_reference_tap(self) -> bytes:
        """Return reference audio bytes played up to playhead for AEC (VOICE-09)."""
        ...


@runtime_checkable
class STT(Protocol):
    """Abstract speech-to-text engine interface (VOICE-01)."""
    
    def transcribe_stream(
        self, audio_stream: AsyncIterable[AudioFrame]
    ) -> AsyncIterator[STTResult]:
        """Transcribe streaming audio into partial/final STT results."""
        ...

    async def warmup(self) -> None:
        """Warm up engine resources before turn execution (VOICE-10)."""
        ...


@runtime_checkable
class TTS(Protocol):
    """Abstract text-to-speech engine interface (VOICE-01)."""
    
    def synthesize(
        self, text: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioFrame]:
        """Synthesize text into streaming audio frames."""
        ...

    async def warmup(self) -> None:
        """Warm up engine resources before turn execution (VOICE-10)."""
        ...


@runtime_checkable
class WakeWord(Protocol):
    """Abstract wake word detection engine interface (VOICE-01)."""
    
    async def detect(self, frame: AudioFrame) -> WakeWordResult:
        """Evaluate a single frame for wake word trigger."""
        ...

    async def warmup(self) -> None:
        """Warm up wake word model resources (VOICE-10)."""
        ...


@runtime_checkable
class VAD(Protocol):
    """Abstract voice activity detection interface (VOICE-01)."""
    
    async def process_frame(self, frame: AudioFrame) -> VADResult:
        """Determine if audio frame contains human speech."""
        ...

    async def warmup(self) -> None:
        """Warm up VAD engine resources (VOICE-10)."""
        ...
```

---

## 2. Test Double Architecture (`paaf_voice.testing`)

Per decision **D-02**, test doubles ship in the public `paaf_voice.testing` module so `paaf-session` and external applications can run full turn state machine tests without hardware audio or ML models.

### `FakeAudioSink` & Virtual Playhead (D-03)
`FakeAudioSink` tracks playback using a virtual playhead based on sample count and configurable playback modes:
- **`instant`**: Playhead advances immediately upon `write_frame()`.
- **`1x`**: Playhead advances according to wall-clock time (`time.monotonic()`).
- **`stepped`**: Playhead advances deterministically via manual `step(ms)` calls.

```python
# packages/paaf-voice/src/paaf_voice/testing/fakes.py
import time
from typing import Literal
from paaf_voice.ports import AudioFrame, AudioSink

class FakeAudioSink(AudioSink):
    def __init__(self, mode: Literal["instant", "1x", "stepped"] = "instant") -> None:
        self.mode = mode
        self.recorded_frames: list[AudioFrame] = []
        self._total_samples_written = 0
        self._start_wall_time: float | None = None
        self._stepped_time_s: float = 0.0

    async def write_frame(self, frame: AudioFrame) -> None:
        if self._start_wall_time is None:
            self._start_wall_time = time.monotonic()
        self.recorded_frames.append(frame)
        # 16-bit mono PCM: sample_width=2, channels=1 -> samples = len(data) / 2
        samples = len(frame.data) // (frame.channels * frame.sample_width)
        self._total_samples_written += samples

    def step(self, duration_ms: float) -> None:
        """Manually advance playhead in 'stepped' mode."""
        self._stepped_time_s += duration_ms / 1000.0

    def get_playhead_position(self) -> float:
        total_duration_s = self._total_samples_written / 16000.0  # assuming 16kHz
        if self.mode == "instant":
            return total_duration_s
        elif self.mode == "1x":
            if self._start_wall_time is None:
                return 0.0
            elapsed = time.monotonic() - self._start_wall_time
            return min(total_duration_s, elapsed)
        elif self.mode == "stepped":
            return min(total_duration_s, self._stepped_time_s)
        return 0.0

    def get_reference_tap(self) -> bytes:
        """Return reference PCM audio played up to current playhead position."""
        pos_s = self.get_playhead_position()
        target_bytes = int(pos_s * 16000 * 2)  # 16kHz 16-bit PCM mono
        accumulated = bytearray()
        for f in self.recorded_frames:
            accumulated.extend(f.data)
            if len(accumulated) >= target_bytes:
                return bytes(accumulated[:target_bytes])
        return bytes(accumulated)
```

### `FakeAudioSource` Stream Generator (D-04)
`FakeAudioSource` yields fixed-size PCM frames (e.g. 20ms / 320 samples / 640 bytes @ 16kHz) from canned bytes or WAV file inputs via `asyncio.sleep()`.

```python
class FakeAudioSource(AudioSource):
    def __init__(self, pcm_data: bytes, sample_rate: int = 16000, realtime: bool = False) -> None:
        self.pcm_data = pcm_data
        self.sample_rate = sample_rate
        self.realtime = realtime
        self._active = False

    async def start(self) -> None:
        self._active = True

    async def stop(self) -> None:
        self._active = False

    async def read_frames(self, frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]:
        bytes_per_frame = int((self.sample_rate * 1 * 2) * (frame_duration_ms / 1000.0))
        offset = 0
        timestamp_ms = 0.0
        while self._active and offset < len(self.pcm_data):
            chunk = self.pcm_data[offset : offset + bytes_per_frame]
            if len(chunk) < bytes_per_frame:
                chunk = chunk + b"\x00" * (bytes_per_frame - len(chunk))
            
            frame = AudioFrame(
                data=chunk,
                sample_rate=self.sample_rate,
                timestamp_ms=timestamp_ms
            )
            yield frame
            offset += bytes_per_frame
            timestamp_ms += frame_duration_ms
            if self.realtime:
                await asyncio.sleep(frame_duration_ms / 1000.0)
```

### Other Shipped Test Doubles
- `FakeSTT`: Returns pre-configured transcriptions or streams tokens.
- `FakeTTS`: Yields synthetic tone frames proportional to text length; records input text in `synthesized_texts: list[str]`.
- `FakeWakeWord`: Responds to manual `trigger()` calls or pattern matching.
- `FakeVAD`: Follows a pre-configured timeline of speech vs non-speech frames.

---

## 3. Sentence Aggregation & Multilingual Text Sanitization

### Text Sanitizer (`TTSSanitizer`)

`TTSSanitizer` cleans LLM output before passing chunks to TTS engines (**D-13**, **D-14**, **D-16**):
1. **Fenced Code Blocks**: Removes ```...``` blocks completely.
2. **Inline Code**: Removes backticks surrounding inline code (`...` -> `...`).
3. **Headings**: Removes `#`, `##`, `###` prefixes.
4. **Markdown Formatting**: Removes `**`, `*`, `__`, `_`, `~`.
5. **Markdown Links**: Transforms `[Anchor Text](http://url)` -> `Anchor Text`.
6. **Raw URLs**: Strips `http://...` and `https://...` completely.
7. **Emojis**: Strips Unicode category `So` (Symbol, Other) and emoji code point ranges.

```python
# packages/paaf-voice/src/paaf_voice/sanitizer.py
import re
import unicodedata

class TTSSanitizer:
    # Regex patterns
    CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
    URL_RE = re.compile(r"https?://\S+")
    MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
    HEADING_RE = re.compile(r"^\s*#+\s*", re.MULTILINE)
    INLINE_CODE_RE = re.compile(r"`([^`]+)`")
    MARKDOWN_FORMAT_RE = re.compile(r"[*_~]{1,3}")

    @classmethod
    def sanitize(cls, text: str) -> str:
        if not text:
            return ""
        # 1. Remove code blocks
        text = cls.CODE_BLOCK_RE.sub("", text)
        # 2. Convert markdown links [text](url) -> text
        text = cls.MARKDOWN_LINK_RE.sub(r"\1", text)
        # 3. Strip raw URLs
        text = cls.URL_RE.sub("", text)
        # 4. Remove headings
        text = cls.HEADING_RE.sub("", text)
        # 5. Remove inline code backticks (keep content)
        text = cls.INLINE_CODE_RE.sub(r"\1", text)
        # 6. Remove bold/italic markers
        text = cls.MARKDOWN_FORMAT_RE.sub("", text)
        # 7. Strip Emojis (category 'So' and explicit symbol ranges)
        text = cls._strip_emojis(text)
        # 8. Collapse extra whitespace
        return " ".join(text.split())

    @staticmethod
    def _strip_emojis(text: str) -> str:
        cleaned = []
        for char in text:
            cat = unicodedata.category(char)
            # 'So' = Symbol, Other (includes most emojis)
            if cat == "So":
                continue
            cleaned.append(char)
        return "".join(cleaned)
```

### Sentence Aggregator (`SentenceAggregator`)

The aggregator processes incoming LLM tokens and yields clean, speakable text sentences.

#### Key Rules & Requirements:
1. **Unicode Sentence Boundaries (D-05)**:
   - Latin/Cyrillic: `.`, `!`, `?`
   - Hebrew: `׃` (Sof Pasuq, `U+05C3`)
   - CJK: `。`, `！`, `？` (`U+3002`, `U+FF01`, `U+FF1F`)
2. **Abbreviation & Decimal Protection (D-08)**:
   - Decimals: `\d+\.\d+` (e.g. `3.14`)
   - Abbreviations: `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `Prof.`, `Sr.`, `Jr.`, `e.g.`, `i.e.`, `vs.`, `etc.`, `St.`, `approx.`
3. **Mid-Sentence Script Transitions (D-06)**:
   - English phrases inside Cyrillic or Hebrew text (e.g., `"Я запускаю Python скрипт."`) are NOT split on script boundary; they are split ONLY on sentence terminators.
4. **First-Chunk Early Emission Strategy (D-09, D-10, D-12)**:
   - **Chunk 1**: `first_chunk_min_chars = 20`. Clause punctuation (`,`, `;`, `:`) OR sentence terminators trigger emission if buffer >= 20.
   - **Chunk 1 Safety Fallbacks (D-12)**: Emits chunk 1 immediately if max token count (15 tokens) OR sentence terminator is reached, even if buffer < 20 chars.
   - **Subsequent Chunks (D-10)**: `subsequent_min_chars = 60`. Clause punctuation is IGNORED; emission strictly requires sentence terminators OR stream EOF.
5. **Sentinel & Flush (D-07)**:
   - Calling `flush()` or ending input stream immediately yields any remaining text buffer.

```python
# packages/paaf-voice/src/paaf_voice/aggregator.py
from dataclasses import dataclass
from typing import AsyncIterable, AsyncIterator
from paaf_voice.sanitizer import TTSSanitizer

@dataclass(frozen=True, slots=True)
class AggregatorConfig:
    first_chunk_min_chars: int = 20
    subsequent_min_chars: int = 60
    max_first_chunk_tokens: int = 15

class SentenceAggregator:
    # Unicode sentence terminators: . ! ? Hebrew Sof Pasuq ׃ (U+05C3) CJK 。 ！ ？
    SENTENCE_TERMINATORS = {".", "!", "?", "׃", "。", "！", "？"}
    CLAUSE_PUNCTUATION = {",", ";", ":"}

    def __init__(self, config: AggregatorConfig | None = None) -> None:
        self.config = config or AggregatorConfig()
        self._buffer = ""
        self._token_count = 0
        self._first_chunk_emitted = False

    async def aggregate_stream(self, token_stream: AsyncIterable[str]) -> AsyncIterator[str]:
        async for token in token_stream:
            for chunk in self.add_token(token):
                yield chunk
        for chunk in self.flush():
            yield chunk

    def add_token(self, token: str) -> list[str]:
        self._buffer += token
        self._token_count += 1
        return self._evaluate_buffer()

    def flush(self) -> list[str]:
        if not self._buffer.strip():
            self._buffer = ""
            return []
        cleaned = TTSSanitizer.sanitize(self._buffer)
        self._buffer = ""
        self._token_count = 0
        return [cleaned] if cleaned else []
```

---

## 4. Programmatic WAV Generators & Test Fixtures

Per **D-15** and **VOICE-11**, zero-dependency standard library helper utilities in `paaf_voice.testing.generators` allow generating standard 16kHz mono 16-bit PCM WAV frames and bytes programmatically.

```python
# packages/paaf-voice/src/paaf_voice/testing/generators.py
import math
import struct
import wave
import io

def generate_pcm_sine_bytes(
    duration_s: float, frequency: float = 440.0, sample_rate: int = 16000
) -> bytes:
    """Generate raw 16-bit signed mono PCM sine wave bytes."""
    num_samples = int(duration_s * sample_rate)
    samples = []
    for i in range(num_samples):
        t = float(i) / sample_rate
        val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * frequency * t))
        samples.append(struct.pack("<h", val))
    return b"".join(samples)

def create_wav_bytes(
    pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Wrap raw PCM bytes into a valid WAV file in memory using stdlib wave module."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
```

---

## 5. TTFA Benchmark Strategy (D-11)

To satisfy **D-11** (empirically proving TTFA latency reduction in CI), a benchmark test compares `first_chunk_min_chars=20` (dual threshold) vs `first_chunk_min_chars=60` (single threshold) on identical token streams.

```python
# packages/paaf-voice/tests/test_ttfa_benchmark.py
import pytest
from paaf_voice.aggregator import SentenceAggregator, AggregatorConfig

def test_ttfa_first_chunk_reduction():
    # Simulated streaming LLM token output with initial clause
    tokens = ["Hello ", "there, ", "I ", "am ", "ready ", "to ", "assist ", "you. ", "How ", "can ", "I ", "help?"]

    # Short first chunk config (PAAF strategy: 20 chars + clause)
    agg_short = SentenceAggregator(AggregatorConfig(first_chunk_min_chars=20, subsequent_min_chars=60))
    chunks_short = []
    for i, t in enumerate(tokens):
        res = agg_short.add_token(t)
        if res and not chunks_short:
            first_chunk_token_index_short = i
            chunks_short.extend(res)

    # Long first chunk config (Baseline: 60 chars)
    agg_long = SentenceAggregator(AggregatorConfig(first_chunk_min_chars=60, subsequent_min_chars=60))
    chunks_long = []
    for i, t in enumerate(tokens):
        res = agg_long.add_token(t)
        if res and not chunks_long:
            first_chunk_token_index_long = i
            chunks_long.extend(res)

    # Assert short strategy emitted chunk 1 much earlier in token stream
    assert first_chunk_token_index_short < first_chunk_token_index_long
    assert chunks_short[0] == "Hello there,"
```

---

## Validation Architecture

### 1. Test Suite Structure Matrix

| Test Module | Goal / Requirement | Primary Assertions |
|-------------|-------------------|-------------------|
| `test_ports.py` | `VOICE-01`, `D-01` | Verify `isinstance(FakeAdapter, Protocol)` works with `@runtime_checkable` across all 6 ports. Assert no framework imports. |
| `test_fakes.py` | `VOICE-02`, `D-02`, `D-03`, `D-04` | Assert `FakeAudioSink` virtual playhead in `instant`, `1x`, `stepped` modes. Test reference tap output. Test `FakeAudioSource` frame yield sizes. |
| `test_sanitizer.py` | `D-13`, `D-14` | Assert stripping of ```code```, backticks, `#` headings, URLs (`https://...`), emojis (`So`), and transformation of `[link](url)` -> `link`. |
| `test_aggregator.py` | `VOICE-06`, `D-05`..`D-10`, `D-12` | Test sentence boundary splitting across Latin, Cyrillic, Hebrew `׃` Sof Pasuq, CJK. Test decimal/abbreviation protection. Test mid-sentence script transition. Test safety fallbacks (15 tokens). Test `flush()`. |
| `test_ttfa_benchmark.py` | `D-11` | Empirical benchmark asserting early token index emission for 20-char first-chunk vs 60-char baseline. |
| `test_wav_fixtures.py` | `VOICE-11`, `D-15` | Verify standard WAV reading/writing, sine frame generation, and test execution against static WAV fixture files without microphone hardware. |

### 2. CI Commands
Verification must run cleanly via `uv`:
1. `uv run pytest packages/paaf-voice` — Run full unit & benchmark test suite.
2. `uv run lint-imports` — Validate import contracts (ensure `paaf_voice` has no imports of `paaf_llm` or forbidden packages).

---

## Recommended Task Execution Plan

Phase 7 implementation should be broken down into 4 clear plans:

1. **Plan 01: Core Ports & Audio Models (`paaf_voice.ports`)**
   - Create `src/paaf_voice/ports.py` containing `AudioFrame`, `STTResult`, `WakeWordResult`, `VADResult`, and `@runtime_checkable` Protocols (`AudioSource`, `AudioSink`, `STT`, `TTS`, `WakeWord`, `VAD`).
   - Create `tests/test_ports.py` verifying protocol compliance and signature contracts.

2. **Plan 02: Test Doubles & Virtual Hardware (`paaf_voice.testing`)**
   - Create `src/paaf_voice/testing/fakes.py` and `generators.py`.
   - Implement `FakeAudioSink` with `instant`, `1x`, `stepped` playhead modes and reference tap.
   - Implement `FakeAudioSource` streaming PCM frames.
   - Implement `FakeSTT`, `FakeTTS`, `FakeWakeWord`, `FakeVAD`.
   - Add WAV fixtures in `tests/fixtures/wav/` and write `tests/test_fakes.py` & `tests/test_wav_fixtures.py`.

3. **Plan 03: Text Sanitizer (`TTSSanitizer`)**
   - Create `src/paaf_voice/sanitizer.py`.
   - Implement markdown syntax removal, link transformation, URL stripping, emoji removal (`So` category).
   - Write `tests/test_sanitizer.py` covering edge cases.

4. **Plan 04: Sentence Aggregator & TTFA Benchmarks (`SentenceAggregator`)**
   - Create `src/paaf_voice/aggregator.py`.
   - Implement Unicode boundary splitting (Latin, Cyrillic, Hebrew `׃` Sof Pasuq, CJK), decimal/abbreviation protection, dual character thresholds (20 vs 60), clause punctuation chunk 1 emission, safety fallbacks, and `flush()`.
   - Integrate `TTSSanitizer` into aggregator.
   - Write `tests/test_aggregator.py` and `tests/test_ttfa_benchmark.py`.

---

## RESEARCH COMPLETE
