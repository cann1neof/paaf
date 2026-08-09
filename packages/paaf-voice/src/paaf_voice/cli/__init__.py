# SPDX-License-Identifier: Apache-2.0
"""CLI interface for paaf-voice."""

from paaf_voice.cli.devices import get_audio_devices, list_devices_cmd
from paaf_voice.cli.models import (
    DEFAULT_CACHE_DIR,
    download_model_weights,
    download_models_cmd,
    list_installed_models,
    list_models_cmd,
    voice_cli,
)

__all__ = [
    "DEFAULT_CACHE_DIR",
    "download_model_weights",
    "download_models_cmd",
    "get_audio_devices",
    "list_devices_cmd",
    "list_installed_models",
    "list_models_cmd",
    "voice_cli",
]

