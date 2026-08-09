# SPDX-License-Identifier: Apache-2.0
"""PAAF Voice Engine implementations and pluggable registry."""

from paaf_voice.engines.faster_whisper import FasterWhisperSTT
from paaf_voice.engines.openwakeword import OpenWakeWordEngine
from paaf_voice.engines.registry import (
    clear_registries,
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
from paaf_voice.engines.silero_vad import SileroVADEngine
from paaf_voice.engines.whisper_cpp import WhisperCppSTT

__all__ = [
    "FasterWhisperSTT",
    "OpenWakeWordEngine",
    "SileroVADEngine",
    "WhisperCppSTT",
    "clear_registries",
    "create_stt_engine",
    "create_tts_engine",
    "create_vad_engine",
    "create_wake_engine",
    "get_engine_for_language",
    "list_stt_engines",
    "list_tts_engines",
    "list_vad_engines",
    "list_wake_engines",
    "register_stt_engine",
    "register_tts_engine",
    "register_vad_engine",
    "register_wake_engine",
]
