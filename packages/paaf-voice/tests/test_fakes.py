# SPDX-License-Identifier: Apache-2.0
"""Tests for paaf_voice hardware test doubles."""

import pytest

from paaf_voice.ports import AudioFrame
from paaf_voice.testing import FakeAudioSink, FakeAudioSource


def test_fake_audio_sink_instant_mode():
    sink = FakeAudioSink(mode="instant")

    # Write two 20ms frames (640 bytes each)
    frame1 = AudioFrame(data=b"\x01" * 640, sample_rate=16000, channels=1, sample_width=2)
    frame2 = AudioFrame(data=b"\x02" * 640, sample_rate=16000, channels=1, sample_width=2)

    sink.write_frame(frame1)
    sink.write_frame(frame2)

    assert len(sink.recorded_frames) == 2
    assert sink.get_playhead_position() == 0.04  # 40ms = 0.04s
    assert sink.get_reference_tap() == (b"\x01" * 640 + b"\x02" * 640)


def test_fake_audio_sink_stepped_mode():
    sink = FakeAudioSink(mode="stepped")

    frame1 = AudioFrame(data=b"\x01" * 640, sample_rate=16000, channels=1, sample_width=2)
    frame2 = AudioFrame(data=b"\x02" * 640, sample_rate=16000, channels=1, sample_width=2)

    sink.write_frame(frame1)
    sink.write_frame(frame2)

    # Initial position in stepped mode before step()
    assert sink.get_playhead_position() == 0.0
    assert sink.get_reference_tap() == b""

    # Step by 10ms (0.01s)
    sink.step(10)
    assert sink.get_playhead_position() == 0.01
    # 10ms @ 16kHz 16-bit mono = 320 bytes
    assert sink.get_reference_tap() == b"\x01" * 320

    # Step by another 20ms -> total 30ms (0.03s)
    sink.step(20)
    assert sink.get_playhead_position() == 0.03
    # 30ms = 640 bytes (frame1) + 320 bytes (half of frame2)
    assert sink.get_reference_tap() == (b"\x01" * 640 + b"\x02" * 320)

    # Step beyond total written (e.g. total written = 40ms = 0.04s)
    sink.step(50)
    assert sink.get_playhead_position() == 0.04
    assert sink.get_reference_tap() == (b"\x01" * 640 + b"\x02" * 640)


@pytest.mark.asyncio
async def test_fake_audio_source_reading():
    # 1000 bytes of PCM audio
    raw_pcm = bytes(range(256)) * 4  # 1024 bytes
    source = FakeAudioSource(pcm_data=raw_pcm, sample_rate=16000, channels=1, sample_width=2)

    frames = []
    async for frame in source.read_frames(frame_duration_ms=20):
        frames.append(frame)

    # 1024 bytes with 640 bytes per 20ms frame:
    # Frame 1: 640 bytes
    # Frame 2: 384 bytes + 256 bytes zero-padding = 640 bytes
    assert len(frames) == 2
    assert len(frames[0].data) == 640
    assert len(frames[1].data) == 640
    assert frames[0].duration_ms == 20.0
    assert frames[1].duration_ms == 20.0
    assert frames[1].data[384:] == b"\x00" * 256


@pytest.mark.asyncio
async def test_fake_audio_source_stop():
    raw_pcm = b"\x00" * 1280
    source = FakeAudioSource(pcm_data=raw_pcm)

    frames = []
    source.start()
    async for frame in source.read_frames():
        frames.append(frame)
        source.stop()

    # Should have stopped after yielding 1 frame
    assert len(frames) == 1
