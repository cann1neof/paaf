# SPDX-License-Identifier: Apache-2.0
"""Unit tests for OpenWakeWordEngine and SileroVADEngine adapters."""

import io
import wave
from unittest.mock import MagicMock

import pytest
from paaf_voice.engines import (
    OpenWakeWordEngine,
    SileroVADEngine,
    create_vad_engine,
    create_wake_engine,
    list_vad_engines,
    list_wake_engines,
)
from paaf_voice.ports import AudioFrame, VADResult, WakeWordResult


def generate_pcm_frame(
    duration_ms: float = 20.0, sample_rate: int = 16000
) -> AudioFrame:
    """Generate raw 16-bit PCM AudioFrame for testing."""
    num_samples = int((duration_ms / 1000.0) * sample_rate)
    pcm_data = b"\x00\x00" * num_samples
    return AudioFrame(
        data=pcm_data,
        sample_rate=sample_rate,
        channels=1,
        sample_width=2,
    )


def generate_wav_bytes(
    duration_ms: float = 100.0, sample_rate: int = 16000
) -> bytes:
    """Generate in-memory WAV audio file bytes for testing."""
    num_samples = int((duration_ms / 1000.0) * sample_rate)
    pcm_data = b"\x00\x00" * num_samples

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()


def test_engine_registrations():
    """Verify openwakeword and silero engines are correctly registered."""
    wake_engines = list_wake_engines()
    assert "openwakeword" in wake_engines

    vad_engines = list_vad_engines()
    assert "silero" in vad_engines


def test_create_wake_engine():
    """Verify factory function instantiates OpenWakeWordEngine correctly."""
    wake_engine = create_wake_engine(
        "openwakeword", model_path_or_name="alexa", threshold=0.7
    )
    assert isinstance(wake_engine, OpenWakeWordEngine)
    assert wake_engine.model_path_or_name == "alexa"
    assert wake_engine.threshold == 0.7


def test_create_vad_engine():
    """Verify factory function instantiates SileroVADEngine correctly."""
    vad_engine = create_vad_engine(
        "silero",
        speech_threshold_idle=0.45,
        speech_threshold_playback=0.70,
    )
    assert isinstance(vad_engine, SileroVADEngine)
    assert vad_engine.speech_threshold_idle == 0.45
    assert vad_engine.speech_threshold_playback == 0.70


def test_openwakeword_detection():
    """Verify openWakeWord detection with mock model predictions."""
    mock_model = MagicMock()
    mock_model.predict.return_value = {"hey_jarvis": 0.82}

    engine = OpenWakeWordEngine(
        model_path_or_name="hey_jarvis", threshold=0.5, model=mock_model
    )
    engine.warmup()
    assert engine._is_warmed_up is True

    frame = generate_pcm_frame(duration_ms=20.0)
    result = engine.detect(frame)

    assert isinstance(result, WakeWordResult)
    assert result.detected is True
    assert result.keyword == "hey_jarvis"
    assert pytest.approx(result.confidence, 0.01) == 0.82

    # Test detection below threshold
    mock_model.predict.return_value = {"hey_jarvis": 0.35}
    low_result = engine.detect(frame)
    assert low_result.detected is False
    assert pytest.approx(low_result.confidence, 0.01) == 0.35


def test_openwakeword_missing_dependency():
    """Verify ImportError when openwakeword is not installed."""
    engine = OpenWakeWordEngine(model=None)
    with pytest.raises(ImportError, match="openwakeword package is required"):
        engine._ensure_model()


def test_silero_vad_dual_threshold_switching():
    """Verify continuous dual-threshold VAD switching between idle and playback active."""
    mock_model = MagicMock()
    # Mock model run returns probability output
    mock_model.run.return_value = [0.58]

    vad_engine = SileroVADEngine(
        speech_threshold_idle=0.50,
        speech_threshold_playback=0.65,
        model=mock_model,
    )
    vad_engine.warmup()
    assert vad_engine._is_warmed_up is True

    # 1. Idle mode: threshold is 0.50. Probability 0.58 >= 0.50 -> speech detected
    assert vad_engine.current_threshold == 0.50
    frame = generate_pcm_frame(duration_ms=20.0)
    res_idle = vad_engine.process_frame(frame)
    assert isinstance(res_idle, VADResult)
    assert res_idle.is_speech is True
    assert pytest.approx(res_idle.confidence, 0.01) == 0.58

    # 2. Switch to active playback mode: threshold becomes 0.65.
    vad_engine.set_playback_active(True)
    assert vad_engine.current_threshold == 0.65

    # Same speech probability 0.58 < 0.65 -> NOT detected as speech (prevents playback bleed trigger)
    res_playback = vad_engine.process_frame(frame)
    assert res_playback.is_speech is False
    assert pytest.approx(res_playback.confidence, 0.01) == 0.58

    # 3. Switch back to idle mode: threshold reverts to 0.50
    vad_engine.set_playback_active(False)
    assert vad_engine.current_threshold == 0.50
    res_revert = vad_engine.process_frame(frame)
    assert res_revert.is_speech is True


def test_silero_vad_missing_dependency():
    """Verify error handling for missing model or dependency in SileroVADEngine."""
    engine = SileroVADEngine(model=None, model_path=None)
    with pytest.raises((ValueError, ImportError)):
        engine._ensure_model()
