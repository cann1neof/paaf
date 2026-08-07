# SPDX-License-Identifier: Apache-2.0
"""MESH-01/02: build the handoff surface, and validate whatever the model calls.

This module makes exactly one thing mechanical: **only a declared peer is
reachable**, and it enforces that twice, deliberately (Pattern 2).

* :func:`handoff_tools` shapes the surface — one ``transfer_to_<peer>`` tool per
  name in the awake agent's ``peers``, and nothing else. A target that is not a
  peer is not *offerable*. This is capability removal, the mesh's house style:
  the model is not instructed to behave, it is handed a smaller set of moves.
* :func:`resolve_handoff` checks the answer anyway, against ``awake.peers`` and
  never against ``LlmConfig.profiles``. A target that merely EXISTS is not a
  target this agent may reach. The second check is not belt-and-braces caution —
  models routinely emit tool names that were never bound, so a design resting on
  the surface alone would make MESH-02's "rejected, never silently followed"
  contingent on the provider behaving (Pitfall 4).

The guard is the one mesh guarantee that holds in every configuration, observed
or not (D-13): the observer can be absent, unreachable, or ungranted, and this
still refuses.

**No routing rule lives here, and none can.** PAAF never picks a target. It
offers the choice, in the user's declared order, described in the user's own
free text — and then validates. There is no keyword matching, no capability
scoring, and no config key that could express one (MESH-01).

The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the half of the mesh that decides what is reachable cannot
depend on anything swappable (SC#5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ports import ToolSpec, UndeclaredPeer

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .ports import ToolCall
    from .profiles import ModelProfile

#: The prefix every handoff tool's name carries. Three independent
#: implementations converged on this exact spelling — the OpenAI Agents SDK
#: (``transfer_to_<agent_name>``, its documented default) and ``langgraph-swarm``
#: (``create_handoff_tool`` produces the same) — which is the strongest available
#: evidence that D-01's tool-call signal is the right shape.
#:
#: The target lives in the tool NAME, never in arguments. That is why every
#: handoff tool takes no parameters at all: there is no argument for a model to
#: hallucinate, mistype, or smuggle something into, and the set of names it was
#: offered IS the set of moves available.
HANDOFF_TOOL_PREFIX = "transfer_to_"

#: The smallest hop budget a user may configure (D-08, Assumption A2).
#:
#: Three, because the legitimate A→B→A hand-back costs TWO hops and MESH-03
#: requires it to work. A floor below that would let a user stand the wall in
#: front of the very behavior the requirement demands — and because the wall is
#: enforced by *withdrawing* the tool, they would see it as an agent that
#: declined to hand back rather than as a misconfiguration. So the floor is a
#: schema constraint, checked at load.
#:
#: :class:`~paaf_llm.profiles.LlmConfig` imports this rather than repeating the
#: literal: two numbers that must agree are one number that eventually does not.
HOP_BUDGET_FLOOR = 3

#: How many handoffs one user turn may make before the engine stops offering the
#: tools (T-04-04). The default IS the floor: three is the smallest value that
#: leaves headroom above the legitimate A→B→A hand-back, and every hop above it
#: costs a full time-to-first-token on the latency path (Pitfall 6), so the
#: default errs toward the user hearing an answer.
#:
#: This is the fallback for callers with no :class:`LlmConfig` in hand. The
#: engine reads ``LlmConfig.hop_budget``, which the user owns.
DEFAULT_HOP_BUDGET = HOP_BUDGET_FLOOR


def handoff_tools(
    awake_name: str,
    awake: ModelProfile,
    profiles: Mapping[str, ModelProfile],
) -> tuple[ToolSpec, ...]:
    """Return one handoff tool per DECLARED peer of ``awake``, in declared order.

    This is the capability-removal half of MESH-02: a profile that is not one of
    ``awake.peers`` produces no tool, so it is not a move the model can make. The
    order is the user's — ``peers`` is written by hand and its order is part of
    what the user controls, exactly as ``fallback_chain``'s is.

    Every spec takes no parameters. The target lives in the tool's name (see
    :data:`HANDOFF_TOOL_PREFIX`), so the set of names offered IS the set of moves
    available, with no argument in between for a model to get wrong.

    **Both strings a tool carries are steering text** — the generated name and the
    peer's own ``capabilities`` manifest are read by the model and shape its
    choice. PERS-05 therefore says the user must be able to read them too; plan
    04-05 renders exactly these specs in the prompt inspector under
    ``--provenance``. Nothing here may be text the inspector cannot be handed.

    ``profiles`` is read ONLY to look up a peer's manifest. It is never consulted
    to decide reachability — that is :func:`resolve_handoff`'s job and it uses
    ``awake.peers``.

    Args:
        awake_name: the name of the agent being offered these tools. Present for
            symmetry with :func:`resolve_handoff` and for error text; a profile
            does not carry its own name (it is the key it sits under).
        awake: the profile whose ``peers`` shape the surface.
        profiles: the declared profiles, for reading each peer's manifest.
    """
    del awake_name  # named for symmetry; the surface depends only on `awake`
    return tuple(
        ToolSpec(
            name=f"{HANDOFF_TOOL_PREFIX}{peer}",
            description=_describe(peer, profiles.get(peer)),
            parameters={},
        )
        for peer in awake.peers
    )


def tools_for_leg(
    awake_name: str,
    awake: ModelProfile,
    profiles: Mapping[str, ModelProfile],
    hops_used: int,
    budget: int,
) -> tuple[ToolSpec, ...]:
    """Return the moves available on ONE leg: the peer tools, or none at the wall.

    The hop budget and the peer graph are the same mechanism seen twice — both
    decide what is *offerable*, and neither instructs the model about anything
    (D-08). Past the wall this returns an empty tuple, so the awake agent answers
    with no further move available. That is the absence of an option rather than
    a request to stop, which is the only form of the rule that holds no matter
    what the model decides.

    It is a pure function of five values so the rule is testable without driving
    a turn, and so the engine has exactly ONE place that decides it. A budget
    checked at the call site instead would be a second copy of the wall, and two
    copies of a safety rule is one copy plus a future divergence.

    ``hops_used >= budget`` rather than ``>``: the budget counts handoffs, so
    after the third hop of a three-hop budget there is nothing left to spend.

    Args:
        awake_name: the agent this leg belongs to (see :func:`handoff_tools`).
        awake: its profile — the ``peers`` list is the reachable set.
        profiles: the declared profiles, read only for each peer's manifest.
        hops_used: handoffs already made in THIS user turn.
        budget: ``LlmConfig.hop_budget``, never a constant read from here — the
            wall's height belongs to the user (floor :data:`HOP_BUDGET_FLOOR`).
    """
    if hops_used >= budget:
        return ()
    return handoff_tools(awake_name, awake, profiles)


def _describe(peer: str, profile: ModelProfile | None) -> str:
    """Return the tool description for ``peer`` — its manifest, verbatim.

    Verbatim is the contract: this is the user's own free text (D-08), and
    rewriting or summarizing it would put words the user never wrote in front of
    the model while ``paaf prompt`` showed the original.

    A peer that declared no manifest gets a neutral one-line fallback that names
    the peer and says nothing else. PAAF does not invent a capability on the
    user's behalf — a guessed description is a routing rule written by the
    framework, which is precisely what MESH-01 forbids.
    """
    manifest = profile.capabilities.strip() if profile is not None else ""
    return manifest or f"Hand the conversation to {peer}."


def target_of(call: ToolCall) -> str:
    """Return the peer name a tool call addresses — the name minus the prefix.

    A name that does not carry :data:`HANDOFF_TOOL_PREFIX` is returned RAW rather
    than repaired. That is deliberate: the caller needs the offending value to
    put in the error, and stripping a prefix that was never there could turn a
    call to some unrelated tool named ``chef`` into a successful handoff to the
    peer ``chef``. :func:`resolve_handoff` checks the prefix itself.
    """
    if not call.name.startswith(HANDOFF_TOOL_PREFIX):
        return call.name
    return call.name[len(HANDOFF_TOOL_PREFIX) :]


def resolve_handoff(awake_name: str, awake: ModelProfile, call: ToolCall) -> str:
    """Return the validated handoff target, or raise :class:`UndeclaredPeer`.

    Deterministic and unconditional. This is the ONE mesh guarantee that holds in
    every configuration, observed or not (D-13) — the observer may be absent,
    unreachable, or granted nothing, and this still refuses.

    It exists IN ADDITION to capability removal, and the redundancy is the point.
    Models routinely emit tool calls for tools that were never bound; a design
    resting on :func:`handoff_tools` alone would make MESH-02's "rejected rather
    than silently followed" contingent on the provider never misbehaving, which
    is the one circumstance the requirement was written for (Pitfall 4).

    Checked against ``awake.peers`` and NEVER against ``LlmConfig.profiles``: a
    target that merely EXISTS is not a target this agent may reach. The natural
    wrong implementation — ``profiles[target]`` — passes every other test in the
    mesh suite and fails only this one.

    Raises:
        UndeclaredPeer: the call is not a handoff tool at all, or it names a
            target outside ``awake``'s declared peers. Both messages name the
            offending value and the alternatives, in ``profiles.py``'s style.
    """
    offered = [f"{HANDOFF_TOOL_PREFIX}{peer}" for peer in sorted(awake.peers)]

    if not call.name.startswith(HANDOFF_TOOL_PREFIX):
        raise UndeclaredPeer(
            f"{awake_name!r} called tool {call.name!r}, which is not a handoff "
            f"tool; the only tools it was offered are {offered}"
        )

    target = target_of(call)
    if target not in awake.peers:
        raise UndeclaredPeer(
            f"{awake_name!r} attempted a handoff to {target!r}, which is not in "
            f"its declared peers {sorted(awake.peers)}"
        )
    return target
