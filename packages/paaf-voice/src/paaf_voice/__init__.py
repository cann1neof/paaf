# SPDX-License-Identifier: Apache-2.0
"""PAAF voice package."""

from paaf_voice.aggregator import AggregatorConfig, SentenceAggregator
from paaf_voice.exceptions import ModelMissingError, VoiceError, verify_model_present
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
from paaf_voice.sanitizer import TTSSanitizer

__version__ = "0.1.0"

__all__ = [
    "STT",
    "TTS",
    "VAD",
    "AggregatorConfig",
    "AudioFrame",
    "AudioSink",
    "AudioSource",
    "ModelMissingError",
    "STTResult",
    "SentenceAggregator",
    "TTSSanitizer",
    "VADResult",
    "VoiceError",
    "WakeWord",
    "WakeWordResult",
    "verify_model_present",
]

