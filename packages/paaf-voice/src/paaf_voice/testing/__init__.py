# SPDX-License-Identifier: Apache-2.0
"""Test doubles and utilities for paaf-voice."""

from paaf_voice.testing.fakes import (
    FakeAudioSink,
    FakeAudioSource,
    FakeSTT,
    FakeTTS,
    FakeVAD,
    FakeWakeWord,
)
from paaf_voice.testing.generators import create_wav_bytes, generate_pcm_sine_bytes

__all__ = [
    "FakeAudioSink",
    "FakeAudioSource",
    "FakeSTT",
    "FakeTTS",
    "FakeVAD",
    "FakeWakeWord",
    "create_wav_bytes",
    "generate_pcm_sine_bytes",
]
