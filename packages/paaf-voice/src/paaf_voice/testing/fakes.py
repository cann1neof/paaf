# SPDX-License-Identifier: Apache-2.0
"""Fake implementations of voice hardware ports for testing."""

import asyncio
import time
from collections.abc import AsyncIterable, AsyncIterator
from typing import Literal

from paaf_voice.ports import (
    STT,
    TTS,
    VAD,
    AudioFrame,
    AudioSink,
    AudioSource,
    STTResult,
    VADResult,
    WakeWord,
    WakeWordResult,
)


class FakeAudioSink(AudioSink):
    """Test double for AudioSink hardware playback.

    Supports virtual playhead tracking ('instant', '1x', 'stepped') and
    reference tap extraction for Acoustic Echo Cancellation (AEC).
    """

    def __init__(self, mode: Literal["instant", "1x", "stepped"] = "instant") -> None:
        self.mode = mode
        self.recorded_frames: list[AudioFrame] = []
        self._start_wall_time: float | None = None
        self._stepped_time_s: float = 0.0
        self._chunks: list[str] = []

    def mark_chunk(self, text: str) -> None:
        """Mark the boundary of a new text chunk being written."""
        self._chunks.append(text)

    def get_played_chunks(self) -> list[str]:
        """Get list of sentences/chunks that were completely played out."""
        # For a fake sink, we'll just return all marked chunks if mode="instant"
        # Since it's instant, they are immediately "played"
        if self.mode == "instant":
            return self._chunks.copy()
        return []

    def write_frame(self, frame: AudioFrame) -> None:
        """Record an incoming audio frame."""
        self.recorded_frames.append(frame)
        if self.mode == "1x" and self._start_wall_time is None:
            self._start_wall_time = time.monotonic()

    def step(self, duration_ms: float) -> None:
        """Advance playhead in stepped mode by duration_ms."""
        self._stepped_time_s += duration_ms / 1000.0

    def get_total_duration_s(self) -> float:
        """Calculate total duration of all recorded frames in seconds."""
        return sum(frame.duration_ms for frame in self.recorded_frames) / 1000.0

    def get_playhead_position(self) -> float:
        """Get current playhead position in seconds."""
        total_duration = self.get_total_duration_s()
        if self.mode == "instant":
            return total_duration
        elif self.mode == "1x":
            if self._start_wall_time is None:
                return 0.0
            elapsed = time.monotonic() - self._start_wall_time
            return min(total_duration, elapsed)
        elif self.mode == "stepped":
            return min(total_duration, self._stepped_time_s)
        return total_duration

    def get_reference_tap(self) -> bytes:
        """Get played PCM audio bytes up to current playhead position."""
        playhead_s = self.get_playhead_position()
        if playhead_s <= 0.0 or not self.recorded_frames:
            return b""

        tap_bytes = bytearray()
        accumulated_s = 0.0

        for frame in self.recorded_frames:
            frame_dur_s = frame.duration_ms / 1000.0
            if frame_dur_s <= 0.0:
                continue

            bytes_per_sec = (frame.sample_rate * frame.channels * frame.sample_width)
            sample_alignment = frame.channels * frame.sample_width

            if accumulated_s + frame_dur_s <= playhead_s:
                tap_bytes.extend(frame.data)
                accumulated_s += frame_dur_s
            else:
                remaining_s = playhead_s - accumulated_s
                target_bytes = int(round(remaining_s * bytes_per_sec))
                # Align target_bytes to sample boundary
                if sample_alignment > 0:
                    target_bytes = (target_bytes // sample_alignment) * sample_alignment
                target_bytes = max(0, min(len(frame.data), target_bytes))
                tap_bytes.extend(frame.data[:target_bytes])
                break

        return bytes(tap_bytes)


class FakeAudioSource(AudioSource):
    """Test double for AudioSource hardware input streaming."""

    def __init__(
        self,
        pcm_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        realtime: bool = False,
    ) -> None:
        self.pcm_data = pcm_data
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.realtime = realtime
        self._started = False

    def start(self) -> None:
        """Start capturing audio."""
        self._started = True

    def stop(self) -> None:
        """Stop capturing audio."""
        self._started = False

    async def read_frames(self, frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]:
        """Yield AudioFrame chunks of frame_duration_ms from pcm_data."""
        if not self._started:
            self.start()

        bytes_per_ms = (self.sample_rate * self.channels * self.sample_width) / 1000.0
        frame_bytes_size = int(bytes_per_ms * frame_duration_ms)
        sample_alignment = self.channels * self.sample_width
        if sample_alignment > 0:
            frame_bytes_size = (frame_bytes_size // sample_alignment) * sample_alignment

        if frame_bytes_size <= 0:
            return

        offset = 0
        total_len = len(self.pcm_data)
        timestamp_ms = 0.0

        while self._started and offset < total_len:
            chunk = self.pcm_data[offset : offset + frame_bytes_size]
            offset += len(chunk)

            # Zero-pad trailing incomplete frame
            if len(chunk) < frame_bytes_size:
                chunk = chunk + b"\x00" * (frame_bytes_size - len(chunk))

            frame = AudioFrame(
                data=chunk,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=self.sample_width,
                timestamp_ms=timestamp_ms,
            )
            timestamp_ms += frame_duration_ms
            yield frame

            if self.realtime and self._started:
                await asyncio.sleep(frame_duration_ms / 1000.0)


class FakeSTT(STT):
    """Test double for Speech-To-Text engine."""

    def __init__(
        self,
        canned_transcriptions: list[STTResult] | list[str] | None = None,
        default_text: str = "Fake transcription",
    ) -> None:
        self.canned_transcriptions = canned_transcriptions
        self.default_text = default_text
        self.transcribed_stream_count = 0
        self.is_warmed_up = False

    def warmup(self) -> None:
        """Pre-warm or load model resources."""
        self.is_warmed_up = True

    async def transcribe_stream(
        self, audio_stream: AsyncIterable[AudioFrame]
    ) -> AsyncIterator[STTResult]:
        """Consume audio stream and yield canned or default STT results."""
        # Consume stream
        async for _ in audio_stream:
            pass

        self.transcribed_stream_count += 1

        if self.canned_transcriptions:
            for item in self.canned_transcriptions:
                if isinstance(item, STTResult):
                    yield item
                else:
                    yield STTResult(text=str(item), is_final=True)
        else:
            yield STTResult(text=self.default_text, is_final=True)


class FakeTTS(TTS):
    """Test double for Text-To-Speech engine."""

    def __init__(
        self,
        frame_duration_ms: int = 20,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        self.frame_duration_ms = frame_duration_ms
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.synthesized_texts: list[str] = []
        self.is_warmed_up = False

    def warmup(self) -> None:
        """Pre-warm model resources."""
        self.is_warmed_up = True

    async def synthesize(
        self, text: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioFrame]:
        """Synthesize input text into a sequence of AudioFrame objects."""
        self.synthesized_texts.append(text)
        num_frames = max(1, len(text) // 5)
        frame_bytes_size = int(
            (self.sample_rate * self.channels * self.sample_width)
            * (self.frame_duration_ms / 1000.0)
        )

        for i in range(num_frames):
            yield AudioFrame(
                data=b"\x00" * frame_bytes_size,
                sample_rate=self.sample_rate,
                channels=self.channels,
                sample_width=self.sample_width,
                timestamp_ms=float(i * self.frame_duration_ms),
            )


class FakeWakeWord(WakeWord):
    """Test double for Wake Word detection engine."""

    def __init__(
        self,
        target_keyword: str = "hey_paaf",
        always_detect: bool = False,
    ) -> None:
        self.target_keyword = target_keyword
        self.always_detect = always_detect
        self._triggered = False
        self._triggered_keyword: str | None = None
        self.is_warmed_up = False

    def warmup(self) -> None:
        """Pre-warm model resources."""
        self.is_warmed_up = True

    def trigger(self, keyword: str | None = None) -> None:
        """Manually trigger wake word detection for the next frame."""
        self._triggered = True
        self._triggered_keyword = keyword or self.target_keyword

    def reset(self) -> None:
        """Reset manual trigger state."""
        self._triggered = False
        self._triggered_keyword = None

    def detect(self, frame: AudioFrame) -> WakeWordResult:
        """Detect wake word in an AudioFrame."""
        if self.always_detect or self._triggered:
            kw = self._triggered_keyword or self.target_keyword
            self._triggered = False
            return WakeWordResult(detected=True, keyword=kw, confidence=1.0)
        return WakeWordResult(detected=False, keyword=None, confidence=0.0)


class FakeVAD(VAD):
    """Test double for Voice Activity Detection engine."""

    def __init__(
        self,
        speech_timeline: list[bool] | None = None,
        default_speech: bool = True,
    ) -> None:
        self.timeline = list(speech_timeline) if speech_timeline is not None else []
        self.default_speech = default_speech
        self.is_warmed_up = False

    def warmup(self) -> None:
        """Pre-warm model resources."""
        self.is_warmed_up = True

    def set_timeline(self, timeline: list[bool]) -> None:
        """Set a sequence of boolean flags for voice activity detection."""
        self.timeline = list(timeline)

    def process_frame(self, frame: AudioFrame) -> VADResult:
        """Process AudioFrame for voice activity."""
        if self.timeline:
            is_speech = self.timeline.pop(0)
        else:
            is_speech = self.default_speech
        return VADResult(is_speech=is_speech, confidence=1.0 if is_speech else 0.0)

