# SPDX-License-Identifier: Apache-2.0
"""Unit tests for STT engine adapters (FasterWhisperSTT and WhisperCppSTT)."""

import io
import wave
from unittest.mock import MagicMock

import pytest
from paaf_voice.engines import (
    FasterWhisperSTT,
    WhisperCppSTT,
    create_stt_engine,
    list_stt_engines,
)
from paaf_voice.ports import AudioFrame, STTResult


def generate_wav_bytes(duration_ms: float = 100.0, sample_rate: int = 16000) -> bytes:
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


def test_stt_engine_registration():
    stt_engines = list_stt_engines()
    assert "faster_whisper" in stt_engines
    assert "whisper_cpp" in stt_engines


def test_create_stt_engines():
    fw_engine = create_stt_engine("faster_whisper", model_size_or_path="tiny")
    assert isinstance(fw_engine, FasterWhisperSTT)
    assert fw_engine.model_size_or_path == "tiny"

    cpp_engine = create_stt_engine("whisper_cpp", model_path="ggml-tiny.bin")
    assert isinstance(cpp_engine, WhisperCppSTT)
    assert cpp_engine.model_path == "ggml-tiny.bin"


@pytest.mark.asyncio
async def test_faster_whisper_warmup_and_transcribe():
    mock_model = MagicMock()

    mock_segment = MagicMock()
    mock_segment.text = " Hello world "

    mock_info = MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.98

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    engine = FasterWhisperSTT(model=mock_model)
    engine.warmup()
    assert engine._is_warmed_up is True
    assert mock_model.transcribe.called

    mock_model.transcribe.reset_mock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    async def sample_stream():
        yield AudioFrame(data=b"\x00\x00" * 320, sample_rate=16000)
        yield AudioFrame(data=b"\x00\x00" * 320, sample_rate=16000)

    results: list[STTResult] = []
    async for res in engine.transcribe_stream(sample_stream()):
        results.append(res)

    assert len(results) == 1
    assert results[0].text == "Hello world"
    assert results[0].language == "en"
    assert results[0].is_final is True
    assert pytest.approx(results[0].confidence, 0.01) == 0.98


@pytest.mark.asyncio
async def test_whisper_cpp_warmup_and_transcribe():
    mock_model = MagicMock()

    mock_segment = MagicMock()
    mock_segment.text = " Testing whisper cpp "
    mock_segment.language = "he"

    mock_info = MagicMock()
    mock_info.language = "he"
    mock_info.language_probability = 0.95

    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    engine = WhisperCppSTT(model=mock_model)
    engine.warmup()
    assert engine._is_warmed_up is True
    assert mock_model.transcribe.called

    mock_model.transcribe.reset_mock()
    mock_model.transcribe.return_value = ([mock_segment], mock_info)

    async def sample_stream():
        yield AudioFrame(data=b"\x00\x00" * 320, sample_rate=16000)

    results: list[STTResult] = []
    async for res in engine.transcribe_stream(sample_stream()):
        results.append(res)

    assert len(results) == 1
    assert results[0].text == "Testing whisper cpp"
    assert results[0].language == "he"
    assert results[0].is_final is True


def test_missing_package_error():
    engine_fw = FasterWhisperSTT(model=None)
    with pytest.raises(ImportError, match="faster-whisper package is required"):
        engine_fw._ensure_model()

    engine_cpp = WhisperCppSTT(model=None)
    with pytest.raises(ImportError, match="pywhispercpp package is required"):
        engine_cpp._ensure_model()
