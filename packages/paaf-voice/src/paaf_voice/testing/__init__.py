# SPDX-License-Identifier: Apache-2.0
"""Test doubles and utilities for paaf-voice."""

from paaf_voice.testing.fakes import (
    FakeSTT,
    FakeTTS,
    FakeVAD,
    FakeAudioSink,
    FakeAudioSource,
    FakeWakeWord,
)
from paaf_voice.testing.generators import create_wav_bytes, generate_pcm_sine_bytes

__all__ = [
    "FakeAudioSink",
    "FakeAudioSource",
    "FakeSTT",
    "FakeTTS",
    "FakeWakeWord",
    "FakeVAD",
    "generate_pcm_sine_bytes",
    "create_wav_bytes",
]
