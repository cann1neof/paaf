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

**The module also owns the words the agent is told about its peers (MESH-04).**
:func:`explainer_for` generates one agent's handoff explainer from *that* agent's
peer list and *those* peers' manifests, and :func:`mesh_fragments_for` hands it,
plus the agent's own persona, to the one composer as labelled segments. That is
the second half of a single rule: the model is offered the peers, and it is told
— in text the user can read verbatim in ``paaf prompt --provenance`` — that they
exist and what they are for. Generated text that steers a model and cannot be
read is the exact thing PERS-05 forbids, so both halves are user-overridable
(D-18) and both are inspectable.

The generated template names peers and quotes manifests. It states **no
condition** under which a handoff should happen, and adding one would be a
routing DSL written in English — banned by MESH-01 and Phase-3 D-08 no matter
what language it is written in (T-04-22).

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
    from .profiles import LlmConfig, ModelProfile

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

#: ``Segment.source`` for an agent's own persona — how THIS agent talks to the
#: user (D-16 layer 3). Namespaced in the same style as ``f"skill:{name}"``, so a
#: reader of ``--provenance`` can tell at a glance which layer a span came from.
MESH_PERSONA_SOURCE = "mesh:persona"

#: ``Segment.source`` for the handoff explainer, generated or overridden (D-18).
#: One label for both, deliberately: the user reads their override in exactly the
#: place they read the generated text, so replacing it cannot hide it.
MESH_EXPLAINER_SOURCE = "mesh:explainer"

#: The prefix the prompt inspector labels a bound handoff tool with, completed by
#: the tool's own name (``mesh:tool:transfer_to_chef``).
#:
#: This one is NOT a :class:`~paaf_llm.compose.Segment` source. A tool's name and
#: description reach the model *beside* the system prompt rather than inside it,
#: so composing them in would make ``compose`` claim to have sent bytes it never
#: sent. They are steering text all the same (RESEARCH Finding 1), which is why
#: ``paaf prompt --provenance`` renders them under this label: PERS-05 is about
#: what reaches the model, not about which field carried it.
MESH_TOOL_SOURCE_PREFIX = "mesh:tool:"

#: Where :func:`explainer_for` substitutes the peer list into a template.
#:
#: Substituted with :meth:`str.replace`, never ``str.format``. A user's own
#: template is prose, and prose contains braces — a stray ``{oven}`` would raise
#: ``KeyError`` at prompt-composition time, i.e. a crash in the one code path
#: that must always be able to show the user what was sent. A template that omits
#: the placeholder simply gets no peer list, which is a legitimate thing to ask
#: for and not an error to repair.
EXPLAINER_PEERS_PLACEHOLDER = "{peers}"

#: One line per peer inside the rendered explainer: the name the model must call
#: the tool for, and that peer's manifest exactly as :func:`_describe` gives it
#: to the tool surface. One derivation, so the explainer and the tool description
#: cannot disagree about the same agent.
EXPLAINER_PEER_LINE = "- {peer}: {manifest}"

#: The generated explainer (MESH-04), used whenever the user overrode nothing.
#:
#: It does three things and refuses a fourth. It says peers exist, it lists them
#: with their own manifests, and it says the hand-over is silent. It states **no
#: condition** under which to hand off — no keyword list, no ranking, no
#: "hand off when the user asks about X". Such a sentence would be a routing rule
#: that happens to be written in English, and MESH-01 bans routing rules, not
#: routing syntax (T-04-22). PAAF offers the choice; the model makes it.
#:
#: **The last paragraph is D-11, and only half of D-11.** Prose emitted *before*
#: a handoff ("let me get someone else for that") reaches the user attached to
#: nothing, because the hand-over is silent and a different agent then answers.
#: The explainer therefore DISCOURAGES it — and Phase 4 stops there on purpose.
#: Nothing here strips such prose, and no code elsewhere does either; mechanical
#: enforcement is a **v2 item the founder marked as really important** and it must
#: not be read as an oversight because the paragraph exists.
#:
#: Worth knowing while reading it: plan 04-04 measured ``qwen3.5:2b`` and
#: ``qwen3.5:9b`` against a live Ollama and found both emit the handoff tool call
#: with **zero** accompanying prose. So on today's gate models this paragraph
#: reinforces what they already do rather than correcting them, and every code
#: path around a handoff has to be correct when the prose is empty — which is the
#: common case, not the edge case.
DEFAULT_EXPLAINER_TEMPLATE = (
    "You are not the only agent in this conversation. You may hand it to any of "
    "the agents listed below, by calling that agent's handoff tool. Whoever you "
    "hand to sees everything said so far and answers the user in your place.\n"
    "\n"
    f"{EXPLAINER_PEERS_PLACEHOLDER}\n"
    "\n"
    "Each description above is what its owner wrote about that agent, and it is "
    "the only thing here that describes them. The choice is yours: hand over, or "
    "answer the user yourself.\n"
    "\n"
    "A hand-over is silent. The user is not told that it happened, and hears a "
    "single reply from whoever ends up answering. So hand over rather than "
    'saying that you are about to — a line like "let me get someone else for '
    'that" reaches the user attached to nothing, and then a different agent '
    "replies as though it had never been said."
)


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


def explainer_for(
    agent_name: str,
    agent: ModelProfile,
    profiles: Mapping[str, ModelProfile],
    template: str | None = None,
) -> str:
    """Return THIS agent's handoff explainer — generated, or the user's own.

    MESH-04 in one function. The text is built from the agent's declared
    ``peers`` and each peer's ``capabilities``, quoted verbatim through
    :func:`_describe` — the same call the tool surface makes, so the sentence the
    model reads in its prompt and the description attached to the tool it calls
    are the same bytes rather than two renderings that agree today.

    Precedence, narrowest first (D-18):

    1. ``agent.handoff_explainer`` — used **verbatim**, with no template rendered
       around it. A user who wrote the explainer themselves did not ask PAAF to
       append a paragraph to it, and appending one would put PAAF's words in a
       place the user believes is entirely theirs.
    2. ``template`` — the global ``LlmConfig.handoff_explainer_template``.
    3. :data:`DEFAULT_EXPLAINER_TEMPLATE`.

    An agent with no declared peers gets ``""``, and the caller drops the segment
    entirely. A ``mesh:explainer`` heading over an empty peer list would tell a
    reader of ``--provenance`` that the agent was told something about handing
    off when it was told nothing — the inspector overstating, which is the same
    class of lie as understating.

    The per-agent override is checked BEFORE the peer list, so an agent with an
    explicit explainer and no peers still shows the text its user wrote. That is
    the user's statement about their own assistant; PAAF does not overrule it on
    the grounds that it looks unused.

    Args:
        agent_name: the agent this explainer is for. Present for symmetry with
            the rest of this module (a profile does not carry its own name) and
            so a future template can address the agent by name.
        agent: the profile whose ``peers`` and override this reads.
        profiles: the declared profiles, read ONLY for each peer's manifest —
            never to decide reachability, which is ``agent.peers``' job alone.
        template: the global override, or ``None`` for the generated default.
    """
    del agent_name  # named for symmetry; see the docstring
    if agent.handoff_explainer is not None:
        return agent.handoff_explainer
    if not agent.peers:
        return ""
    peers = "\n".join(
        EXPLAINER_PEER_LINE.format(
            peer=peer, manifest=_describe(peer, profiles.get(peer))
        )
        for peer in agent.peers
    )
    chosen = template if template is not None else DEFAULT_EXPLAINER_TEMPLATE
    return chosen.replace(EXPLAINER_PEERS_PLACEHOLDER, peers)


def base_prompt_for(agent: ModelProfile, config: LlmConfig) -> str:
    """Return the base prompt THIS agent composes against (D-17, Assumption A4).

    A profile's own ``system_prompt`` when it declared one, and the shared
    ``LlmConfig.base_prompt`` otherwise. The per-agent layer is **additive**: the
    global stays meaningful as the base every agent falls back to, rather than
    being reshaped into a per-agent-only concept that would break every config
    written before the mesh existed.

    ``is not None`` rather than truthiness, and the distinction is real: a user
    who wrote ``system_prompt: ""`` asked for an agent with no base prompt, and
    silently substituting the global one would be PAAF overruling an explicit
    declaration with a default — the same mistake ``endpoint_unauthenticated``
    exists to avoid on the credential side.
    """
    if agent.system_prompt is not None:
        return agent.system_prompt
    return config.base_prompt


def mesh_fragments_for(
    agent_name: str, agent: ModelProfile, config: LlmConfig
) -> list[tuple[str, str]]:
    """Return THIS agent's mesh prompt layer as labelled ``(source, text)`` pairs.

    Persona first, explainer second, and the order is part of the composed bytes
    rather than an implementation detail: who the agent is comes before what it
    may do about it, which is also the order a reader of ``--provenance`` expects
    after the base prompt and the skills.

    Either is omitted when the agent declared nothing, so an agent with no
    persona gets no ``mesh:persona`` segment at all. The alternative — an empty
    labelled span — reads in the inspector as PAAF having said something empty,
    and the whole value of the labels is that they mean what they say.

    This is the ONE assembly of the mesh layer. :meth:`Agent.system_prompt` calls
    it for the live turn and ``paaf prompt`` calls it for the inspector, which is
    what makes the two byte-identical by construction instead of by discipline
    (D-02).
    """
    fragments: list[tuple[str, str]] = []
    if agent.persona:
        fragments.append((MESH_PERSONA_SOURCE, agent.persona))
    explainer = explainer_for(
        agent_name, agent, config.profiles, config.handoff_explainer_template
    )
    if explainer:
        fragments.append((MESH_EXPLAINER_SOURCE, explainer))
    return fragments


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
