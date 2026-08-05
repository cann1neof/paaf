# SPDX-License-Identifier: Apache-2.0
"""MODEL-01/05/06: the model-profile schema validates on read.

Every test here is paired with a positive control so the rejections are never
vacuously green: a healthy profile / config MUST validate, and only then does a
malformed one raising ``pydantic.ValidationError`` mean anything.
"""
from __future__ import annotations

import pytest
from paaf_llm.profiles import ModelProfile
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
