# SPDX-License-Identifier: Apache-2.0
"""Unit tests for sounddevice audio hardware I/O, resampling, and device management (VOICE-09)."""

import asyncio
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import pytest

from paaf_voice.audio import SoundDeviceAudioSink, SoundDeviceAudioSource
from paaf_voice.cli import get_audio_devices, list_devices_cmd, voice_cli
from paaf_voice.ports import AudioFrame, AudioSink, AudioSource


def test_audio_source_sink_protocols() -> None:
    """Verify SoundDeviceAudioSource and SoundDeviceAudioSink satisfy port protocols."""
    source = SoundDeviceAudioSource()
    sink = SoundDeviceAudioSink()

    assert isinstance(source, AudioSource)
    assert isinstance(sink, AudioSink)


@pytest.mark.asyncio
async def test_sounddevice_audio_source_streaming() -> None:
    """Verify SoundDeviceAudioSource accumulates raw PCM data and yields 20ms 16kHz frames."""
    source = SoundDeviceAudioSource(sample_rate=16000, channels=1, sample_width=2)
    source.start()

    # Push 60ms of raw PCM data into queue manually (3 frames of 20ms = 320 samples each = 640 bytes each = 1920 bytes)
    sample_frame_bytes = b"\x01\x02" * 320
    source._queue.put(sample_frame_bytes * 3)

    collected_frames = []
    async for frame in source.read_frames(frame_duration_ms=20):
        collected_frames.append(frame)
        if len(collected_frames) == 3:
            source.stop()

    assert len(collected_frames) == 3
    assert collected_frames[0].data == sample_frame_bytes
    assert collected_frames[0].duration_ms == 20.0
    assert collected_frames[0].timestamp_ms == 0.0
    assert collected_frames[1].timestamp_ms == 20.0
    assert collected_frames[2].timestamp_ms == 40.0


def test_sounddevice_audio_sink_resampling_and_playhead() -> None:
    """Verify SoundDeviceAudioSink resamples frames, tracks playhead position, and manages reference tap."""
    sink = SoundDeviceAudioSink(target_sample_rate=48000, channels=1, sample_width=2)
    sink.start()

    assert sink.get_playhead_position() == 0.0
    assert sink.get_reference_tap() == b""

    # Write a 20ms 16kHz frame (320 samples = 640 bytes)
    frame_16k = AudioFrame(
        data=b"\x00\x00" * 320,
        sample_rate=16000,
        channels=1,
        sample_width=2,
    )
    sink.write_frame(frame_16k)

    # 16kHz resampled to 48kHz (3x factor) -> 960 samples = 1920 bytes
    # Playhead position: 960 / 48000 = 0.02 seconds (20ms)
    assert sink.get_playhead_position() == pytest.approx(0.02, abs=1e-4)

    tap_bytes = sink.get_reference_tap()
    assert len(tap_bytes) == 960 * 2  # 1920 bytes
    # After draining, reference tap is empty
    assert sink.get_reference_tap() == b""

    sink.stop()


def test_sounddevice_audio_sink_max_tap_bytes() -> None:
    """Verify SoundDeviceAudioSink truncates reference tap buffer at max_tap_bytes bound."""
    sink = SoundDeviceAudioSink(
        target_sample_rate=16000,
        channels=1,
        sample_width=2,
        max_tap_bytes=1000,
    )
    # Write frame larger than max_tap_bytes (1000 samples = 2000 bytes)
    frame = AudioFrame(
        data=b"\x05\x05" * 1000,
        sample_rate=16000,
        channels=1,
        sample_width=2,
    )
    sink.write_frame(frame)

    tap_bytes = sink.get_reference_tap()
    assert len(tap_bytes) == 1000


def test_get_audio_devices_mocked() -> None:
    """Verify get_audio_devices formats sounddevice query_devices result."""
    mock_devices = [
        {
            "name": "Built-in Microphone",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
            "is_default_input": True,
            "is_default_output": False,
        },
        {
            "name": "Built-in Speakers",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
            "is_default_input": False,
            "is_default_output": True,
        },
    ]

    mock_sd = MagicMock()
    mock_sd.query_devices.return_value = mock_devices

    with patch.dict("sys.modules", {"sounddevice": mock_sd}):
        devs = get_audio_devices()

    assert len(devs) == 2
    assert devs[0]["name"] == "Built-in Microphone"
    assert devs[0]["max_input_channels"] == 2
    assert devs[0]["is_default_input"] is True
    assert devs[1]["name"] == "Built-in Speakers"
    assert devs[1]["max_output_channels"] == 2
    assert devs[1]["is_default_output"] is True


def test_list_devices_cli_command() -> None:
    """Verify paaf voice list-devices CLI subcommand output formatting."""
    runner = CliRunner()
    mock_devices = [
        {
            "name": "USB Mic",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 16000.0,
            "is_default_input": True,
            "is_default_output": False,
        }
    ]

    with patch("paaf_voice.cli.devices.get_audio_devices", return_value=mock_devices):
        result = runner.invoke(voice_cli, ["list-devices"])

    assert result.exit_code == 0
    assert "Connected Audio Hardware Devices" in result.output
    assert "USB Mic" in result.output
    assert "Default Input" in result.output
