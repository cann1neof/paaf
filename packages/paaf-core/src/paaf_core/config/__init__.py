# SPDX-License-Identifier: Apache-2.0
"""paaf_core.config — the typed, atomic, revision-guarded config subsystem.

Submodule-level exports only; the top-level ``paaf_core`` package is left
untouched. Downstream code imports from ``paaf_core.config``.
"""

from .reload_tiers import DEFAULT_TIER, reload_tiers
from .schema import (
    AppConfig,
    McpServerConfig,
    McpServerTransport,
    ModelConfig,
    ReloadTier,
    VoiceConfig,
)
from .store import (
    ConflictError,
    atomic_write_bytes,
    dump_config,
    load_config,
    write_config,
)

__all__ = [
    "DEFAULT_TIER",
    "AppConfig",
    "ConflictError",
    "McpServerConfig",
    "McpServerTransport",
    "ModelConfig",
    "ReloadTier",
    "VoiceConfig",
    "atomic_write_bytes",
    "dump_config",
    "load_config",
    "reload_tiers",
    "write_config",
]

