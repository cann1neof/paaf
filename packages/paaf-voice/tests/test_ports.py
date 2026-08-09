# SPDX-License-Identifier: Apache-2.0
"""Tests for paaf_voice core port protocols and value objects."""

import sys
from dataclasses import FrozenInstanceError

import pytest
from paaf_voice.ports import (
    AudioFrame,
    AudioSink,
    AudioSource,
    STTResult,
    VADResult,
    WakeWordResult,
)


def test_audio_frame_duration_and_immutability():
    # Standard 20ms frame: 16kHz, 16-bit (2 bytes/sample), mono (1 channel)
    # 16000 samples/s * 2 bytes/sample * 0.02s = 640 bytes
    data = b"\x00" * 640
    frame = AudioFrame(data=data, sample_rate=16000, channels=1, sample_width=2)
    assert frame.duration_ms == 20.0

    # Test frozen immutability
    with pytest.raises(FrozenInstanceError):
        frame.data = b"\x01" * 640  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        frame.sample_rate = 8000  # type: ignore[misc]


def test_audio_frame_invalid_params_guard():
    data = b"\x00" * 640
    frame_zero_sr = AudioFrame(data=data, sample_rate=0)
    assert frame_zero_sr.duration_ms == 0.0

    frame_neg_ch = AudioFrame(data=data, channels=-1)
    assert frame_neg_ch.duration_ms == 0.0

    frame_zero_sw = AudioFrame(data=data, sample_width=0)
    assert frame_zero_sw.duration_ms == 0.0


def test_result_objects_immutability():
    stt_res = STTResult(text="hello", confidence=0.95)
    assert stt_res.text == "hello"
    with pytest.raises(FrozenInstanceError):
        stt_res.text = "world"  # type: ignore[misc]

    ww_res = WakeWordResult(detected=True, keyword="alexa", confidence=0.99)
    assert ww_res.detected is True
    with pytest.raises(FrozenInstanceError):
        ww_res.detected = False  # type: ignore[misc]

    vad_res = VADResult(is_speech=True, confidence=0.8)
    assert vad_res.is_speech is True
    with pytest.raises(FrozenInstanceError):
        vad_res.is_speech = False  # type: ignore[misc]


def test_runtime_checkable_protocols():
    class DummySink:
        def write_frame(self, frame: AudioFrame) -> None:
            pass

        def get_playhead_position(self) -> float:
            return 0.0

        def get_reference_tap(self) -> bytes:
            return b""

    class DummySource:
        async def read_frames(self, frame_duration_ms: int = 20):
            yield AudioFrame(data=b"")

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    sink = DummySink()
    source = DummySource()

    assert isinstance(sink, AudioSink)
    assert isinstance(source, AudioSource)


def test_no_non_stdlib_imports_in_ports():
    import paaf_voice.ports as ports_module

    # Standard library module names (or internal)
    stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else set()
    
    # Verify imports in ports_module are stdlib or typing/collections
    for key, val in ports_module.__dict__.items():
        if hasattr(val, "__module__") and val.__module__ is not None:
            mod_root = val.__module__.split(".")[0]
            if mod_root not in ("typing", "collections", "dataclasses", "builtins", "paaf_voice"):
                if stdlib_modules:
                    assert mod_root in stdlib_modules, f"Non-stdlib import detected: {val.__module__}"
