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

__all__ = [
    "FakeAudioSink",
    "FakeAudioSource",
    "FakeSTT",
    "FakeTTS",
    "FakeWakeWord",
    "FakeVAD",
]
