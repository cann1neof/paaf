# SPDX-License-Identifier: Apache-2.0
"""CORE-01: the typed config schema validates on read — invalid input is rejected.

The negative control is the load-bearing test here: an out-of-range / mistyped
field MUST raise pydantic.ValidationError rather than being silently accepted.
"""
import pytest
from paaf_core.config import AppConfig, ReloadTier
from pydantic import ValidationError


def _valid_config() -> dict:
    return {
        "revision": 1,
        "voice": {"tts_volume": 1.0, "stt_model": "large-v3-turbo"},
        "model": {"temperature": 0.7, "provider": "ollama"},
    }


def test_valid_config_is_accepted():
    cfg = AppConfig.model_validate(_valid_config())
    assert cfg.revision == 1
    assert cfg.voice.tts_volume == 1.0
    assert cfg.model.provider == "ollama"


def test_revision_defaults_to_starting_value():
    # revision has an integer default so a fresh config is well-formed without it
    cfg = AppConfig.model_validate(
        {"voice": {}, "model": {}}
    )
    assert isinstance(cfg.revision, int)
    assert cfg.revision == 1


def test_out_of_range_value_is_rejected():
    # NEGATIVE CONTROL (CORE-01): tts_volume is bounded; an out-of-range value
    # must raise ValidationError, proving validate-on-read is non-vacuous.
    bad = _valid_config()
    bad["voice"]["tts_volume"] = 99.0
    with pytest.raises(ValidationError):
        AppConfig.model_validate(bad)


def test_mistyped_value_is_rejected():
    # NEGATIVE CONTROL (CORE-01): a non-numeric temperature must be rejected.
    bad = _valid_config()
    bad["model"]["temperature"] = "not-a-number"
    with pytest.raises(ValidationError):
        AppConfig.model_validate(bad)


def test_reload_tier_is_a_str_enum_with_four_members():
    assert issubclass(ReloadTier, str)
    assert {t.name for t in ReloadTier} == {"HOT", "WARM", "COLD", "RESTART"}
