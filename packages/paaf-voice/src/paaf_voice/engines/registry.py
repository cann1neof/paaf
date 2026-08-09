# SPDX-License-Identifier: Apache-2.0
"""Dynamic engine registry and decorator framework for PAAF voice engines."""

import re
from collections.abc import Callable
from typing import TypeVar

from paaf_voice.ports import STT, TTS, VAD, WakeWord

_ENGINE_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")

_STT_REGISTRY: dict[str, type[STT]] = {}
_TTS_REGISTRY: dict[str, type[TTS]] = {}
_WAKE_REGISTRY: dict[str, type[WakeWord]] = {}
_VAD_REGISTRY: dict[str, type[VAD]] = {}

STTType = TypeVar("STTType", bound=type[STT])
TTSType = TypeVar("TTSType", bound=type[TTS])
WakeType = TypeVar("WakeType", bound=type[WakeWord])
VADType = TypeVar("VADType", bound=type[VAD])


def _validate_engine_name(name: str) -> None:
    """Validate engine name against secure identifier pattern [a-z0-9_-]+."""
    if not isinstance(name, str) or not _ENGINE_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid engine name '{name}'. Engine name must match pattern '^[a-z0-9_-]+$'."
        )


def register_stt_engine(name: str) -> Callable[[STTType], STTType]:
    """Decorator to register a Speech-To-Text (STT) engine implementation."""
    _validate_engine_name(name)

    def decorator(cls: STTType) -> STTType:
        _STT_REGISTRY[name] = cls
        return cls

    return decorator


def register_tts_engine(name: str) -> Callable[[TTSType], TTSType]:
    """Decorator to register a Text-To-Speech (TTS) engine implementation."""
    _validate_engine_name(name)

    def decorator(cls: TTSType) -> TTSType:
        _TTS_REGISTRY[name] = cls
        return cls

    return decorator


def register_wake_engine(name: str) -> Callable[[WakeType], WakeType]:
    """Decorator to register a Wake Word engine implementation."""
    _validate_engine_name(name)

    def decorator(cls: WakeType) -> WakeType:
        _WAKE_REGISTRY[name] = cls
        return cls

    return decorator


def register_vad_engine(name: str) -> Callable[[VADType], VADType]:
    """Decorator to register a Voice Activity Detection (VAD) engine implementation."""
    _validate_engine_name(name)

    def decorator(cls: VADType) -> VADType:
        _VAD_REGISTRY[name] = cls
        return cls

    return decorator


def create_stt_engine(name: str, **kwargs) -> STT:
    """Instantiate a registered STT engine by name with keyword arguments."""
    if name not in _STT_REGISTRY:
        available = ", ".join(sorted(_STT_REGISTRY.keys())) or "none"
        raise ValueError(
            f"Unknown STT engine '{name}'. Available STT engines: [{available}]"
        )
    return _STT_REGISTRY[name](**kwargs)


def create_tts_engine(name: str, **kwargs) -> TTS:
    """Instantiate a registered TTS engine by name with keyword arguments."""
    if name not in _TTS_REGISTRY:
        available = ", ".join(sorted(_TTS_REGISTRY.keys())) or "none"
        raise ValueError(
            f"Unknown TTS engine '{name}'. Available TTS engines: [{available}]"
        )
    return _TTS_REGISTRY[name](**kwargs)


def create_wake_engine(name: str, **kwargs) -> WakeWord:
    """Instantiate a registered WakeWord engine by name with keyword arguments."""
    if name not in _WAKE_REGISTRY:
        available = ", ".join(sorted(_WAKE_REGISTRY.keys())) or "none"
        raise ValueError(
            f"Unknown WakeWord engine '{name}'. Available WakeWord engines: [{available}]"
        )
    return _WAKE_REGISTRY[name](**kwargs)


def create_vad_engine(name: str, **kwargs) -> VAD:
    """Instantiate a registered VAD engine by name with keyword arguments."""
    if name not in _VAD_REGISTRY:
        available = ", ".join(sorted(_VAD_REGISTRY.keys())) or "none"
        raise ValueError(
            f"Unknown VAD engine '{name}'. Available VAD engines: [{available}]"
        )
    return _VAD_REGISTRY[name](**kwargs)


def list_stt_engines() -> list[str]:
    """List registered STT engine names in sorted order."""
    return sorted(_STT_REGISTRY.keys())


def list_tts_engines() -> list[str]:
    """List registered TTS engine names in sorted order."""
    return sorted(_TTS_REGISTRY.keys())


def list_wake_engines() -> list[str]:
    """List registered Wake Word engine names in sorted order."""
    return sorted(_WAKE_REGISTRY.keys())


def list_vad_engines() -> list[str]:
    """List registered VAD engine names in sorted order."""
    return sorted(_VAD_REGISTRY.keys())


def get_engine_for_language(
    lang: str, default_engine: str, overrides: dict[str, str] | None = None
) -> str:
    """Return the engine key for a language code, checking optional overrides (VOICE-05)."""
    if overrides and lang in overrides:
        return overrides[lang]
    return default_engine


def clear_registries() -> None:
    """Clear all registries (useful for isolated testing)."""
    _STT_REGISTRY.clear()
    _TTS_REGISTRY.clear()
    _WAKE_REGISTRY.clear()
    _VAD_REGISTRY.clear()
