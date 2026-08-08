# SPDX-License-Identifier: Apache-2.0
"""PAAF voice package."""

from paaf_voice.ports import (
    STT,
    TTS,
    VAD,
    AudioFrame,
    AudioSink,
    AudioSource,
    STTResult,
    VADResult,
    WakeWord,
    WakeWordResult,
)

__version__ = "0.1.0"

__all__ = [
    "AudioFrame",
    "STTResult",
    "WakeWordResult",
    "VADResult",
    "AudioSource",
    "AudioSink",
    "STT",
    "TTS",
    "WakeWord",
    "VAD",
]
