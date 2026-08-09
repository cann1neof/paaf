# SPDX-License-Identifier: Apache-2.0
"""Exception hierarchy and model verification helpers for PAAF voice."""

from pathlib import Path


class VoiceError(Exception):
    """Base exception class for paaf-voice errors."""


class ModelMissingError(VoiceError):
    """Raised when required model weights are not present on disk (PRIV-06 gate)."""

    def __init__(
        self,
        engine_name: str,
        model_name: str,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.engine_name = engine_name
        self.model_name = model_name
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "paaf" / "models"
        self.cache_dir = str(cache_dir)
        message = (
            f"STT model '{model_name}' for engine '{engine_name}' not found in "
            f"{self.cache_dir}. Run 'paaf voice download-models --engine {engine_name} "
            f"--model {model_name}' to download with explicit consent."
        )
        super().__init__(message)


def verify_model_present(
    engine_name: str,
    model_name: str,
    cache_dir: str | Path | None = None,
) -> Path:
    """Verify that model weights exist in cache_dir.

    Returns the Path to the model if present, or raises ModelMissingError.
    """
    if cache_dir is None:
        c_path = Path.home() / ".cache" / "paaf" / "models"
    else:
        c_path = Path(cache_dir)

    engine_model_path = c_path / engine_name / model_name
    model_only_path = c_path / model_name

    if engine_model_path.exists():
        return engine_model_path
    elif model_only_path.exists():
        return model_only_path
    else:
        raise ModelMissingError(
            engine_name=engine_name,
            model_name=model_name,
            cache_dir=str(c_path),
        )
