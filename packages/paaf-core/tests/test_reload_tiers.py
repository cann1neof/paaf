# SPDX-License-Identifier: Apache-2.0
"""CORE-06: every config key's reload tier is discoverable via reload_tiers().

Proves the discovery function is non-vacuous: every field path appears, a known
HOT field reports HOT, an unannotated field falls back to the documented default,
and all four tiers are represented across the schema.
"""
from paaf_core.config import AppConfig, ReloadTier, reload_tiers
from paaf_core.config.reload_tiers import DEFAULT_TIER


def test_reload_tiers_returns_nonempty_dict_of_tiers():
    tiers = reload_tiers(AppConfig)
    assert tiers, "reload_tiers must not be empty"
    assert all(isinstance(v, ReloadTier) for v in tiers.values())


def test_every_annotated_field_path_is_present():
    tiers = reload_tiers(AppConfig)
    # nested models are reported with dotted key paths
    assert "voice.tts_volume" in tiers
    assert "voice.stt_model" in tiers
    assert "model.temperature" in tiers
    assert "model.provider" in tiers


def test_known_hot_field_reports_hot():
    tiers = reload_tiers(AppConfig)
    assert tiers["voice.tts_volume"] == ReloadTier.HOT


def test_known_cold_field_reports_cold():
    tiers = reload_tiers(AppConfig)
    assert tiers["voice.stt_model"] == ReloadTier.COLD


def test_unannotated_field_reports_default_tier():
    # a field carrying no explicit reload_tier is reported with the documented
    # default, not omitted (revision + persona carry no annotation)
    tiers = reload_tiers(AppConfig)
    assert tiers["revision"] == DEFAULT_TIER
    assert tiers["persona"] == DEFAULT_TIER


def test_all_four_tiers_are_represented():
    present = set(reload_tiers(AppConfig).values())
    assert {ReloadTier.HOT, ReloadTier.WARM, ReloadTier.COLD, ReloadTier.RESTART} <= present
