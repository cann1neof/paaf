# SPDX-License-Identifier: Apache-2.0
"""Tests for voice model CLI and weight presence verification (PRIV-06)."""

from pathlib import Path
import pytest
from click.testing import CliRunner

from paaf_voice.cli import (
    download_model_weights,
    list_installed_models,
    voice_cli,
)
from paaf_voice.exceptions import (
    ModelMissingError,
    VoiceError,
    verify_model_present,
)
from paaf_llm.cli import main as paaf_main_cli


def test_model_missing_error_message() -> None:
    """Verify ModelMissingError stores metadata and formats message with CLI command."""
    err = ModelMissingError("faster_whisper", "base", "/tmp/cache")
    assert isinstance(err, VoiceError)
    assert err.engine_name == "faster_whisper"
    assert err.model_name == "base"
    assert err.cache_dir == "/tmp/cache"
    assert (
        str(err)
        == "STT model 'base' for engine 'faster_whisper' not found in /tmp/cache. "
        "Run 'paaf voice download-models --engine faster_whisper --model base' to download with explicit consent."
    )


def test_verify_model_present_raises_missing(tmp_path: Path) -> None:
    """verify_model_present raises ModelMissingError when weights are not present on disk."""
    with pytest.raises(ModelMissingError) as exc_info:
        verify_model_present("faster_whisper", "base", cache_dir=tmp_path)

    assert exc_info.value.engine_name == "faster_whisper"
    assert exc_info.value.model_name == "base"
    assert exc_info.value.cache_dir == str(tmp_path)


def test_verify_model_present_success(tmp_path: Path) -> None:
    """verify_model_present returns Path when model directory exists."""
    model_dir = tmp_path / "faster_whisper" / "base"
    model_dir.mkdir(parents=True)

    found_path = verify_model_present("faster_whisper", "base", cache_dir=tmp_path)
    assert found_path == model_dir


def test_download_models_cli(tmp_path: Path) -> None:
    """paaf voice download-models creates weights in cache directory with progress output."""
    runner = CliRunner()
    result = runner.invoke(
        voice_cli,
        ["download-models", "--engine", "faster_whisper", "--model", "base", "--cache-dir", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "Downloading model weights" in result.output
    assert "faster_whisper" in result.output
    assert "base" in result.output
    assert tmp_path.name in result.output

    target_dir = tmp_path / "faster_whisper" / "base"
    assert target_dir.exists()
    assert (target_dir / "model.bin").exists()
    assert (target_dir / "config.json").exists()


def test_list_models_cli_empty(tmp_path: Path) -> None:
    """paaf voice list-models output when no models are installed."""
    runner = CliRunner()
    result = runner.invoke(voice_cli, ["list-models", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "No model weights found in cache" in result.output


def test_list_models_cli_populated(tmp_path: Path) -> None:
    """paaf voice list-models lists installed models in cache directory."""
    download_model_weights("faster_whisper", "base", cache_dir=tmp_path)

    runner = CliRunner()
    result = runner.invoke(voice_cli, ["list-models", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "faster_whisper" in result.output
    assert "base" in result.output


def test_paaf_main_cli_voice_integration(tmp_path: Path) -> None:
    """Verify 'paaf voice list-models' executes cleanly via main paaf CLI."""
    if "voice" not in paaf_main_cli.commands:
        paaf_main_cli.add_command(voice_cli, name="voice")
    runner = CliRunner()
    result = runner.invoke(paaf_main_cli, ["voice", "list-models", "--cache-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "PAAF Voice Installed Models" in result.output

