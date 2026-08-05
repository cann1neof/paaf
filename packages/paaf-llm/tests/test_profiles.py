# SPDX-License-Identifier: Apache-2.0
"""MODEL-01/05/06: the model-profile schema validates on read.

Every test here is paired with a positive control so the rejections are never
vacuously green: a healthy profile / config MUST validate, and only then does a
malformed one raising ``pydantic.ValidationError`` mean anything.
"""
from __future__ import annotations

import pytest
from paaf_llm.profiles import LlmConfig, ModelProfile
from pydantic import ValidationError


def test_lan_ollama_profile_declares_a_lan_endpoint() -> None:
    # MODEL-06 half 1: a profile pointing at a LAN Ollama server classifies LAN
    # through the Phase-2 paaf_core Endpoint type — not a reinvented one.
    profile = ModelProfile(
        provider="ollama",
        model="qwen3.5:9b",
        endpoint_host="192.168.1.10",
        endpoint_port=11434,
    )
    endpoint = profile.endpoint()
    assert endpoint is not None
    assert endpoint.is_lan()
    assert (endpoint.host, endpoint.port, endpoint.scheme) == (
        "192.168.1.10",
        11434,
        "http",
    )


def test_cloud_profile_declares_no_endpoint() -> None:
    # A cloud profile relies on the provider default, so it declares no endpoint.
    # api_key_ref holds the NAME of a SecretStore key, never the value (CORE-04).
    profile = ModelProfile(
        provider="anthropic",
        model="claude-opus-5",
        api_key_ref="anthropic_api_key",
    )
    assert profile.endpoint() is None
    assert profile.api_key_ref == "anthropic_api_key"


def test_profile_defaults() -> None:
    profile = ModelProfile(provider="ollama", model="qwen3.5:9b")
    assert profile.temperature == 0.7
    # D-05: the per-profile slow-first-token budget, generous per warm model.
    assert profile.first_token_budget_s == 10.0
    # D-08 guard: the capability manifest is FREE TEXT, never structured fields.
    assert profile.capabilities == ""
    assert profile.peers == []
    assert profile.constraints == []


def test_capabilities_is_free_text_not_a_structured_schema() -> None:
    # D-08: encoding capabilities as fields would smuggle in a routing DSL.
    assert ModelProfile.model_fields["capabilities"].annotation is str
    profile = ModelProfile(
        provider="ollama",
        model="qwen3.5:9b",
        capabilities="Handles kitchen questions and timers, in Hebrew or English.",
    )
    assert "timers" in profile.capabilities


def test_unknown_profile_key_is_rejected() -> None:
    # NEGATIVE CONTROL (T-03-02): extra="forbid" refuses any smuggled field, so a
    # routing rule cannot hide in a hand-edited YAML profile.
    with pytest.raises(ValidationError):
        ModelProfile(provider="ollama", model="qwen3.5:9b", bogus=1)


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ModelProfile(provider="not-a-provider", model="qwen3.5:9b")


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_temperature_is_bounded(temperature: float) -> None:
    with pytest.raises(ValidationError):
        ModelProfile(provider="ollama", model="m", temperature=temperature)


@pytest.mark.parametrize("budget", [0.0, -1.0])
def test_non_positive_first_token_budget_is_rejected(budget: float) -> None:
    with pytest.raises(ValidationError):
        ModelProfile(provider="ollama", model="m", first_token_budget_s=budget)


# --------------------------------------------------------------------------
# LlmConfig — reference integrity across the whole profile tree
# --------------------------------------------------------------------------


def _valid_config() -> dict:
    """A healthy two-profile config: the positive control for every rejection."""
    return {
        "base_prompt": "You are a household assistant.",
        "active_profile": "kitchen-local",
        "fallback_chain": ["study-local", "cloud"],
        "profiles": {
            "kitchen-local": {
                "provider": "ollama",
                "model": "qwen3.5:9b",
                "endpoint_host": "192.168.1.10",
                "endpoint_port": 11434,
                "capabilities": "Timers, lights, and quick kitchen questions.",
                "peers": ["study-local"],
            },
            "study-local": {
                "provider": "ollama",
                "model": "qwen3.5:32b",
                "endpoint_host": "192.168.1.11",
                "endpoint_port": 11434,
                "capabilities": "Longer reasoning and writing.",
                "peers": ["kitchen-local"],
                "constraints": ["Never answer about the household calendar."],
            },
            "cloud": {
                "provider": "anthropic",
                "model": "claude-opus-5",
                "api_key_ref": "anthropic_api_key",
            },
        },
    }


def test_valid_config_loads() -> None:
    # POSITIVE CONTROL. Without this, every rejection test below could pass for
    # the wrong reason (a typo in the fixture rather than the validator biting).
    cfg = LlmConfig.model_validate(_valid_config())
    assert cfg.active_profile == "kitchen-local"
    assert cfg.base_prompt.startswith("You are")
    assert cfg.fallback_chain == ["study-local", "cloud"]
    assert set(cfg.profiles) == {"kitchen-local", "study-local", "cloud"}
    assert cfg.profiles["study-local"].peers == ["kitchen-local"]


def test_fallback_chain_and_peers_are_separate_fields() -> None:
    # RESEARCH Open Question 1: resilience (fallback_chain, on LlmConfig) and
    # handoff (peers, on each ModelProfile) have different semantics. Phase 4
    # reads only `peers`. Collapsing them would silently conflate the two.
    assert "fallback_chain" in LlmConfig.model_fields
    assert "fallback_chain" not in ModelProfile.model_fields
    assert "peers" in ModelProfile.model_fields
    assert "peers" not in LlmConfig.model_fields


def test_peer_validation() -> None:
    # MODEL-05 / D-07: the peer graph is inert this phase, but it must still be
    # INTEGRAL — Phase 4 traverses it, so a dangling edge is rejected at load.
    undeclared_peer = _valid_config()
    undeclared_peer["profiles"]["kitchen-local"]["peers"] = ["ghost"]
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(undeclared_peer)

    self_peer = _valid_config()
    self_peer["profiles"]["kitchen-local"]["peers"] = ["kitchen-local"]
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(self_peer)

    undeclared_fallback = _valid_config()
    undeclared_fallback["fallback_chain"] = ["ghost"]
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(undeclared_fallback)

    undeclared_active = _valid_config()
    undeclared_active["active_profile"] = "ghost"
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(undeclared_active)


def test_two_lan_profiles() -> None:
    # MODEL-06: two Ollama servers on the same LAN are two DISTINCT profiles,
    # keyed by name, each classifying LAN through its own declared endpoint.
    cfg = LlmConfig.model_validate(_valid_config())
    kitchen = cfg.profiles["kitchen-local"]
    study = cfg.profiles["study-local"]

    assert kitchen is not study
    assert kitchen.provider == study.provider == "ollama"
    assert kitchen.endpoint() != study.endpoint()
    assert kitchen.endpoint().host == "192.168.1.10"
    assert study.endpoint().host == "192.168.1.11"
    assert kitchen.endpoint().is_lan()
    assert study.endpoint().is_lan()

    # The cloud profile in the same tree declares no endpoint — it is visible to
    # the registry as "no PAAF-declared endpoint", not hidden (T-03-03).
    assert cfg.profiles["cloud"].endpoint() is None


def test_empty_fallback_chain_is_allowed() -> None:
    # A user who wants no fallback at all is not forced to declare one.
    minimal = _valid_config()
    minimal["fallback_chain"] = []
    assert LlmConfig.model_validate(minimal).fallback_chain == []


def test_unknown_config_key_is_rejected() -> None:
    # NEGATIVE CONTROL (T-03-02): extra="forbid" on the root too.
    bad = _valid_config()
    bad["routing_rules"] = {"if": "hebrew", "then": "cloud"}
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(bad)
