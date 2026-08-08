# SPDX-License-Identifier: Apache-2.0
"""Tests for WAV file fixtures and audio generator utilities."""

import io
from pathlib import Path
import wave
import pytest

from paaf_voice.testing import (
    FakeAudioSink,
    FakeAudioSource,
    create_wav_bytes,
    generate_pcm_sine_bytes,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "wav"


def test_static_wav_fixtures_headers():
    silence_path = FIXTURES_DIR / "silence_16k_1s.wav"
    tone_path = FIXTURES_DIR / "tone_440hz_16k_1s.wav"

    assert silence_path.exists()
    assert tone_path.exists()

    with wave.open(str(silence_path), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 16000

    with wave.open(str(tone_path), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 16000


@pytest.mark.asyncio
async def test_wav_fixture_streaming_pipeline():
    silence_path = FIXTURES_DIR / "silence_16k_1s.wav"
    with wave.open(str(silence_path), "rb") as w:
        pcm_bytes = w.readframes(w.getnframes())

    source = FakeAudioSource(pcm_data=pcm_bytes, sample_rate=16000)
    sink = FakeAudioSink(mode="instant")

    async for frame in source.read_frames(frame_duration_ms=20):
        sink.write_frame(frame)

    assert sink.get_playhead_position() == 1.0
    assert len(sink.recorded_frames) == 50  # 1.0s / 0.02s = 50 frames


def test_programmatic_audio_generators():
    pcm = generate_pcm_sine_bytes(duration_s=0.5, frequency=440.0, sample_rate=16000)
    # 0.5s * 16000 samples/s * 2 bytes/sample = 16000 bytes
    assert len(pcm) == 16000

    wav_buf = create_wav_bytes(pcm, sample_rate=16000, channels=1, sample_width=2)
    with wave.open(io.BytesIO(wav_buf), "rb") as w:
        assert w.getframerate() == 16000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 8000
