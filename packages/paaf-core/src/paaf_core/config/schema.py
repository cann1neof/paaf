# SPDX-License-Identifier: Apache-2.0
"""Typed config schema (CORE-01) with per-field reload-tier metadata (CORE-06).

The reload tier rides on the same Pydantic model the store validates, so there
is a single source of truth: the schema is both the validation contract and the
authority on how each key may be reloaded. Secret VALUES never live here — only
key references (coordinated with Plan 05's SecretStore).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ReloadTier(str, Enum):
    """How a config key can be applied after an edit.

    HOT     — applied immediately, no restart, no re-init.
    WARM    — applied on the next request/turn.
    COLD    — requires re-initializing a subsystem (e.g. reloading a model).
    RESTART — takes effect only after a full process restart.
    """

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    RESTART = "restart-only"


class VoiceConfig(BaseModel):
    """Voice-subsystem settings, spanning the HOT and COLD tiers."""

    # HOT: volume can change live without touching the audio graph.
    tts_volume: float = Field(
        1.0, ge=0.0, le=2.0, json_schema_extra={"reload_tier": ReloadTier.HOT}
    )
    # COLD: swapping the STT model means re-initializing the recognizer.
    stt_model: str = Field(
        "large-v3-turbo", json_schema_extra={"reload_tier": ReloadTier.COLD}
    )


class ModelConfig(BaseModel):
    """LLM-subsystem settings, spanning the WARM and RESTART tiers."""

    # WARM: a new temperature applies on the next turn.
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # RESTART: changing the provider re-wires the engine; restart required.
    provider: str = Field(
        "ollama", json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )


class AppConfig(BaseModel):
    """Root of the one YAML tree the user owns.

    `revision` is the monotonic optimistic-concurrency counter the store bumps
    on every successful write. `persona` deliberately carries no reload_tier so
    the discovery function's documented-default path is exercised.
    """

    model_config = {"extra": "forbid"}

    revision: int = 1
    persona: str = "assistant"
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
