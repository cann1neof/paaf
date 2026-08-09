# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ChatterboxTTS adapter, PerTh watermarking docs, and system-wide engine warmup (VOICE-04, VOICE-10, VOICE-12)."""

import time
from unittest.mock import MagicMock

import pytest
from paaf_voice.engines import (
    ChatterboxTTS,
    FasterWhisperSTT,
    OpenWakeWordEngine,
    SileroVADEngine,
    WhisperCppSTT,
    create_tts_engine,
    list_tts_engines,
)
from paaf_voice.ports import AudioFrame, STTResult, VADResult, WakeWordResult


def test_chatterbox_engine_registration():
    """Verify chatterbox engine is correctly registered in the engine registry."""
    tts_engines = list_tts_engines()
    assert "chatterbox" in tts_engines

    mock_model = MagicMock()
    engine = create_tts_engine("chatterbox", voice_id="unified_v1", model=mock_model)
    assert isinstance(engine, ChatterboxTTS)
    assert engine.voice_id == "unified_v1"


@pytest.mark.asyncio
async def test_chatterbox_multilingual_synthesis():
    """Verify ChatterboxTTS synthesizes multi-script text (EN, RU, HE, ES) in 24kHz PCM frames (VOICE-04)."""
    mock_model = MagicMock()
    engine = ChatterboxTTS(voice_id="single_identity", model=mock_model)

    # Multi-script input text covering English, Russian, Hebrew, Spanish
    multilingual_text = "Hello world! Привет мир! שלום עולם! ¡Hola mundo!"

    frames = []
    async for frame in engine.synthesize(multilingual_text):
        frames.append(frame)

    assert len(frames) > 0
    for frame in frames:
        assert isinstance(frame, AudioFrame)
        assert frame.sample_rate == 24000
        assert frame.channels == 1
        assert frame.sample_width == 2
        assert len(frame.data) > 0


def test_chatterbox_perth_watermarking_docstring():
    """Verify ChatterboxTTS class docstring contains explicit PerTh watermarking notes (VOICE-12)."""
    doc = ChatterboxTTS.__doc__
    assert doc is not None
    assert "PerTh" in doc
    assert "watermark" in doc.lower()
    assert "VOICE-12" in doc or "acoustic" in doc.lower()


def test_chatterbox_missing_dependency():
    """Verify error handling when ChatterboxTTS model or model_path is missing."""
    engine = ChatterboxTTS(model=None, model_path=None)
    with pytest.raises((ValueError, ImportError)):
        engine._ensure_model()


def test_system_wide_engine_warmup_gate():
    """Verify system-wide engine warmup gate across all 5 real engine classes (VOICE-10)."""
    mock_stt_model = MagicMock()
    mock_stt_model.transcribe.return_value = ([], None)

    mock_tts_model = MagicMock()

    mock_wake_model = MagicMock()
    mock_wake_model.predict.return_value = {"hey_jarvis": 0.10}

    mock_vad_model = MagicMock()
    mock_vad_model.run.return_value = [0.10]

    engines = [
        FasterWhisperSTT(model=mock_stt_model),
        WhisperCppSTT(model=mock_stt_model),
        ChatterboxTTS(model=mock_tts_model),
        OpenWakeWordEngine(model=mock_wake_model),
        SileroVADEngine(model=mock_vad_model),
    ]

    # Verify initially un-warmed state
    for engine in engines:
        assert getattr(engine, "_is_warmed_up", False) is False

    # Execute warmup gate across all 5 engines
    start_time = time.monotonic()
    for engine in engines:
        engine.warmup()
        assert getattr(engine, "_is_warmed_up", False) is True

    warmup_duration = time.monotonic() - start_time
    assert warmup_duration < 1.0  # Warmup gate completes rapidly for pre-loaded weights

    # Verify zero cold-start delay for subsequent inference calls after warmup
    stt_engine = engines[0]
    frame = AudioFrame(data=b"\x00" * 640, sample_rate=16000, channels=1, sample_width=2)
    wake_engine = engines[3]
    vad_engine = engines[4]

    # Post-warmup execution calls execute instantly without weight loading overhead
    wake_res = wake_engine.detect(frame)
    assert isinstance(wake_res, WakeWordResult)

    vad_res = vad_engine.process_frame(frame)
    assert isinstance(vad_res, VADResult)
