# Phase 07: paaf-voice Ports & Fakes — Pattern Mapping

**Gathered:** 2026-08-08  
**Status:** Complete  
**Target Package:** `packages/paaf-voice`  
**Requirements Addressed:** `VOICE-01`, `VOICE-02`, `VOICE-06`, `VOICE-11`

---

## Executive Summary

Phase 07 establishes the core interface ports, shipped public test doubles, streaming text sentence aggregator, and markdown/emoji TTS sanitizer for `paaf-voice`. In accordance with PAAF's **fake-adapter-first architecture**, all 6 core voice interfaces (STT, TTS, Wake Word, VAD, AudioSource, AudioSink) are defined using pure Python protocols and backed by robust test doubles in `paaf_voice.testing` before any real hardware or ML engine integration (Phase 8).

This document maps all files to be created or modified, classifies their role and data flow, links them to existing codebase analogs (in `paaf-llm` and `paaf-core`), extracts concrete code patterns, and establishes governance compliance rules (e.g. `.importlinter` boundaries, zero third-party audio/ML dependencies, standard library Unicode processing).

---

## System Map: Component Roles & Data Flow Matrix

| File Path | Role | Data Flow | Closest Analog |
|-----------|------|-----------|----------------|
| [`src/paaf_voice/ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/ports.py) | Core Domain Interfaces & Data Models | Defines frozen value objects (`AudioFrame`, `STTResult`, `WakeWordResult`, `VADResult`) and `@runtime_checkable` `Protocol` boundaries (`AudioSource`, `AudioSink`, `STT`, `TTS`, `WakeWord`, `VAD`). | [`packages/paaf-llm/src/paaf_llm/ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/ports.py) |
| [`src/paaf_voice/testing/fakes.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/testing/fakes.py) | Shipped Public Test Doubles | Implements `FakeAudioSink` (with virtual playhead & reference tap), `FakeAudioSource`, `FakeSTT`, `FakeTTS`, `FakeWakeWord`, `FakeVAD`. Consumes frames/text and produces test outputs deterministically. | [`packages/paaf-llm/src/paaf_llm/fake/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/fake/__init__.py) |
| [`src/paaf_voice/testing/generators.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/testing/generators.py) | Audio Data Synthetic Generator Utilities | Pure functions generating PCM sine wave bytes and in-memory WAV structures using stdlib `struct`, `math`, `wave`, `io`. | Helper factories in [`packages/paaf-llm/src/paaf_llm/fake/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/fake/__init__.py) |
| [`src/paaf_voice/testing/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/testing/__init__.py) | Public Testing Module Entrypoint | Re-exports all fake test doubles and generator utilities so `paaf-session` and external applications can import them. | [`packages/paaf-llm/src/paaf_llm/fake/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/fake/__init__.py) |
| [`src/paaf_voice/sanitizer.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/sanitizer.py) | Text Sanitizer | Receives raw LLM string, strips markdown, code blocks, URLs, and Unicode `So` category emojis, transforming links `[text](url)` to anchor text. | [`packages/paaf-llm/src/paaf_llm/compose.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/compose.py) |
| [`src/paaf_voice/aggregator.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/aggregator.py) | Streaming Sentence Aggregator | Consumes `AsyncIterable[str]` LLM token stream, accumulates buffer, evaluates Unicode boundaries & TTFA dual thresholds, sanitizes via `TTSSanitizer`, and yields ready-to-speak sentences. | [`packages/paaf-llm/src/paaf_llm/agent.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/agent.py) |
| [`src/paaf_voice/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/src/paaf_voice/__init__.py) | Package Top-Level Entrypoint | Re-exports ports, aggregator, sanitizer, and package version. | [`packages/paaf-llm/src/paaf_llm/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/__init__.py) |
| [`tests/fixtures/wav/silence_16k_1s.wav`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/fixtures/wav/silence_16k_1s.wav) | Standard PCM WAV Fixture File | 1-second 16kHz mono 16-bit PCM silent audio fixture for zero-dependency CI test execution. | Test data files in `packages/paaf-core/tests/` |
| [`tests/test_ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_ports.py) | Protocol Conformance Unit Tests | Verifies `@runtime_checkable` compliance for all 6 port protocols and validates data object immutability. | [`packages/paaf-llm/tests/test_ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/tests/test_ports.py) |
| [`tests/test_fakes.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_fakes.py) | Test Double Behavior Tests | Exercises `FakeAudioSink` playhead modes (`instant`, `1x`, `stepped`), AEC reference tap, and `FakeAudioSource` frame streaming. | [`packages/paaf-llm/tests/test_fake_adapter.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/tests/test_fake_adapter.py) |
| [`tests/test_sanitizer.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_sanitizer.py) | Text Sanitizer Unit Tests | Tests markdown removal, URL stripping, link conversion, and Unicode emoji stripping. | [`packages/paaf-llm/tests/test_compose.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/tests/test_compose.py) |
| [`tests/test_aggregator.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_aggregator.py) | Sentence Chunker Unit Tests | Tests sentence boundaries (Latin, Cyrillic, Hebrew `׃` Sof Pasuq, CJK), decimal/abbreviation protection, script transitions, and `flush()`. | [`packages/paaf-llm/tests/test_agent_turn.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/tests/test_agent_turn.py) |
| [`tests/test_ttfa_benchmark.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_ttfa_benchmark.py) | Empirical TTFA Latency Benchmark | Asserts early token index emission for short dual threshold (20 chars + clause) vs baseline (60 chars). | Baseline benchmarks in [`packages/paaf-llm/tests/test_fallback.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/tests/test_fallback.py) |
| [`tests/test_wav_fixtures.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-voice/tests/test_wav_fixtures.py) | WAV Fixture & Generator Tests | Asserts correct header parsing, frame sizing, and audio generation via stdlib `wave`. | [`packages/paaf-core/tests/test_atomic_write.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-core/tests/test_atomic_write.py) |

---

## Architectural Patterns & Code Analogues

### 1. Pure PAAF Ports & Immutable Value Types

* **Existing Analog**: [`packages/paaf-llm/src/paaf_llm/ports.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/ports.py#L44-L120)
* **Pattern**: All domain data structures crossing framework boundaries use `@dataclass(frozen=True, slots=True)`. Interfaces use Python `typing.Protocol` with `@runtime_checkable` (**D-01**). Zero third-party or hardware imports are allowed in core port definitions.
* **Code Excerpt (Analog)**:
  ```python
  @dataclass(frozen=True, slots=True)
  class Message:
      role: Role
      content: str

  @runtime_checkable
  class ChatAdapter(Protocol):
      def stream(self, profile: ModelProfile, messages: Sequence[Message]) -> AsyncIterator[str]: ...
  ```
* **Phase 07 Port Application**:
  ```python
  @dataclass(frozen=True, slots=True)
  class AudioFrame:
      data: bytes
      sample_rate: int = 16000
      channels: int = 1
      sample_width: int = 2  # 16-bit PCM = 2 bytes per sample
      timestamp_ms: float = 0.0

      @property
      def duration_ms(self) -> float:
          bytes_per_ms = (self.sample_rate * self.channels * self.sample_width) / 1000.0
          return len(self.data) / bytes_per_ms if bytes_per_ms > 0 else 0.0

  @runtime_checkable
  class AudioSink(Protocol):
      async def write_frame(self, frame: AudioFrame) -> None: ...
      def get_playhead_position(self) -> float: ...
      def get_reference_tap(self) -> bytes: ...
  ```

---

### 2. Shipped Public Test Doubles & Virtual Hardware

* **Existing Analog**: [`packages/paaf-llm/src/paaf_llm/fake/__init__.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/fake/__init__.py#L82-L135)
* **Pattern**: Framework packages ship their test doubles in a public submodule (`paaf_voice.testing`) so downstream packages (`paaf-session`, CLI, user apps) can execute end-to-end turns in CI without hardware micro-phones, speakers, or ML models (**D-02**).
* **Virtual Playhead Modes (D-03)**: `FakeAudioSink` supports `instant` (immediate sample duration accumulation), `1x` (wall-clock bounded using `time.monotonic()`), and `stepped` (manual advance via `step(ms)`).
* **Code Excerpt (Phase 07 Pattern)**:
  ```python
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
          samples = len(frame.data) // (frame.channels * frame.sample_width)
          self._total_samples_written += samples

      def step(self, duration_ms: float) -> None:
          self._stepped_time_s += duration_ms / 1000.0

      def get_playhead_position(self) -> float:
          total_s = self._total_samples_written / 16000.0
          if self.mode == "instant":
              return total_s
          elif self.mode == "1x":
              if self._start_wall_time is None:
                  return 0.0
              return min(total_s, time.monotonic() - self._start_wall_time)
          elif self.mode == "stepped":
              return min(total_s, self._stepped_time_s)
          return 0.0

      def get_reference_tap(self) -> bytes:
          pos_s = self.get_playhead_position()
          target_bytes = int(pos_s * 16000 * 2)
          accumulated = bytearray()
          for f in self.recorded_frames:
              accumulated.extend(f.data)
              if len(accumulated) >= target_bytes:
                  return bytes(accumulated[:target_bytes])
          return bytes(accumulated)
  ```

---

### 3. Multilingual Unicode Sentence Boundary Engine

* **Existing Analog**: [`packages/paaf-llm/src/paaf_llm/compose.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/compose.py) (Pure text transformation using standard library)
* **Pattern**: Zero external NLP/NLTK/ICU dependencies (**D-05**). Uses Python `unicodedata` categories + explicit regex guards to match Unicode sentence terminators across Latin, Cyrillic, Hebrew Sof Pasuq (`׃`), and CJK (`。`, `！`, `？`).
* **Regex Protection Rules**:
  - **Decimals (D-08)**: Protect `\d+\.\d+` (e.g. `3.14`).
  - **Abbreviations (D-08)**: Protect `Dr.`, `Mr.`, `Mrs.`, `Ms.`, `Prof.`, `Sr.`, `Jr.`, `e.g.`, `i.e.`, `vs.`, `etc.`, `St.`, `approx.`.
  - **Mid-sentence script transitions (D-06)**: English words inside Cyrillic/Hebrew sentences are processed as normal text and split ONLY on sentence terminators.
* **Code Excerpt**:
  ```python
  class SentenceAggregator:
      SENTENCE_TERMINATORS = {".", "!", "?", "׃", "。", "！", "？"}
      CLAUSE_PUNCTUATION = {",", ";", ":"}
      ABBREVIATION_PATTERN = re.compile(
          r"\b(Dr|Mr|Mrs|Ms|Prof|Sr|Jr|e\.g|i\.e|vs|etc|St|approx)\.$", re.IGNORECASE
      )
  ```

---

### 4. Early-Emission Dual-Threshold Aggregator & TTFA Optimization

* **Existing Analog**: Streaming token consumer patterns in [`packages/paaf-llm/src/paaf_llm/agent.py`](file:///Users/alexanderikonnikov/Documents/repos/paaf/packages/paaf-llm/src/paaf_llm/agent.py)
* **Pattern**: Dual character threshold strategy to minimize Time-To-First-Audio (TTFA) without degrading natural phrasing for subsequent chunks (**D-09**, **D-10**):
  - **Chunk 1**: Threshold = 20 chars (`first_chunk_min_chars=20`). Clause punctuation (`,`, `;`, `:`) OR sentence terminators trigger emission when buffer length >= 20.
  - **Safety Fallback (D-12)**: Chunk 1 emits immediately if buffer reaches 15 tokens or encounters a sentence terminator, even if character length < 20.
  - **Subsequent Chunks (D-10)**: Threshold = 60 chars (`subsequent_min_chars=60`). Clause punctuation is ignored; emission strictly requires a sentence terminator or stream EOF.
  - **Flush (D-07)**: `flush()` method or stream EOF immediately cleans and yields any remaining text buffer.
* **Integrated Sanitization (D-16)**: `TTSSanitizer` cleans every chunk before yielding.

---

### 5. Standard Library WAV Generators & Fixtures

* **Existing Analog**: `packages/paaf-core/tests/test_atomic_write.py`
* **Pattern**: Hardware-free WAV generation using standard library `wave`, `struct`, `math`, `io` (**D-15**, **VOICE-11**).
* **Code Excerpt**:
  ```python
  def generate_pcm_sine_bytes(
      duration_s: float, frequency: float = 440.0, sample_rate: int = 16000
  ) -> bytes:
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
      buf = io.BytesIO()
      with wave.open(buf, "wb") as wf:
          wf.setnchannels(channels)
          wf.setsampwidth(sample_width)
          wf.setframerate(sample_rate)
          wf.writeframes(pcm_data)
      return buf.getvalue()
  ```

---

## Complete File-by-File Implementation Plan

### 1. `packages/paaf-voice/src/paaf_voice/ports.py`
- **Purpose**: Core port protocols and immutable PAAF audio data types.
- **Key Exports**: `AudioFrame`, `STTResult`, `WakeWordResult`, `VADResult`, `AudioSource`, `AudioSink`, `STT`, `TTS`, `WakeWord`, `VAD`.
- **Dependencies**: Standard library `dataclasses`, `typing` (`Protocol`, `runtime_checkable`, `AsyncIterable`, `AsyncIterator`). Zero third-party dependencies.

### 2. `packages/paaf-voice/src/paaf_voice/sanitizer.py`
- **Purpose**: Cleans LLM Markdown and Unicode formatting for speech synthesis.
- **Key Methods**: `TTSSanitizer.sanitize(text: str) -> str`.
- **Transformation Steps**:
  1. Remove fenced code blocks (```...```).
  2. Remove headings (`#`, `##`, `###`).
  3. Transform markdown links `[anchor](url)` to `anchor`.
  4. Strip raw HTTP/HTTPS URLs.
  5. Remove inline backticks (keeping internal code text).
  6. Strip bold/italic formatting (`*`, `_`, `~`).
  7. Strip emojis using Unicode category check `unicodedata.category(char) == "So"`.
  8. Normalize whitespace.

### 3. `packages/paaf-voice/src/paaf_voice/aggregator.py`
- **Purpose**: Streaming token accumulator and sentence chunker.
- **Key Classes**: `AggregatorConfig`, `SentenceAggregator`.
- **Key Methods**: `add_token(token: str) -> list[str]`, `flush() -> list[str]`, `aggregate_stream(token_stream: AsyncIterable[str]) -> AsyncIterator[str]`.

### 4. `packages/paaf-voice/src/paaf_voice/testing/fakes.py`
- **Purpose**: Public test double implementations for all 6 port protocols.
- **Key Classes**:
  - `FakeAudioSink(AudioSink)`: Supports `instant`, `1x`, `stepped` playhead position tracking and reference tap extraction.
  - `FakeAudioSource(AudioSource)`: Streams fixed 20ms PCM frames from bytes/WAV fixtures with optional real-time pacing.
  - `FakeSTT(STT)`: Yields pre-scripted transcriptions.
  - `FakeTTS(TTS)`: Generates tone PCM frames proportional to input text; records synthesized text history.
  - `FakeWakeWord(WakeWord)`: Evaluates frames against trigger rules.
  - `FakeVAD(VAD)`: Evaluates frames against pre-configured speech timelines.

### 5. `packages/paaf-voice/src/paaf_voice/testing/generators.py`
- **Purpose**: Programmatic audio frame and WAV buffer generators for testing.
- **Key Exports**: `generate_pcm_sine_bytes`, `create_wav_bytes`.

### 6. `packages/paaf-voice/src/paaf_voice/testing/__init__.py`
- **Purpose**: Module initializer re-exporting test doubles and generators.

### 7. `packages/paaf-voice/src/paaf_voice/__init__.py`
- **Purpose**: Package entrypoint re-exporting core ports, aggregator, and sanitizer.

### 8. `packages/paaf-voice/tests/test_ports.py`
- **Purpose**: Tests protocol `@runtime_checkable` inheritance compliance and dataclass immutability.

### 9. `packages/paaf-voice/tests/test_fakes.py`
- **Purpose**: Unit tests for all shipped test double behaviors (playhead modes, reference tap, audio source streaming).

### 10. `packages/paaf-voice/tests/test_sanitizer.py`
- **Purpose**: Comprehensive test cases for markdown, code, emoji, and link stripping rules.

### 11. `packages/paaf-voice/tests/test_aggregator.py`
- **Purpose**: Unit tests for sentence boundary splitting across Latin, Cyrillic, Hebrew, CJK, decimal/abbreviation protection, and `flush()`.

### 12. `packages/paaf-voice/tests/test_ttfa_benchmark.py`
- **Purpose**: Empirical benchmark test proving earlier first-chunk emission for dual threshold (20 chars) vs single baseline threshold (60 chars).

### 13. `packages/paaf-voice/tests/test_wav_fixtures.py`
- **Purpose**: Tests parsing static WAV fixtures and programmatically generated audio buffers.

---

## Governance & Contract Compliance

### 1. Import-Linter Contracts (`.importlinter`)
- **`voice-and-llm-are-independent`**: `paaf_voice` MUST NOT import `paaf_llm` or any of its submodules.
- **`no-network-client-in-framework`**: `paaf_voice` MUST NOT import `httpx`, `requests`, `aiohttp`, or `socket`.
- **`langchain-confined-to-adapter`**: `paaf_voice` MUST NOT import any LangChain/LangGraph modules.

### 2. Dependency Rules
- `paaf-voice` `pyproject.toml` dependencies remain empty (`dependencies = []`).
- Uses strictly **Python 3.12 Standard Library** (`unicodedata`, `re`, `wave`, `struct`, `math`, `io`, `asyncio`, `dataclasses`, `typing`).

---

## Verification & Execution Commands

When implementation plans complete, run the following verification steps:
1. `uv run pytest packages/paaf-voice` — Executes unit tests and TTFA benchmarks.
2. `uv run lint-imports` — Validates architectural independence boundaries.

---

## PATTERN MAPPING COMPLETE
