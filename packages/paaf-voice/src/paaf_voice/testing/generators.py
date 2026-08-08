# SPDX-License-Identifier: Apache-2.0
"""Synthetic audio generators and WAV buffer utilities for testing."""

import io
import math
import struct
import wave


def generate_pcm_sine_bytes(
    duration_s: float,
    frequency: float = 440.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
) -> bytes:
    """Generate raw 16-bit signed mono PCM sine wave bytes."""
    num_samples = int(sample_rate * duration_s)
    pcm_bytes = bytearray()
    max_amplitude = 32767 * amplitude

    for i in range(num_samples):
        sample_val = int(max_amplitude * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
        # Clamp to 16-bit signed int range
        sample_val = max(-32768, min(32767, sample_val))
        pcm_bytes.extend(struct.pack("<h", sample_val))

    return bytes(pcm_bytes)


def create_wav_bytes(
    pcm_data: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw PCM bytes into a valid RIFF WAV header buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_out:
        wav_out.setnchannels(channels)
        wav_out.setsampwidth(sample_width)
        wav_out.setframerate(sample_rate)
        wav_out.writeframes(pcm_data)
    return buf.getvalue()
