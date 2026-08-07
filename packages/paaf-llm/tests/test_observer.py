# SPDX-License-Identifier: Apache-2.0
"""MESH-06: a supervising model judges every handoff, and its powers are its grant.

The requirement is that an agent's free-text hard constraints are enforced by
**the system** rather than by hoping the routing model read them. D-13 rules that
the observer counts as the system, so this file is where that ruling is cashed
in — and where the two ways it could be hollow are closed.

**The triggers and the negative controls are declared PAIRS here, and neither
half means anything alone.**

* ``vetoes`` proves a constraint-violating handoff is killed. On its own it is
  satisfied by an observer that vetoes *everything* — which would pass every
  positive assertion in this file while making the mesh useless. ``allows`` is
  the other half: the same wiring, a good handoff, and it goes through with no
  retry leg at all.
* ``grant_bounds`` proves a retry-only observer cannot re-route no matter what it
  emits. On its own it is satisfied by an implementation that ignores re-routes
  *entirely*. So it carries both halves: with the grant the same emission does
  redirect, and without it the handoff proceeds to the originally named target.

**What the two D-04/D-06 rows prove together** is the whole security shape of the
observer: its POWERS come from its tool grant, and its REACH comes from the
calling agent's own peer graph. Neither can be argued into existence by
conversation content, because neither is decided by reading the observer's
output — the recognized tool set is derived from :func:`paaf_llm.mesh.observer_tools`
for that very call, and a named re-route target is run through the same
:func:`paaf_llm.mesh.resolve_handoff` an agent's target goes through, with the
CALLER's profile. One graph, one guard, no second privilege tier.

**OQ-1 is why the veto looks the way it does.** A refusal reaches the calling
agent as a transient labelled prompt segment on that leg's message list only. It
is never in :attr:`paaf_llm.agent.Agent.history`, and ``Role`` is never widened
with a ``"tool"`` member — that option was considered and forbidden, because it
re-opens Pitfall 1's dangling tool-call bug that the Phase-3 message model closes
by construction.

Every test here runs against the shipped fake with the agent framework
uninstalled (SC#5), and none of them opens a socket.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest
from paaf_llm import mesh
from paaf_llm.profiles import LlmConfig, ModelProfile
from pydantic import ValidationError

# --------------------------------------------------------- the reserved name --


def test_a_config_with_no_observer_is_valid(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """D-07: "on by default" reserves the slot; it does not invent a model for it.

    PAAF never picks a model on the user's behalf, so a config that declares no
    ``observer`` profile is a legitimate configuration — the mesh runs
    unobserved. An implementation that required the profile would turn a design
    principle into a startup failure.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})

    assert mesh.OBSERVER_PROFILE_NAME not in config.profiles
    # And the reserved name is still reserved: nothing about declaring no
    # observer makes `observer` an ordinary name a user may reuse.
    assert config.observer_grants == [mesh.OBSERVER_GRANT_RETRY]


def test_an_observer_profile_is_an_ordinary_profile(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """Pattern 5: declaring it buys endpoint, tiers, forbid and secret-by-ref free.

    The observer is a :class:`ModelProfile` under a reserved key and nothing
    else, which is what makes it configurable down to its own system prompt
    (D-03) and what puts its endpoint in front of Phase-9's offline refusal —
    the mitigation T-04-35 rests on.
    """
    config = make_mesh_config(
        active="host", peers={"host": ["chef"], "chef": []}, observer=True
    )

    profile = config.profiles[mesh.OBSERVER_PROFILE_NAME]
    assert isinstance(profile, ModelProfile)
    assert profile.peers == []  # never awake, so it needs none
    # The four inherited-for-free properties, asserted rather than assumed.
    assert profile.endpoint() is None  # declarable, and declared as nothing here
    assert "reload_tier" in str(
        ModelProfile.model_fields["temperature"].json_schema_extra
    )
    assert ModelProfile.model_config["extra"] == "forbid"
    assert profile.api_key_ref is None


def test_observer_may_not_be_a_handoff_target(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """T-04-36: the reserved name is refused in any profile's peers, BY NAME.

    This is the load-bearing half of reserving the name. Without it, enabling the
    observer would quietly add an edge every agent could take — the supervisor
    becomes a participant, and MESH-02's graph acquires a member the user never
    drew.
    """
    with pytest.raises(ValidationError) as raised:
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile("host", peers=[mesh.OBSERVER_PROFILE_NAME]),
                mesh.OBSERVER_PROFILE_NAME: make_profile(mesh.OBSERVER_PROFILE_NAME),
            },
        )

    message = str(raised.value)
    assert "host" in message  # the offending profile, named
    assert mesh.OBSERVER_PROFILE_NAME in message
    assert "reserved" in message


def test_observer_may_not_be_active_profile_or_a_fallback_entry(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """D-03: three ways to make a supervisor a participant, all three refused.

    Each is asserted separately rather than as one "invalid config" check,
    because they are three different mistakes with three different fixes — and
    an implementation that caught only the first would leave the other two as
    silent ways in.
    """
    observer_profile = make_profile(mesh.OBSERVER_PROFILE_NAME)

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile=mesh.OBSERVER_PROFILE_NAME,
            profiles={
                "host": make_profile("host"),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
        )

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile("host"),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
            fallback_chain=[mesh.OBSERVER_PROFILE_NAME],
        )

    with pytest.raises(ValidationError, match="reserved"):
        LlmConfig(
            active_profile="host",
            profiles={
                "host": make_profile(
                    "host", fallback_chain=[mesh.OBSERVER_PROFILE_NAME]
                ),
                mesh.OBSERVER_PROFILE_NAME: observer_profile,
            },
        )


# ------------------------------------------------------------- the grant (D-04) --


def test_observer_grants_default_to_retry_only(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """D-04: the shipped observer can bounce a handoff and can do nothing else.

    Read off the schema rather than off the fixture, so this measures the default
    a user actually gets. Re-routing is a deliberate, readable edit to a config
    line — never something that arrives by upgrade.
    """
    config = make_mesh_config(active="host", peers={"host": ["chef"], "chef": []})

    assert config.observer_grants == ["generic_retry"]
    assert config.observer_window_messages == 0
    assert config.observer_window_handoffs == 0

    widened = make_mesh_config(
        active="host",
        peers={"host": ["chef"], "chef": []},
        observer_grants=["generic_retry", "reroute"],
    )
    assert widened.observer_grants == ["generic_retry", "reroute"]


def test_observer_grant_spellings_agree_between_schema_and_mesh() -> None:
    """The one place the ``Literal`` and ``mesh``'s constants could drift apart.

    ``LlmConfig.observer_grants`` must spell its members as literals — Pydantic
    cannot build a ``Literal`` from a variable — so the same two strings exist
    twice. This is the assertion that makes the duplication safe: rename one and
    the suite says so, rather than the grant check silently recognizing nothing.
    """
    annotation = LlmConfig.model_fields["observer_grants"].annotation
    # list[Literal[...]] -> Literal[...] -> the members
    (literal,) = annotation.__args__  # type: ignore[union-attr]

    assert set(literal.__args__) == set(mesh.OBSERVER_GRANTS)


def test_observer_grants_reject_an_unknown_power(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """An invented grant is refused at LOAD, never ignored at handoff time.

    The grant IS the boundary (D-04), so a typo in it must not degrade quietly
    into "no such power, carry on" — that would be a security control the user
    believes they configured and did not.
    """
    with pytest.raises(ValidationError):
        LlmConfig(
            active_profile="host",
            profiles={"host": make_profile("host")},
            observer_grants=["generic_retry", "rewrite_the_reply"],
        )


def test_observer_windows_reject_a_negative_size(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """D-15's two knobs are counts, and a negative count is a config error.

    Not clamped to zero: ``profiles.py``'s standing rule is validate-on-read and
    never repair, because a repaired value is a value the user did not write.
    """
    for field in ("observer_window_messages", "observer_window_handoffs"):
        with pytest.raises(ValidationError):
            LlmConfig(
                active_profile="host",
                profiles={"host": make_profile("host")},
                **{field: -1},
            )


# ---------------------------------------------------- the surface (D-04/D-06) --


def test_observer_tools_are_exactly_the_grant(
    make_mesh_config: Callable[..., LlmConfig],
) -> None:
    """The grant shapes the surface, and the CALLER's peers shape the re-routes.

    Equality assertions, not containment: an implementation that offered the
    re-route tools unconditionally, or that built them from every declared
    profile, would satisfy an ``in`` check and fail this one — which is the same
    trap ``test_tool_surface_is_exactly_the_declared_peers`` sets for the agent
    surface.
    """
    config = make_mesh_config(
        active="host",
        peers={"host": ["chef", "cook"], "chef": [], "cook": [], "admin": []},
        capabilities={"chef": "cooks"},
    )
    caller_peers = config.profiles["host"].peers

    retry_only = mesh.observer_tools(
        (mesh.OBSERVER_GRANT_RETRY,), caller_peers, config.profiles
    )
    assert [tool.name for tool in retry_only] == [mesh.OBSERVER_RETRY_TOOL]

    both = mesh.observer_tools(mesh.OBSERVER_GRANTS, caller_peers, config.profiles)
    assert [tool.name for tool in both] == [
        mesh.OBSERVER_RETRY_TOOL,
        "reroute_to_chef",
        "reroute_to_cook",
    ]
    # `admin` is a declared profile that `host` may not reach. It must not be
    # offerable to the observer either — that is D-06 enforced by the surface.
    assert not any("admin" in tool.name for tool in both)

    # Each peer is described by its OWN manifest, through the same `_describe`
    # the handoff surface uses, so the observer and the agent cannot be told
    # different things about the same agent.
    assert both[1].description == "cooks"
    assert all(tool.parameters == {} for tool in both)

    # A grant of nothing is a surface of nothing — the observer can then only
    # approve, which is exactly what "no powers" should mean.
    assert mesh.observer_tools((), caller_peers, config.profiles) == ()


def test_retry_text_names_the_target_and_quotes_the_reason() -> None:
    """OQ-1: the refusal is generated text, so PERS-05 applies to it too.

    Substituted with ``str.replace`` rather than ``str.format`` for the reason
    the explainer is: a user's own override is prose, and prose contains braces.
    An unexplained refusal gets a stated placeholder rather than an empty gap,
    because PAAF does not invent a reason on a model's behalf.
    """
    text = mesh.retry_text("chef", "chef may not read private files")

    assert "chef" in text
    assert "chef may not read private files" in text
    assert mesh.RETRY_TARGET_PLACEHOLDER not in text
    assert mesh.RETRY_REASON_PLACEHOLDER not in text

    assert mesh.NO_STATED_REASON in mesh.retry_text("chef", "   ")
    assert (
        mesh.retry_text("chef", "why", template="Refused {target}: {reason}. {oven}")
        == "Refused chef: why. {oven}"
    )


def test_grants_are_a_grant_and_never_a_routing_rule(
    make_profile: Callable[..., ModelProfile],
) -> None:
    """MESH-01 on the observer's own surface: no key here can express a rule.

    The near misses are the point. ``observer_grants`` is a list of powers, and a
    sibling key that read like a companion to it — a condition, a rule, a
    constraint vocabulary — is the shape a routing DSL would actually arrive in.
    ``extra="forbid"`` is the whole mechanism, and this is what keeps it honest.
    """
    near_misses: Sequence[str] = (
        "observer_rules",
        "observer_veto_conditions",
        "observer_constraint_types",
        "observer_routing",
    )
    for key in near_misses:
        with pytest.raises(ValidationError):
            LlmConfig(
                active_profile="host",
                profiles={"host": make_profile("host")},
                **{key: ["anything"]},
            )
