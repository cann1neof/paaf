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
    # A declared path and a declared no-auth posture are both OPT-IN. Asserted
    # here so a future default flip cannot pass silently: defaulting the path
    # would append a URL segment nobody wrote, and defaulting the flag would
    # send unauthenticated requests on the user's behalf.
    assert profile.endpoint_path is None
    assert profile.endpoint_unauthenticated is False


def test_a_declared_path_reaches_the_full_url() -> None:
    # MODEL-02: /v1 is where vLLM, llama.cpp's server and LM Studio actually
    # serve, so an OpenAI-compatible profile must be able to say so in YAML.
    profile = ModelProfile(
        provider="openai_compatible",
        model="qwen3:32b",
        endpoint_host="192.168.1.20",
        endpoint_port=8000,
        endpoint_path="/v1",
    )
    endpoint = profile.endpoint()
    assert endpoint is not None
    assert endpoint.path == "/v1"
    assert endpoint.url() == "http://192.168.1.20:8000/v1"
    # The path travels WITH the endpoint, so the value Phase-9's offline check
    # classifies is the same one the adapter dials (CORE-05).
    assert endpoint.is_lan()


def test_an_unauthenticated_openai_compatible_profile_validates() -> None:
    # A LAN vLLM/llama.cpp server with no auth is a real configuration, and
    # saying so explicitly is the only way PAAF will send a credential-free
    # request — an absent api_key_ref alone is ambiguous with "I forgot".
    profile = ModelProfile(
        provider="openai_compatible",
        model="qwen3:32b",
        endpoint_host="192.168.1.20",
        endpoint_port=8000,
        endpoint_path="/v1",
        endpoint_unauthenticated=True,
    )
    assert profile.endpoint_unauthenticated is True
    assert profile.api_key_ref is None


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        (
            {"provider": "openai_compatible", "model": "m", "endpoint_path": "/v1"},
            "endpoint_path",
        ),
        (
            {
                "provider": "openai_compatible",
                "model": "m",
                "endpoint_host": "192.168.1.20",
                "endpoint_port": 8000,
                "endpoint_path": "v1",
            },
            "endpoint_path",
        ),
        (
            {
                "provider": "openai_compatible",
                "model": "m",
                "endpoint_host": "192.168.1.20",
                "endpoint_port": 8000,
                "endpoint_path": "/v1/",
            },
            "endpoint_path",
        ),
        (
            {
                "provider": "openai_compatible",
                "model": "m",
                "endpoint_host": "192.168.1.20",
                "endpoint_port": 8000,
                "endpoint_path": "/v1?key=x",
            },
            "endpoint_path",
        ),
        (
            {
                "provider": "openai_compatible",
                "model": "m",
                "endpoint_unauthenticated": True,
                "api_key_ref": "some_key",
            },
            "endpoint_unauthenticated",
        ),
        (
            {"provider": "ollama", "model": "m", "endpoint_unauthenticated": True},
            "endpoint_unauthenticated",
        ),
    ],
    ids=[
        "path_without_host_or_port",
        "path_not_starting_with_slash",
        "path_ending_with_slash",
        "path_with_a_query_character",
        "unauthenticated_and_api_key_ref",
        "unauthenticated_on_the_wrong_provider",
    ],
)
def test_malformed_endpoint_declarations_are_rejected(kwargs: dict, field: str) -> None:
    # T-03-36: a hand-edited path crosses into a DIALED URL, so it is untrusted
    # input. Every rejection names its field, and nothing is normalized — PAAF
    # repairing a malformed path would be it dialing a URL the user never wrote.
    with pytest.raises(ValidationError) as raised:
        ModelProfile(**kwargs)
    assert field in str(raised.value)


@pytest.mark.parametrize("path", ["/v1 beta", "/v1\tx", "/v1#frag"])
def test_a_path_with_whitespace_or_a_fragment_is_rejected(path: str) -> None:
    with pytest.raises(ValidationError):
        ModelProfile(
            provider="openai_compatible",
            model="m",
            endpoint_host="192.168.1.20",
            endpoint_port=8000,
            endpoint_path=path,
        )


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
