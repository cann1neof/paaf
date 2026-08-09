# SPDX-License-Identifier: Apache-2.0
"""SoundDevice PortAudio implementation of AudioSource and AudioSink ports (VOICE-09)."""

import asyncio
import queue
import struct
import threading
from typing import Any, AsyncIterator

from paaf_voice.ports import AudioFrame, AudioSink, AudioSource


class SoundDeviceAudioSource(AudioSource):
    """Live microphone hardware audio source powered by sounddevice / PortAudio."""

    def __init__(
        self,
        device_index: int | str | None = None,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self._is_running = False
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._stream: Any = None
        self._elapsed_ms: float = 0.0
        self._accumulated_bytes = bytearray()

    def start(self) -> None:
        """Start capturing audio stream from microphone."""
        if self._is_running:
            return
        self._is_running = True
        self._elapsed_ms = 0.0
        self._accumulated_bytes.clear()

        try:
            import sounddevice as sd

            def callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    pass  # xrun or status warnings
                raw_bytes = indata.tobytes() if hasattr(indata, "tobytes") else bytes(indata)
                self._queue.put(raw_bytes)

            self._stream = sd.InputStream(
                device=self.device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                callback=callback,
            )
            self._stream.start()
        except ImportError:
            # sounddevice module not installed; fallback to mock queue behavior
            self._stream = None
        except Exception:
            # Audio device unavailable or headless host
            self._stream = None

    def stop(self) -> None:
        """Stop audio stream capture."""
        self._is_running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    async def read_frames(self, frame_duration_ms: int = 20) -> AsyncIterator[AudioFrame]:
        """Async generator reading PCM 16kHz audio frames."""
        bytes_per_sample = self.sample_width * self.channels
        samples_per_frame = int(self.sample_rate * (frame_duration_ms / 1000.0))
        target_bytes = samples_per_frame * bytes_per_sample

        while self._is_running:
            # Drain incoming raw bytes from sounddevice thread-safe queue
            drained = False
            while not self._queue.empty():
                try:
                    chunk = self._queue.get_nowait()
                    self._accumulated_bytes.extend(chunk)
                    drained = True
                except queue.Empty:
                    break

            while len(self._accumulated_bytes) >= target_bytes:
                frame_data = bytes(self._accumulated_bytes[:target_bytes])
                del self._accumulated_bytes[:target_bytes]
                ts = self._elapsed_ms
                self._elapsed_ms += frame_duration_ms
                yield AudioFrame(
                    data=frame_data,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    sample_width=self.sample_width,
                    timestamp_ms=ts,
                )

            if not drained:
                await asyncio.sleep(0.005)


class SoundDeviceAudioSink(AudioSink):
    """Live speaker hardware audio sink powered by sounddevice and soxr dynamic resampler."""

    def __init__(
        self,
        device_index: int | str | None = None,
        target_sample_rate: int = 48000,
        channels: int = 1,
        sample_width: int = 2,
        max_tap_bytes: int = 320000,
    ) -> None:
        self.device_index = device_index
        self.target_sample_rate = target_sample_rate
        self.channels = channels
        self.sample_width = sample_width
        self.max_tap_bytes = max_tap_bytes

        self._playhead_samples: int = 0
        self._reference_tap_buffer: bytearray = bytearray()
        self._lock = threading.Lock()
        self._stream: Any = None
        self._is_started = False

    def _ensure_stream(self) -> None:
        if self._stream is not None or not self._is_started:
            return
        try:
            import sounddevice as sd

            self._stream = sd.OutputStream(
                device=self.device_index,
                samplerate=self.target_sample_rate,
                channels=self.channels,
                dtype="int16",
            )
            self._stream.start()
        except Exception:
            self._stream = None

    def start(self) -> None:
        """Start output audio stream."""
        self._is_started = True
        self._ensure_stream()

    def stop(self) -> None:
        """Stop output audio stream."""
        self._is_started = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def resample_pcm(self, pcm_bytes: bytes, source_rate: int, target_rate: int) -> bytes:
        """Resample PCM 16-bit mono audio bytes using soxr or fallback resampling."""
        if source_rate == target_rate or not pcm_bytes:
            return pcm_bytes

        # Attempt soxr / numpy resampling
        try:
            import numpy as np
            import soxr

            audio_arr = np.frombuffer(pcm_bytes, dtype=np.int16)
            resampled_arr = soxr.resample(
                audio_arr, in_rate=source_rate, out_rate=target_rate
            )
            return resampled_arr.astype(np.int16).tobytes()
        except ImportError:
            pass

        # Pure Python fallback linear interpolation / sample replication
        num_samples_in = len(pcm_bytes) // 2
        if num_samples_in == 0:
            return b""
        in_samples = list(struct.unpack(f"<{num_samples_in}h", pcm_bytes))
        ratio = float(target_rate) / float(source_rate)
        num_samples_out = max(1, int(num_samples_in * ratio))
        out_samples = []
        for i in range(num_samples_out):
            src_idx = int(i / ratio)
            if src_idx >= num_samples_in:
                src_idx = num_samples_in - 1
            out_samples.append(in_samples[src_idx])
        return struct.pack(f"<{len(out_samples)}h", *out_samples)

    def write_frame(self, frame: AudioFrame) -> None:
        """Write an audio frame for speaker playback."""
        out_pcm = self.resample_pcm(
            frame.data,
            source_rate=frame.sample_rate,
            target_rate=self.target_sample_rate,
        )

        if not out_pcm:
            return

        # Write to physical soundcard if available
        self._ensure_stream()
        if self._stream is not None:
            try:
                import numpy as np

                arr = np.frombuffer(out_pcm, dtype=np.int16)
                self._stream.write(arr)
            except Exception:
                pass

        # Update playhead position in target samples
        resampled_samples = len(out_pcm) // (self.sample_width * self.channels)
        with self._lock:
            self._playhead_samples += resampled_samples
            # Append output PCM bytes to reference tap buffer for AEC
            self._reference_tap_buffer.extend(out_pcm)
            if len(self._reference_tap_buffer) > self.max_tap_bytes:
                excess = len(self._reference_tap_buffer) - self.max_tap_bytes
                del self._reference_tap_buffer[:excess]

    def get_playhead_position(self) -> float:
        """Get current playhead position in seconds."""
        with self._lock:
            if self.target_sample_rate <= 0:
                return 0.0
            return float(self._playhead_samples) / float(self.target_sample_rate)

    def get_reference_tap(self) -> bytes:
        """Get played audio buffer for acoustic echo cancellation (AEC) and drain buffer."""
        with self._lock:
            tap_bytes = bytes(self._reference_tap_buffer)
            self._reference_tap_buffer.clear()
            return tap_bytes
