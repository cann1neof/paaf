# SPDX-License-Identifier: Apache-2.0
"""MESH-06: a handoff attempt is judged before control moves, and the judge is bounded.

This module makes exactly one thing mechanical: **every handoff attempt is put in
front of a supervising model before the transfer happens, and that model's powers
are exactly the tools it was granted** (D-03/D-04). Both halves matter, and the
second is the one that is easy to get wrong. A supervisor whose limits are a mode
flag or a sentence in its system prompt is a supervisor that can be argued with —
the observer's window carries user and model text that may make a case for its own
approval (T-04-32). So the recognized tool set is derived from
:func:`paaf_llm.mesh.observer_tools` **for this call**, with the default grant of
retry-only, and a power that was not granted is not exercisable no matter what the
observer emits. Capability removal, never instruction: the same mechanism the hop
wall uses (D-08), for the same reason.

**The observer is not a subsystem.** It is an ordinary
:class:`~paaf_llm.profiles.ModelProfile` under a reserved name, streamed through
the SAME :class:`~paaf_llm.ports.ChatAdapter` port and the SAME ordered fallback
loop as any other agent — which is what gives it ``ModelProfile.fallback_chain``,
``Endpoint`` declaration, reload tiers, ``extra="forbid"`` and secret-by-reference
for free (Pattern 5, OQ-4). It reaches that loop through :class:`LegRunner`, a
protocol narrow enough that a test satisfies it in a few lines, and narrow on
purpose: a second calling path is how an observer would quietly stop inheriting
those four things.

**Two verdicts do something, and the third is the ordinary case** (D-05).
Emitting nothing is ``APPROVE`` and the handoff proceeds. The retry tool kills the
attempt and bounces it to the calling agent, which runs again with the refusal in
front of it — as a transient labelled prompt segment on *that leg's* message list
only, never as a widened ``Role`` and never in ``Agent.history`` (OQ-1, Pitfall 1).
A re-route tool redirects, and only ever to a peer the CALLING agent already had
(D-06).

**An ungranted emission is recorded and not acted on, and that non-answer is
deliberate.** Translating an attempted re-route from a retry-only observer into a
retry would be PAAF deciding on the model's behalf what it meant. The honest
behaviour is to not exercise a power that was not granted, to let the handoff
proceed as originally named, and to say so in the attempt record — no silent
swallow, and no PAAF-invented reinterpretation (T-04-37).

Constraints stay **free text** throughout (D-12). A closed constraint vocabulary
would be a routing DSL by the back door, banned by MESH-01 whatever it is written
in; the observer reads the user's own sentences the same way the awake model reads
a peer's manifest.

The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the half of the mesh that supervises the mesh cannot depend on
anything swappable (SC#5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from . import mesh
from .ports import Message

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .ports import ToolCall, ToolSpec
    from .profiles import LlmConfig

#: One recorded fallback hop as :meth:`LegRunner.run_leg` reports it —
#: ``(from_profile, to_profile, reason)``, the same triple
#: :attr:`~paaf_llm.ports.TurnResult.fallback_trail` carries. Spelled here rather
#: than imported from :mod:`paaf_llm.agent` so this module keeps its one-way
#: dependency: the engine knows about the observer, not the reverse.
Hop = tuple[str, str, str]


class ObserverVerdict(str, Enum):
    """What the observer decided about ONE handoff attempt (D-05, MESH-06).

    A ``str`` enum for the same reason :class:`~paaf_llm.ports.FallbackReason` is
    one: a verdict serializes straight into the ``handoffs`` row's
    ``observer_verdict`` column and prints in a signal or a CLI notice without a
    lookup table in between.

    Three members, and :attr:`APPROVE` is the ordinary one — it is what an
    observer that emitted no tool call at all produced, and it is also what an
    observer that reached for a power it was not granted produced. The difference
    between those two is recorded in :attr:`ObserverDecision.detail`, never in a
    fourth verdict, because a verdict says what HAPPENED to the handoff and both
    of those left it alone.
    """

    APPROVE = "approve"
    GENERIC_RETRY = "generic_retry"
    REROUTE = "reroute"


@dataclass(frozen=True, slots=True)
class HandoffAttempt:
    """Everything the observer is shown about one attempt (D-14, D-15).

    Frozen for the reason :class:`~paaf_llm.ports.Message` is frozen: it crosses
    into the text handed to a model, and nothing downstream may rewrite what the
    agents actually said on the way there.

    **The default window is the three narrow fields**, per D-15: the last user
    message, the handoff decision itself (``from_agent`` → ``to_agent``), and the
    calling agent's own stated reasoning if it gave any. ``messages`` and
    ``recent_handoffs`` are empty unless the user widened the window, and the
    default matters beyond tidiness — a cloud observer profile with a wide window
    ships a slice of conversation off-box on **every** attempt, including the
    rejected ones (Pitfall 7, T-04-35).

    ``recent_handoffs`` exists for one specific purpose rather than for symmetry:
    an observer that can see it is inside a handoff loop can break the loop
    gracefully, before the deterministic wall ends the turn by exhaustion (D-08).

    Both ``constraints`` tuples are **free text**, verbatim (D-12). A structured
    constraint vocabulary would be a routing DSL by the back door, and quoting
    them rather than summarizing them is the same rule the peer manifests follow:
    the model reads what the user wrote, and the user can read it too.
    """

    turn_id: str
    seq: int
    from_agent: str
    to_agent: str
    #: The calling agent's own declared hard constraints, free text (D-12).
    from_constraints: tuple[str, ...] = ()
    #: The TARGET's declared hard constraints — the ones MESH-06 is written for:
    #: "never send private files" is declared on the agent it binds.
    to_constraints: tuple[str, ...] = ()
    #: The last user message. Always present — it is the default window.
    user_text: str = ""
    #: Whatever the calling agent said before reaching for the handoff tool.
    #: Often empty: plan 04-04 measured both gate models emitting the call with
    #: zero accompanying prose, so a silent handoff is the normal case.
    reasoning: str = ""
    #: The last N conversation messages, when ``observer_window_messages`` > 0.
    messages: tuple[Message, ...] = ()
    #: The last N attempts in THIS turn as ``(from, to, outcome)``, when
    #: ``observer_window_handoffs`` > 0.
    recent_handoffs: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ObserverDecision:
    """One verdict, with the record that goes on the ``handoffs`` row.

    ``target`` is set only for :attr:`ObserverVerdict.REROUTE` and is the name the
    observer's tool call NAMED — deliberately not yet validated. Validation is
    :func:`paaf_llm.mesh.resolve_handoff`'s job, run by the engine with the
    CALLER's profile, so the observer's target goes through the same guard and
    raises the same :class:`~paaf_llm.ports.UndeclaredPeer` an agent's would
    (D-06). Resolving it here would be a second guard, and two copies of a
    reachability rule is one copy plus a future divergence.

    ``detail`` is the observer's own words, verbatim — never a summary, because
    it is quoted back to the vetoed agent by :func:`paaf_llm.mesh.retry_text` and
    the user reads the same bytes.

    ``ungranted`` is set — and the verdict is :attr:`ObserverVerdict.APPROVE` —
    when the observer reached for a power it was not granted. It is a separate
    field rather than a fourth verdict because a verdict says what HAPPENED to
    the handoff, and this one left it alone. The engine writes it onto the
    attempt row's ``detail``, which is the whole of T-04-37's mitigation: the
    attempt is in the record rather than silently swallowed.

    ``served_by`` names the profile that ACTUALLY served the observer's leg,
    which may be a fallback down its own chain (SC#4 applies to it like any other
    agent). It becomes ``handoffs.observer_profile``, and ``None`` there is the
    meaningful value D-07 turns on: nobody looked.
    """

    verdict: ObserverVerdict
    target: str | None = None
    detail: str = ""
    served_by: str | None = None
    ungranted: str | None = None


class LegRunner(Protocol):
    """The one thing the observer needs from the engine: run ONE leg as an agent.

    Narrow on purpose, and modelled on :class:`~paaf_llm.agent.TraceSink` for the
    same reason: a collaborator this small is a contract a test can satisfy in a
    few lines, and it keeps the observer from typing itself against the whole
    :class:`~paaf_llm.agent.Agent`.

    **It is also why the observer does not invent a second calling path.**
    Running its leg through the engine means the observer's own system prompt is
    composed by the one composer (so ``paaf prompt --agent observer`` shows the
    same bytes), its stream crosses the same
    :class:`~paaf_llm.ports.ToolCallingChatAdapter` port, and its resilience is
    the ordinary per-agent ``fallback_chain`` — all inherited rather than
    re-implemented (OQ-4).

    The tool calls come back alongside the reply rather than through a separate
    accessor, because a verdict is unreadable without them; the reply, the trail
    and the calls all describe the one leg that just ran.
    """

    async def run_leg(
        self,
        agent_name: str,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> tuple[str, str, list[Hop], tuple[ToolCall, ...]]:
        """Run one leg as ``agent_name`` and return what it produced.

        The implementation composes ``agent_name``'s own system prompt and
        prepends it, so a caller passes only the content of the leg.

        Returns:
            ``(served_by, reply, trail, tool_calls)`` — who actually answered,
            the aggregated text, the fallback hops taken to get there, and the
            tool calls read AFTER the stream aggregated.
        """
        ...


#: What the brief calls a handoff that has not happened yet. Stated as a fact and
#: nothing more: the brief describes the attempt and names the tools available,
#: and it states no condition under which to use them. A sentence like "refuse
#: this if the target violates a constraint" would be a routing rule for the
#: supervisor, and MESH-01 bans routing rules rather than routing syntax
#: (T-04-22) — the judgement is the observer's, read out of the user's own free
#: text, exactly as the handoff decision is the awake model's.
BRIEF_HEADER = (
    "You are supervising a handoff between agents in this assistant.\n"
    "\n"
    "Agent {from_agent} is attempting to hand the conversation to {to_agent}."
)

#: Headings inside the brief. Each labels text taken verbatim from the user's own
#: config or from the conversation, so the observer reads what the user wrote.
BRIEF_TARGET_CONSTRAINTS = "Hard constraints declared on {to_agent}:"
BRIEF_CALLER_CONSTRAINTS = "Hard constraints declared on {from_agent}:"
BRIEF_REASONING = "What {from_agent} said before asking for the hand-over:"
BRIEF_USER_TEXT = "The user's last message:"
BRIEF_RECENT = "Earlier handoff attempts in this same turn:"
BRIEF_CONVERSATION = "The conversation so far:"

#: Recorded in :attr:`ObserverDecision.detail` when the observer called a tool it
#: was not granted. The offending name is in the record and the handoff proceeds
#: unchanged — PAAF does not decide what the model meant (T-04-37, D-04).
UNGRANTED_EMISSION = (
    "the observer called {name!r}, which it was not granted; it was offered "
    "{offered}. The handoff proceeded as originally named."
)


class Observer:
    """The supervising model, built from the config and driven through a runner.

    Constructed only when the reserved ``observer`` profile is declared — "on by
    default" reserves the slot and wires it, it does not invent a model to fill
    it (D-07). With no such profile the engine holds ``None`` and every handoff
    takes exactly the path it took before this module existed.
    """

    def __init__(self, config: LlmConfig, runner: LegRunner) -> None:
        self._config = config
        self._runner = runner

    async def judge(self, attempt: HandoffAttempt) -> ObserverDecision:
        """Judge ONE handoff attempt — one model round-trip, and only here (D-14).

        Constraint checking is handoff-time only: never per turn, never per
        token. That is a cost decision as much as a scope one — each attempt
        already costs a full time-to-first-token on the latency path, and a
        per-token supervisor would be a second model in the streaming path
        (Pitfall 6, T-04-38).

        The surface is built for THIS call from the caller's own peers, and the
        set of tool names this method recognizes is read straight back off it.
        There is therefore exactly one place that decides what the observer may
        do, and it is the same place that built what the observer was offered —
        which is what stops a grant check and a tool surface from drifting into
        disagreeing about the same power.
        """
        caller = self._config.profiles.get(attempt.from_agent)
        caller_peers = caller.peers if caller is not None else []
        tools = mesh.observer_tools(
            self._config.observer_grants, caller_peers, self._config.profiles
        )

        served_by, reply, _trail, calls = await self._runner.run_leg(
            mesh.OBSERVER_PROFILE_NAME,
            (Message("user", self.brief(attempt)),),
            tools,
        )
        return self._decide(calls, reply, served_by, tools)

    def brief(self, attempt: HandoffAttempt) -> str:
        """Return the text the observer is shown about ``attempt`` (D-15).

        Public because it is steering text: the user is entitled to see what
        their supervisor is being told, and a private assembler would be exactly
        the "reaches the model, unreadable by the user" shape PERS-05 forbids.

        Every span here is either a fixed label or the user's / the models' own
        words, quoted verbatim. Sections the window did not include are omitted
        entirely rather than emitted empty, the same rule
        :func:`paaf_llm.mesh.mesh_fragments_for` follows: a heading over nothing
        claims something was said when it was not.
        """
        parts = [
            BRIEF_HEADER.format(
                from_agent=attempt.from_agent, to_agent=attempt.to_agent
            )
        ]
        if attempt.to_constraints:
            parts.append(
                BRIEF_TARGET_CONSTRAINTS.format(to_agent=attempt.to_agent)
                + "\n"
                + _bullets(attempt.to_constraints)
            )
        if attempt.from_constraints:
            parts.append(
                BRIEF_CALLER_CONSTRAINTS.format(from_agent=attempt.from_agent)
                + "\n"
                + _bullets(attempt.from_constraints)
            )
        if attempt.reasoning:
            parts.append(
                BRIEF_REASONING.format(from_agent=attempt.from_agent)
                + "\n"
                + attempt.reasoning
            )
        if attempt.user_text:
            parts.append(BRIEF_USER_TEXT + "\n" + attempt.user_text)
        if attempt.recent_handoffs:
            parts.append(
                BRIEF_RECENT
                + "\n"
                + _bullets(
                    [
                        f"{frm} -> {to} ({outcome})"
                        for frm, to, outcome in attempt.recent_handoffs
                    ]
                )
            )
        if attempt.messages:
            parts.append(
                BRIEF_CONVERSATION
                + "\n"
                + _bullets(
                    [
                        f"{message.role}: {message.content}"
                        for message in attempt.messages
                    ]
                )
            )
        return "\n\n".join(parts)

    def _decide(
        self,
        calls: Sequence[ToolCall],
        reply: str,
        served_by: str,
        tools: Sequence[ToolSpec],
    ) -> ObserverDecision:
        """Map the emitted tool call onto a verdict, or onto a recorded non-answer.

        **The grant check is explicit and singular, and it is read off the surface
        that was just built.** ``tools`` is
        :func:`paaf_llm.mesh.observer_tools`'s output for THIS call, so there is
        exactly one place that decides what the observer may do and it is the same
        place that decided what the observer was offered. A grant check written
        against ``LlmConfig.observer_grants`` separately would be a second opinion
        about the same question, and two of those is one plus a future divergence.

        **The POWER and the REACH are two questions, and only the first is
        answered here** — that separation is what keeps D-06 honest. Whether the
        observer may re-route AT ALL is this method's business, and it is decided
        by whether a ``reroute_to_*`` spec was offered. Whether a *particular*
        target is reachable is emphatically not: that name is handed on
        unvalidated so the engine can run it through
        :func:`paaf_llm.mesh.resolve_handoff` with the CALLER's profile, raising
        the same :class:`~paaf_llm.ports.UndeclaredPeer` an agent's target would.
        Rejecting an out-of-graph name here instead would make the second layer
        unreachable and quietly reduce a two-layer guard to one — the exact
        belt-and-braces shape ``handoff_tools`` + ``resolve_handoff`` has always
        had, for the reason Pitfall 4 gives.

        **An emission outside the grant is APPROVE, recorded.** Translating an
        ungranted re-route into a retry would look helpful and would be PAAF
        deciding on the model's behalf what it meant. The honest non-answer is to
        not exercise a power that was not granted, let the handoff proceed as
        originally named, and put the offending tool name in the record — no
        silent swallow either (T-04-37). That is the boundary ``grant_bounds``
        pins, with both halves.
        """
        if not calls:
            return ObserverDecision(
                ObserverVerdict.APPROVE, detail=reply, served_by=served_by
            )

        name = calls[0].name
        offered = {tool.name for tool in tools}

        if name == mesh.OBSERVER_RETRY_TOOL and name in offered:
            return ObserverDecision(
                ObserverVerdict.GENERIC_RETRY, detail=reply, served_by=served_by
            )

        may_reroute = any(
            candidate.startswith(mesh.OBSERVER_REROUTE_PREFIX) for candidate in offered
        )
        if name.startswith(mesh.OBSERVER_REROUTE_PREFIX) and may_reroute:
            return ObserverDecision(
                ObserverVerdict.REROUTE,
                target=name[len(mesh.OBSERVER_REROUTE_PREFIX) :],
                detail=reply,
                served_by=served_by,
            )

        return ObserverDecision(
            ObserverVerdict.APPROVE,
            detail=reply,
            served_by=served_by,
            ungranted=UNGRANTED_EMISSION.format(name=name, offered=sorted(offered)),
        )


def _bullets(lines: Sequence[str]) -> str:
    """Render ``lines`` as one dash-prefixed line each — the explainer's shape."""
    return "\n".join(f"- {line}" for line in lines)
