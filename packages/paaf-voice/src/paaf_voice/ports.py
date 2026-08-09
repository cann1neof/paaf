# SPDX-License-Identifier: Apache-2.0
"""Core voice port protocols and immutable value objects for PAAF voice."""

from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class AudioFrame:
    """Immutable audio frame value object representing PCM audio data."""

    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2
    timestamp_ms: float = 0.0

    @property
    def duration_ms(self) -> float:
        """Calculate duration of the frame in milliseconds.

        Returns 0.0 if sample rate, channels, or sample width are invalid (<= 0)
        to prevent division-by-zero errors.
        """
        if self.sample_rate <= 0 or self.channels <= 0 or self.sample_width <= 0:
            return 0.0
        bytes_per_ms = (self.sample_rate * self.channels * self.sample_width) / 1000.0
        if bytes_per_ms <= 0:
            return 0.0
        return len(self.data) / bytes_per_ms


@dataclass(frozen=True, slots=True)
class STTResult:
    """Result of speech-to-text recognition."""

    text: str
    is_final: bool = True
    language: str | None = None
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class WakeWordResult:
    """Result of wake word detection."""

    detected: bool
    keyword: str | None = None
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class VADResult:
    """Result of voice activity detection."""

    is_speech: bool
    confidence: float = 0.0


@runtime_checkable
class AudioSource(Protocol):
    """Protocol for streaming audio hardware/input source."""

    def read_frames(self, frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]:
        """Read audio frames asynchronously."""
        ...

    def start(self) -> None:
        """Start capturing audio."""
        ...

    def stop(self) -> None:
        """Stop capturing audio."""
        ...


@runtime_checkable
class AudioSink(Protocol):
    """Protocol for audio playback hardware/sink."""

    def write_frame(self, frame: AudioFrame) -> None:
        """Write an audio frame for playback."""
        ...

    def get_playhead_position(self) -> float:
        """Get current playhead position in seconds."""
        ...

    def get_reference_tap(self) -> bytes:
        """Get played audio buffer for acoustic echo cancellation (AEC)."""
        ...

    def mark_chunk(self, text: str) -> None:
        """Mark the boundary of a new text chunk being written."""
        ...

    def get_played_chunks(self) -> list[str]:
        """Get list of sentences/chunks that were completely played out."""
        ...


@runtime_checkable
class STT(Protocol):
    """Protocol for Speech-To-Text engine."""

    def transcribe_stream(
        self, audio_stream: AsyncIterable[AudioFrame]
    ) -> AsyncIterator[STTResult]:
        """Transcribe an incoming stream of audio frames."""
        ...

    def warmup(self) -> None:
        """Pre-warm or load model resources into memory."""
        ...


@runtime_checkable
class TTS(Protocol):
    """Protocol for Text-To-Speech engine."""

    def synthesize(
        self, text: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioFrame]:
        """Synthesize text into a stream of audio frames."""
        ...

    def warmup(self) -> None:
        """Pre-warm or load model resources into memory."""
        ...


@runtime_checkable
class WakeWord(Protocol):
    """Protocol for Wake Word detection engine."""

    def detect(self, frame: AudioFrame) -> WakeWordResult:
        """Process an audio frame for wake word detection."""
        ...

    def warmup(self) -> None:
        """Pre-warm model resources into memory."""
        ...


@runtime_checkable
class VAD(Protocol):
    """Protocol for Voice Activity Detection engine."""

    def process_frame(self, frame: AudioFrame) -> VADResult:
        """Process an audio frame for speech activity."""
        ...

    def warmup(self) -> None:
        """Pre-warm model resources into memory."""
        ...
