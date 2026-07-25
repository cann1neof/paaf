# SPDX-License-Identifier: Apache-2.0
"""Test doubles for ``paaf_trace`` (underscore-private: not part of the public API).

Currently exposes :class:`~paaf_trace._testing.fake_tts.FakeTTS`, a fake TTS engine used
by the TTFA regression gate (TRACE-04) to measure ``time_to_first_audio`` accurately on a
deterministic clock before any real audio engine exists.
"""

from __future__ import annotations

from .fake_tts import FakeTTS

__all__ = ["FakeTTS"]
