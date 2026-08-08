# SPDX-License-Identifier: Apache-2.0
"""Fake implementations of voice hardware ports for testing."""

import asyncio
from collections.abc import AsyncIterator
import time
from typing import Literal

from paaf_voice.ports import AudioFrame, AudioSink, AudioSource


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
