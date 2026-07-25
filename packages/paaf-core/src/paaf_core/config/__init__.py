# SPDX-License-Identifier: Apache-2.0
"""paaf_core.config — the typed, atomic, revision-guarded config subsystem.

Submodule-level exports only; the top-level ``paaf_core`` package is left
untouched. Downstream code imports from ``paaf_core.config``.
"""
from .reload_tiers import DEFAULT_TIER, reload_tiers
from .schema import AppConfig, ModelConfig, ReloadTier, VoiceConfig

__all__ = [
    "AppConfig",
    "ModelConfig",
    "VoiceConfig",
    "ReloadTier",
    "reload_tiers",
    "DEFAULT_TIER",
]
