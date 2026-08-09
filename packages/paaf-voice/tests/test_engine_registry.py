# SPDX-License-Identifier: Apache-2.0
"""Unit tests for paaf_voice.engines.registry."""

from collections.abc import AsyncIterable, AsyncIterator

import pytest
from paaf_voice.engines.registry import (
    _STT_REGISTRY,
    _TTS_REGISTRY,
    _VAD_REGISTRY,
    _WAKE_REGISTRY,
    create_stt_engine,
    create_tts_engine,
    create_vad_engine,
    create_wake_engine,
    get_engine_for_language,
    list_stt_engines,
    list_tts_engines,
    list_vad_engines,
    list_wake_engines,
    register_stt_engine,
    register_tts_engine,
    register_vad_engine,
    register_wake_engine,
)
from paaf_voice.ports import (
    STT,
    TTS,
    VAD,
    AudioFrame,
    STTResult,
    VADResult,
    WakeWord,
    WakeWordResult,
)


@pytest.fixture(autouse=True)
def clean_registry():
    saved_stt = dict(_STT_REGISTRY)
    saved_tts = dict(_TTS_REGISTRY)
    saved_wake = dict(_WAKE_REGISTRY)
    saved_vad = dict(_VAD_REGISTRY)
    yield
    _STT_REGISTRY.clear()
    _STT_REGISTRY.update(saved_stt)
    _TTS_REGISTRY.clear()
    _TTS_REGISTRY.update(saved_tts)
    _WAKE_REGISTRY.clear()
    _WAKE_REGISTRY.update(saved_wake)
    _VAD_REGISTRY.clear()
    _VAD_REGISTRY.update(saved_vad)


class DummySTT(STT):
    def __init__(self, model: str = "default"):
        self.model = model

    async def transcribe_stream(
        self, audio_stream: AsyncIterable[AudioFrame]
    ) -> AsyncIterator[STTResult]:
        yield STTResult(text="test")

    def warmup(self) -> None:
        pass


class DummyTTS(TTS):
    def __init__(self, voice: str = "default"):
        self.voice = voice

    async def synthesize(
        self, text: str, voice_id: str | None = None
    ) -> AsyncIterator[AudioFrame]:
        yield AudioFrame(data=b"\x00\x00")

    def warmup(self) -> None:
        pass


class DummyWake(WakeWord):
    def __init__(self, sensitivity: float = 0.5):
        self.sensitivity = sensitivity

    def detect(self, frame: AudioFrame) -> WakeWordResult:
        return WakeWordResult(detected=False)

    def warmup(self) -> None:
        pass


class DummyVAD(VAD):
    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold

    def process_frame(self, frame: AudioFrame) -> VADResult:
        return VADResult(is_speech=False)

    def warmup(self) -> None:
        pass


def test_register_and_create_stt_engine():
    @register_stt_engine("dummy_stt")
    class TestSTT(DummySTT):
        pass

    assert "dummy_stt" in list_stt_engines()
    instance = create_stt_engine("dummy_stt", model="custom-model")
    assert isinstance(instance, TestSTT)
    assert instance.model == "custom-model"


def test_register_and_create_tts_engine():
    @register_tts_engine("dummy_tts")
    class TestTTS(DummyTTS):
        pass

    assert "dummy_tts" in list_tts_engines()
    instance = create_tts_engine("dummy_tts", voice="female_1")
    assert isinstance(instance, TestTTS)
    assert instance.voice == "female_1"


def test_register_and_create_wake_engine():
    @register_wake_engine("dummy_wake")
    class TestWake(DummyWake):
        pass

    assert "dummy_wake" in list_wake_engines()
    instance = create_wake_engine("dummy_wake", sensitivity=0.8)
    assert isinstance(instance, TestWake)
    assert instance.sensitivity == 0.8


def test_register_and_create_vad_engine():
    @register_vad_engine("dummy_vad")
    class TestVAD(DummyVAD):
        pass

    assert "dummy_vad" in list_vad_engines()
    instance = create_vad_engine("dummy_vad", threshold=0.7)
    assert isinstance(instance, TestVAD)
    assert instance.threshold == 0.7


def test_invalid_engine_name_rejection():
    with pytest.raises(ValueError, match="Engine name must match pattern"):
        register_stt_engine("Invalid Engine Name!")

    with pytest.raises(ValueError, match="Engine name must match pattern"):
        register_tts_engine("engine;eval(code)")


def test_unknown_engine_error():
    @register_stt_engine("known_stt")
    class KnownSTT(DummySTT):
        pass

    with pytest.raises(ValueError, match="Unknown STT engine 'unknown_stt'"):
        create_stt_engine("unknown_stt")


def test_get_engine_for_language():
    default_engine = "faster_whisper"
    overrides = {"he": "whisper_cpp", "ru": "faster_whisper"}

    assert get_engine_for_language("en", default_engine, overrides) == "faster_whisper"
    assert get_engine_for_language("he", default_engine, overrides) == "whisper_cpp"
    assert get_engine_for_language("ru", default_engine, overrides) == "faster_whisper"
    assert get_engine_for_language("fr", default_engine, None) == "faster_whisper"
