# SPDX-License-Identifier: Apache-2.0
"""PAAF voice package."""

from paaf_voice.aggregator import AggregatorConfig, SentenceAggregator
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
    "TTSSanitizer",
    "SentenceAggregator",
    "AggregatorConfig",
]
