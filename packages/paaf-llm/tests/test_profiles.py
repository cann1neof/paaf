# SPDX-License-Identifier: Apache-2.0
"""MODEL-01/05/06: the model-profile schema validates on read.

Every test here is paired with a positive control so the rejections are never
vacuously green: a healthy profile / config MUST validate, and only then does a
malformed one raising ``pydantic.ValidationError`` mean anything.
"""
from __future__ import annotations

import pytest
from paaf_core.config.schema import ReloadTier
from paaf_llm.mesh import DEFAULT_HOP_BUDGET, HOP_BUDGET_FLOOR
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


# --------------------------------------------------------------------------
# Phase 4 — the third mesh concept, and MESH-01's mechanical guarantee
# --------------------------------------------------------------------------


def test_mesh_fields_default_to_the_floor_and_no_home_agent() -> None:
    """D-08/D-09: the wall has a user-owned height and nobody is home by default.

    The default IS the floor, and the floor is 3 because the legitimate A→B→A
    hand-back costs two hops (Assumption A2). ``default_agent`` defaults to
    ``None`` because PAAF does not guess who speaks when the mesh runs out of
    moves — with none declared, OQ-2's currently-awake agent answers.
    """
    cfg = LlmConfig.model_validate(_valid_config())
    assert cfg.hop_budget == 3
    assert cfg.hop_budget == HOP_BUDGET_FLOOR == DEFAULT_HOP_BUDGET
    assert cfg.default_agent is None


def test_the_new_mesh_fields_carry_reload_tier_metadata() -> None:
    """Every field on this schema declares when a change to it takes effect.

    Asserted rather than assumed: a field without a tier is invisible to the
    Phase-2 reload machinery, so it would be silently un-reloadable while
    looking exactly like every field beside it.
    """
    fields = LlmConfig.model_fields
    for name in ("hop_budget", "default_agent"):
        extra = fields[name].json_schema_extra
        assert isinstance(extra, dict)
        assert extra["reload_tier"] is ReloadTier.WARM


@pytest.mark.parametrize("budget", [2, 1, 0, -1])
def test_hop_budget_below_the_floor_is_rejected(budget: int) -> None:
    """The floor exists to keep the wall from standing in front of MESH-03.

    A→B→A is two hops. A user who set ``hop_budget=2`` would wall off the very
    hand-back the requirement demands, and — because the tools are simply
    withdrawn — would see it fail *silently* as an agent that declined to hand
    back rather than as a configuration error. So the floor is enforced at load.
    """
    bad = _valid_config()
    bad["hop_budget"] = budget
    with pytest.raises(ValidationError) as raised:
        LlmConfig.model_validate(bad)
    # Named, so the user reads the constraint rather than inferring it.
    assert "3" in str(raised.value)


@pytest.mark.parametrize("budget", [3, 10])
def test_hop_budget_at_or_above_the_floor_is_accepted(budget: int) -> None:
    """POSITIVE CONTROL: the floor is a floor, not a fixed value.

    Without this, a validator that rejected *every* hop_budget would satisfy
    the rejection test above completely.
    """
    good = _valid_config()
    good["hop_budget"] = budget
    assert LlmConfig.model_validate(good).hop_budget == budget


def test_default_agent_must_resolve_to_a_declared_profile() -> None:
    """D-09's home agent joins the same reference-integrity rule as the rest.

    A home agent discovered to be dangling at budget-exhaustion time is a
    runtime failure at the worst possible moment — the turn is already three
    hops deep. Catching it at load makes it a config error the user can read.
    """
    dangling = _valid_config()
    dangling["default_agent"] = "nobody"
    with pytest.raises(ValidationError) as raised:
        LlmConfig.model_validate(dangling)
    assert "nobody" in str(raised.value)  # the offending value, named

    # POSITIVE CONTROL: a declared name is accepted, and omitting it entirely is
    # accepted — otherwise a validator that rejected every default_agent (or
    # required one) would pass the rejection half above.
    declared = _valid_config()
    declared["default_agent"] = "cloud"
    assert LlmConfig.model_validate(declared).default_agent == "cloud"
    assert LlmConfig.model_validate(_valid_config()).default_agent is None


def test_default_agent_grants_no_handoff_edge() -> None:
    """T-04-12: naming a home agent is not naming a universal peer.

    ``default_agent`` is a THIRD concept (D-09) — the terminator — and keeping
    it a separate field from ``peers`` is what stops declaring it from quietly
    making one profile reachable from every other one.
    """
    declared = _valid_config()
    declared["default_agent"] = "cloud"
    cfg = LlmConfig.model_validate(declared)

    assert cfg.default_agent == "cloud"
    assert cfg.profiles["kitchen-local"].peers == ["study-local"]
    assert "cloud" not in cfg.profiles["kitchen-local"].peers
    assert "cloud" not in cfg.profiles["study-local"].peers
    # Three fields, three meanings — the anti-pattern is collapsing any pair.
    assert "default_agent" in LlmConfig.model_fields
    assert "default_agent" not in ModelProfile.model_fields


def test_routing_rules_key_on_the_config_is_rejected() -> None:
    """MESH-01's mechanical guarantee, on ``LlmConfig`` (T-03-02 carried forward).

    MESH-01 says no deterministic, user-written routing rule exists anywhere.
    The *mechanism* behind that claim is ``extra="forbid"`` — nothing else in
    the codebase enforces it — and adding a mesh field to this schema is exactly
    the moment the guarantee could be quietly widened. So it is re-asserted here
    against the plausible spelling a user (or a future maintainer) would reach
    for, rather than against a nonsense key like ``bogus``.
    """
    bad = _valid_config()
    bad["routing_rules"] = [{"match": "hebrew", "route_to": "cloud"}]
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(bad)


def test_routing_rules_key_on_a_profile_is_rejected() -> None:
    """The same guarantee on ``ModelProfile`` — the other half of the surface.

    A rule smuggled onto a single profile routes just as deterministically as a
    global one, so both models must refuse it.
    """
    bad = _valid_config()
    bad["profiles"]["kitchen-local"]["routing_rules"] = {"hebrew": "cloud"}
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(bad)

    with pytest.raises(ValidationError):
        ModelProfile(provider="ollama", model="m", routing_rules={"hebrew": "cloud"})


@pytest.mark.parametrize(
    "key, value",
    [
        ("hop_budget_rules", {"if_peers_gt": 2, "then": 5}),
        ("peer_priority", ["cloud", "study-local"]),
        ("default_agent_rules", {"on_exhaustion": "cloud"}),
    ],
)
def test_a_near_miss_routing_key_on_the_new_mesh_surface_is_rejected(
    key: str, value: object
) -> None:
    """The near miss is the real risk, not the obvious one.

    ``routing_rules`` was never going to be added by accident. A key that reads
    like a companion to the fields this plan *did* add — ``hop_budget_rules``
    beside ``hop_budget``, ``peer_priority`` beside ``peers`` — is the shape a
    routing DSL would actually arrive in, and each of these three encodes a
    deterministic routing decision the model would have no say in.
    """
    bad = _valid_config()
    bad[key] = value
    with pytest.raises(ValidationError):
        LlmConfig.model_validate(bad)
