# SPDX-License-Identifier: Apache-2.0
"""MODEL-03/04/08: the turn loop — compose, stream, survive a lost provider.

This module is the one thing Phase 3 hand-rolls instead of delegating, and the
reason is specific rather than stylistic. The agent framework's own ordered
fallbacks (a runnable-level fallback wrapper, or agent-level model-fallback
middleware) fire only when *creating* the stream raises. They therefore cannot
see the failure this project actually cares about — a provider that accepts the
request, answers ``200``, and then takes forty seconds to produce a first token.
They also could not run here at all: the whole suite must pass with the agent
framework uninstalled (SC#1), and they cannot record *why* each hop happened,
which is what D-06 puts in front of the user.

So the loop below is pure PAAF and stdlib:

* **Ordered, user-owned.** ``[awake_agent, *fallback_chain]`` in exactly the
  order the user wrote it (MODEL-03). No scoring, no reordering, no cleverness.
  Before any handoff the awake agent IS ``active_profile``; resilience follows
  whoever is actually being asked to answer.
* **A first-token deadline, and only that.** ``asyncio.timeout`` wraps ONLY the
  first ``__anext__``; once a token flows the profile has committed and the rest
  of the stream is never interrupted (D-04's slow-first-token trigger is about
  *reaching* the first token). A deadline around the whole stream would abort
  long healthy replies while passing every test a fake can express.
* **Classification by reason, not by exception type.** Each degraded trigger
  arrives as one :class:`~paaf_llm.ports.AdapterError` subclass carrying one
  :class:`~paaf_llm.ports.FallbackReason`, so adding a provider adds a
  translation in its adapter and never a branch here (MODEL-04).
* **Provenance, always.** ``served_by`` plus every ``(from, to, reason)`` hop
  rides back on the :class:`~paaf_llm.ports.TurnResult` and drains to the trace
  (D-06) — "which model answered me, and why not the one I picked?" is a
  recorded fact, not a reconstruction.

**Two clocks, deliberately (Pitfall 2).** A cold local model can spend 3-10s
loading before its first token, which would false-trigger the deadline on every
first turn after an idle period. :meth:`Agent.warmup` pays that cost once at
startup by asking the adapter to preload each profile in the chain; the deadline
then measures a *warm* model's time-to-first-token, which is what
``first_token_budget_s`` actually means.

**History is ephemeral and in-memory** (D-01): a turn that nobody answered is
never appended, so the next turn cannot ship a user message the model never
replied to.

**Phase 4 (MESH-01/02/03): two nested loops, and they mean different things.**
:meth:`Agent.turn` is now a bounded loop over agent LEGS wrapped around the
unchanged fallback loop in :meth:`Agent._run_chain`. Handoff is *delegation* —
the awake model decided a peer should answer — while fallback is *resilience* —
this provider is not working, try the next one. Collapsing them would quietly
make every fallback target a handoff target, which is exactly why
``LlmConfig.fallback_chain`` and ``ModelProfile.peers`` are separate fields.

Three properties of the handoff loop are load-bearing and cheap to destroy:

* **PAAF never picks the target.** It offers one tool per declared peer and
  validates the answer (:mod:`paaf_llm.mesh`). There is no routing rule here and
  no config key that could express one (MESH-01).
* **Each leg builds a FRESH message list** — ``[system, *history, user]``. That
  one line is simultaneously MESH-03's "the receiving agent gets the full prior
  conversation", the reason A→B→A hand-back works (history is shared, not
  per-agent), and the reason the dangling-tool-call trap cannot be sprung
  (Pitfall 1): nothing is carried between legs.
* **The handoff tool call never enters** :attr:`Agent.history`. ``Role`` has no
  ``tool`` member, so it is structurally unrepresentable — and keeping it that
  way is a decision (OQ-1 forbids widening ``Role``), not an accident.

**The loop terminates because of a wall, not because of a prompt (D-08).** The
engine counts hops and asks :func:`paaf_llm.mesh.tools_for_leg` for this leg's
moves; past ``LlmConfig.hop_budget`` that is the empty tuple, so the awake agent
answers with nothing left to call. A model cannot talk past a tool it does not
have, which is the only property that survives contact with a model that has
decided to keep hopping. The budget's floor is three because the legitimate
A→B→A hand-back costs two, so the wall must stand *above* the behavior MESH-03
requires — and the mesh suite proves both halves as a pair.

At the wall, control goes to the user's declared ``default_agent`` if there is
one (D-09), and otherwise stays with whoever is awake (OQ-2). Never to
``active_profile``: that would be PAAF picking an agent in the one situation
where the user declined to. Either way a ``BUDGET_EXHAUSTED`` signal is emitted,
because a turn that quietly stopped hopping looks exactly like one that never
wanted to.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from paaf_trace.store import RunEvent

from . import mesh
from .compose import PromptComposer
from .ports import (
    AdapterError,
    AllProvidersFailed,
    ChatAdapter,
    FallbackReason,
    HandoffRequest,
    MeshSignal,
    MeshSignalKind,
    MeshSignalSink,
    Message,
    ToolCallingChatAdapter,
    TurnResult,
    UndeclaredPeer,
    Usage,
)

if TYPE_CHECKING:
    from .ports import ToolSpec
    from .profiles import LlmConfig, ModelProfile

#: One recorded fallback hop: ``(from_profile, to_profile, reason)``. ``to`` is
#: the empty string when the degraded profile was the LAST in the chain — there
#: was nowhere to go, and saying so is more honest than inventing a target.
Hop = tuple[str, str, str]


class SecretResolver(Protocol):
    """The slice of ``paaf_core``'s SecretStore an adapter needs (CORE-04).

    Held but unused in this phase: key resolution belongs to the real adapter,
    not to the turn loop. Declared so the parameter's meaning is typed rather
    than implied by a bare ``None`` default.
    """

    def get(self, key: str) -> str | None: ...


class TraceSink(Protocol):
    """The one method the engine needs from a trace store: fire-and-forget emit.

    Narrow on purpose. The engine drains provenance into ``paaf-trace``, but it
    should not be *typed against* the whole store — a sink is the contract, and
    a test can satisfy it with four lines.
    """

    def emit(self, event: object) -> None: ...


class Agent:
    """One conversation: composed prompt, in-memory history, ordered fallback."""

    def __init__(
        self,
        config: LlmConfig,
        adapter: ChatAdapter,
        *,
        secret_store: SecretResolver | None = None,
        trace: TraceSink | None = None,
        skill_fragments: Sequence[tuple[str, str]] = (),
        signals: MeshSignalSink | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._secret_store = secret_store
        self._trace = trace
        self._signals = signals
        #: D-09 stub: fragments are injected. Real skill discovery is Phase 6,
        #: and it plugs into this same ``(name, text)`` shape.
        self._skill_fragments: list[tuple[str, str]] = list(skill_fragments)
        self._composer = PromptComposer()
        #: The ephemeral conversation, user/assistant only. The system message is
        #: composed fresh each turn so a live config edit takes effect (WARM).
        self.history: list[Message] = []
        #: Which agent is currently awake (MESH-03, Pattern 4). Starts at the
        #: user's active profile, becomes an accepted handoff target, and is
        #: STICKY across user turns — "the receiving agent becomes awake until it
        #: hands off again" reads naturally as sticky, and it matches the
        #: active-agent state variable the multi-agent literature converged on.
        #:
        #: Deliberately NOT persisted across a restart. Phase-3 history is already
        #: ephemeral and in-memory (D-01), so persisting awake-state alone would
        #: produce the incoherent state of "agent B is awake but remembers
        #: nothing said to it".
        self.awake_agent: str = config.active_profile
        #: MESH_UNAVAILABLE is announced once per agent, not once per turn: it
        #: reports a static fact about the adapter, and re-emitting it on every
        #: turn would train a listener to ignore the channel.
        self._mesh_unavailable_announced = False

    @classmethod
    def build(
        cls,
        config: LlmConfig,
        adapter: ChatAdapter,
        *,
        secret_store: SecretResolver | None = None,
        trace: TraceSink | None = None,
        skill_fragments: Sequence[tuple[str, str]] = (),
        signals: MeshSignalSink | None = None,
    ) -> Agent:
        """Construct an agent for ``config`` served through ``adapter``."""
        return cls(
            config,
            adapter,
            secret_store=secret_store,
            trace=trace,
            skill_fragments=skill_fragments,
            signals=signals,
        )

    # ---------------------------------------------------------------- chain --

    def _chain(self, agent_name: str | None = None) -> list[tuple[str, ModelProfile]]:
        """Return ``[(name, profile), ...]`` in the user's declared order.

        The NAME is carried alongside the profile because it is not *on* it:
        a profile's name is the key it sits under in ``LlmConfig.profiles`` and
        does not cross the adapter port. ``served_by`` and every hop reason are
        reported with these names, so the loop must hold them itself — and it is
        also why a handoff target is a name rather than a profile object.

        The chain starts at whoever is AWAKE rather than at
        ``config.active_profile``, because resilience follows the agent actually
        being asked to answer — falling back from the active profile while a peer
        holds the conversation would answer as the wrong agent. Before any handoff
        the two are the same value, which is why this changed nothing for Phase 3.

        **The chain is resolved PER AWAKE AGENT (SC#4).** Fallback is nested
        inside handoff, so the order that applies on a leg is the order belonging
        to the agent serving that leg: its own ``ModelProfile.fallback_chain``
        when it declared one, and the global ``LlmConfig.fallback_chain`` when it
        did not. Empty-means-global is what keeps every Phase-3 config identical
        — none of them declares a per-agent chain — and it is a default rather
        than a merge, because a user who wrote an order wrote the whole order.

        ``agent_name`` names the agent explicitly. :meth:`turn` passes it because
        the agent serving the current leg is a LOCAL value during a turn — it is
        written back to :attr:`awake_agent` only once the turn has succeeded, so
        a turn that raised part-way cannot leave a phantom agent awake. Omitting
        it falls back to the attribute, which is what :meth:`warmup` wants.
        """
        head = agent_name or self.awake_agent
        tail = self._config.profiles[head].fallback_chain or self._config.fallback_chain
        return [(name, self._config.profiles[name]) for name in [head, *tail]]

    def system_prompt(self, agent_name: str | None = None) -> str:
        """Return THE system prompt for one agent (D-02 — still one composer).

        The CLI's prompt inspector calls this same path; there is no second
        derivation anywhere, which is what makes the inspector incapable of
        understating what was sent — and as of MESH-04 that holds for *any*
        declared agent, not only the one currently awake.

        Three ordered layers, assembled by :class:`PromptComposer` and by nothing
        else: this agent's base prompt (its own ``system_prompt``, or the shared
        ``LlmConfig.base_prompt`` — D-17/A4), the enabled skills' fragments, and
        the per-agent mesh layer of persona plus generated handoff explainer
        (D-16 layer 3, D-18). Two agents therefore come out genuinely different,
        which is the requirement, while the composer stays a pure function that
        has never heard of a mesh.

        ``agent_name`` defaults to the awake agent, so every Phase-3 caller keeps
        its exact meaning. Naming an agent is what ``paaf prompt --agent`` uses:
        it is the only way to read the prompt of a peer that is not awake, and
        later the only way to read the observer's, since the observer never is.

        Raises:
            KeyError: ``agent_name`` names no declared profile. Callers taking
                the name from the user validate it first and report through their
                own error path — an unvalidated CLI string must never reach a
                dict subscript (T-04-23).
        """
        name = agent_name if agent_name is not None else self.awake_agent
        profile = self._config.profiles[name]
        return self._composer.compose(
            mesh.base_prompt_for(profile, self._config),
            self._skill_fragments,
            mesh.mesh_fragments_for(name, profile, self._config),
        )

    def _reachable_agents(self) -> list[str]:
        """Return every agent a turn starting now could end up asking, in order.

        The awake agent, everything reachable from it through the declared peer
        graph (a handoff is a hop, and a hop can be followed by another one), and
        the ``default_agent`` — which is never anybody's peer by design (T-04-12)
        and yet speaks the final leg when the budget is spent (D-09), so it is
        precisely the agent a peer-only walk would miss.

        Order is the user's: the walk is breadth-first over declared peer lists,
        which is also what makes the result deterministic rather than set-shaped.
        """
        order: dict[str, None] = dict.fromkeys([self.awake_agent])
        queue = [self.awake_agent]
        while queue:
            for peer in self._config.profiles[queue.pop(0)].peers:
                if peer not in order:
                    order[peer] = None
                    queue.append(peer)
        if self._config.default_agent is not None:
            order.setdefault(self._config.default_agent, None)
        return list(order)

    async def warmup(self) -> None:
        """Preload every profile a turn could reach, so cold load is paid once.

        The two-clock design (Pitfall 2): model cold-load time is paid HERE, at
        build/startup, and the per-turn deadline then measures only a warm
        model's time-to-first-token. An adapter that exposes no ``preload`` —
        the shipped fake, for instance — makes this a no-op; the real adapter
        wires an empty-prompt load in a later plan.

        With a mesh, "the chain" is no longer one chain. A peer that is cold when
        it is handed a leg pays its 3-10s load *inside* that leg's first-token
        deadline, so it would false-trigger the very fallback the user configured
        for a broken provider — and it would do so only on handoffs, which is the
        hardest version of that bug to reproduce. So every agent reachable in a
        turn is preloaded, each with its OWN chain (SC#4), de-duplicated by
        profile name because one profile can appear in several agents' chains.
        """
        preload = getattr(self._adapter, "preload", None)
        if preload is None:
            return
        loaded: set[str] = set()
        for agent_name in self._reachable_agents():
            for name, profile in self._chain(agent_name):
                if name not in loaded:
                    loaded.add(name)
                    await preload(profile)

    # ----------------------------------------------------------------- turn --

    async def turn(self, user_text: str) -> TurnResult:
        """Serve one user turn — a bounded loop over agent legs (MESH-01/02/03).

        One question in, one answer out (D-10): a handoff resolves INSIDE this
        call, so the caller sees a single reply from whichever agent ended up
        answering. Each leg is a full model round-trip, and handoff is silent, so
        a hopping turn is an assistant going quiet (Pitfall 6, T-04-04) — which
        is why the loop is walled by ``LlmConfig.hop_budget`` (default 3, floor
        3) and why the wall is enforced by taking the tools away rather than by
        asking the model to stop.

        Raises:
            AllProvidersFailed: every profile in the awake agent's chain degraded.
            UndeclaredPeer: the model named a handoff target outside its declared
                peers (MESH-02). Nothing is appended to :attr:`history` — a turn
                nobody answered must not leave a user message the model never
                replied to.
        """
        # An engine-generated correlation id, never a database row id: the trace
        # writer is fire-and-forget and does not surface `lastrowid`, so
        # correlating on one would force a writer redesign (Finding 5).
        turn_id = uuid.uuid4().hex
        started_at = time.time()

        tool_calling = isinstance(self._adapter, ToolCallingChatAdapter)
        self._announce_if_mesh_unavailable(turn_id, tool_calling)

        accepted: HandoffRequest | None = None
        hops = 0
        budget = self._config.hop_budget
        # LOCAL for the duration of the turn, written back to `self.awake_agent`
        # only on success (see the write-back below). A turn that raised part-way
        # must not leave a phantom agent awake holding a conversation it never
        # answered — the same rule `history` already follows (D-01).
        awake = self.awake_agent
        # The mesh path is taken only when there is a mesh: an adapter that can
        # be offered tools AND a config in which somebody declared a peer. With
        # no graph at all this is the Phase-3 single-agent turn, unchanged.
        mesh_active = tool_calling and any(
            profile.peers for profile in self._config.profiles.values()
        )

        while True:
            profile = self._config.profiles[awake]

            # ONE place decides the surface (mesh.tools_for_leg): the declared
            # peers, or nothing at all once the budget is spent. D-08 — at the
            # wall the tool is WITHDRAWN, and the model is never told to stop.
            # Capability removal is the only mechanism that holds regardless of
            # what the model decides; an instruction is a request it may decline.
            tools: tuple[ToolSpec, ...] = (
                mesh.tools_for_leg(awake, profile, self._config.profiles, hops, budget)
                if mesh_active
                else ()
            )

            # A FRESH message list per leg (Pitfall 1). The receiving agent gets
            # the system prompt plus the whole prior transcript plus this turn —
            # which is simultaneously MESH-03's guarantee and the reason a
            # dangling tool call cannot survive between legs: nothing is reused.
            #
            # The prompt is composed for the agent serving THIS leg, so it
            # follows the handoff (MESH-04/D-17): the receiving agent is greeted
            # by its own persona and its own explainer, not by the one belonging
            # to the agent that handed to it. Composing it once outside the loop
            # is the natural wrong implementation and would quietly make every
            # per-agent prompt the caller's.
            system = self.system_prompt(awake)
            messages: list[Message] = [
                Message("system", system),
                *self.history,
                Message("user", user_text),
            ]

            served_by, reply, trail = await self._run_chain(
                messages, tools, awake=awake, tool_path=mesh_active
            )

            # Read tool calls ONCE, after the stream aggregated, and only if this
            # leg actually offered tools — an adapter's last-call state is stale
            # by definition on a leg that offered none.
            calls = self._adapter.last_tool_calls() if tools else ()  # type: ignore[attr-defined]
            if not calls:
                break

            try:
                target = mesh.resolve_handoff(awake, profile, calls[0])
            except UndeclaredPeer as exc:
                self._signal(
                    MeshSignalKind.UNDECLARED_PEER,
                    turn_id,
                    from_agent=awake,
                    to_agent=mesh.target_of(calls[0]),
                    detail=str(exc),
                )
                raise

            accepted = HandoffRequest(from_agent=awake, to_agent=target)
            awake = target
            hops += 1

            if hops >= budget:
                awake = self._exhausted(turn_id, awake, budget)

        # SPIKE-05: read usage ONCE, after the stream fully aggregated. Several
        # providers publish counts only on the final message, so a per-chunk
        # read reports None almost every time.
        usage: Usage = self._adapter.last_usage()
        # One row for the turn, describing the leg that answered. MESH-05 (plan
        # 04-04) splits this into one row per leg correlated by `turn_id`, which
        # is what gives every leg its own fallback provenance; until then a
        # handed-off turn records the answering agent's chain only.
        self._drain(system, served_by, trail, usage, started_at, time.time())

        # Appended only now, and only on success — the existing rule (D-01), and
        # the reason a refused handoff leaves no trace in the conversation.
        #
        # Pitfall 1: the handoff TOOL CALL is never appended here, in any form.
        # Carrying it would leave an assistant message with an unanswered
        # tool_call_id, which poisons every SUBSEQUENT request to an
        # OpenAI-compatible provider rather than just this one. PAAF's `Role` has
        # no `tool` member so it is unrepresentable — keeping it that way is a
        # decision (OQ-1 forbids widening `Role`), not an accident.
        self.history.append(Message("user", user_text))
        self.history.append(Message("assistant", reply))
        # Written back only now, and only on success (MESH-03, Assumption A3):
        # the agent that ended this turn awake starts the next one. Sticky
        # within the process and deliberately not persisted — history is already
        # ephemeral, so a persisted awake agent would return remembering nothing.
        self.awake_agent = awake

        return TurnResult(
            text=reply,
            served_by=served_by,
            usage=usage,
            fallback_trail=trail,
            handoff=accepted,
        )

    def _exhausted(self, turn_id: str, awake: str, budget: int) -> str:
        """Say the wall was hit, and return who serves the final leg (D-09/OQ-2).

        Two branches, and the second is the one worth reading twice.

        With a ``default_agent`` declared, the home agent the USER named takes
        over and becomes awake (D-09). That is the whole point of the field:
        somebody has to speak when the mesh has run out of moves, and PAAF does
        not pick them.

        With none declared, the currently-awake agent answers — with the handoff
        tools withdrawn, because :func:`mesh.tools_for_leg` is already past the
        wall. This is **not** PAAF guessing a fallback: it is the absence of a
        further move, which is exactly what exhaustion means, and it composes
        with D-08 rather than adding a rule. Falling back to
        ``config.active_profile`` is the natural wrong implementation and is
        explicitly rejected (OQ-2) — it would be PAAF choosing an agent on the
        user's behalf, in the one situation where the user said nothing.

        Emitted BEFORE the final leg runs, and exactly once per turn, because
        the loop reaches ``hops >= budget`` only on the hop that spends the last
        of the budget. Exhaustion must never be silent: a turn that quietly
        stopped hopping is indistinguishable from one that never wanted to
        (T-04-13). The matching ``handoffs`` row (``outcome="budget_exhausted"``,
        declared in plan 04-02's schema) is written by plan 04-06, which owns
        every trace emit site.
        """
        home = self._config.default_agent
        server = home if home is not None else awake
        self._signal(
            MeshSignalKind.BUDGET_EXHAUSTED,
            turn_id,
            from_agent=awake,
            to_agent=server,
            detail=str(budget),
        )
        return server

    def _announce_if_mesh_unavailable(self, turn_id: str, tool_calling: bool) -> None:
        """Say so, once, when a peer graph exists but the adapter cannot serve it.

        An adapter that is not a :class:`~paaf_llm.ports.ToolCallingChatAdapter`
        cannot be offered the handoff tools, so the mesh silently does not happen.
        Silently is the problem: a user who declared peers and sees an assistant
        that never hands off would have to infer the cause. Emitting
        :attr:`~paaf_llm.ports.MeshSignalKind.MESH_UNAVAILABLE` states it instead,
        and the turn then runs the ordinary Phase-3 single-agent path.

        No signal is emitted when no profile declares a peer — there is no mesh to
        be unavailable, and reporting one would be noise.
        """
        if tool_calling or self._mesh_unavailable_announced:
            return
        if not any(profile.peers for profile in self._config.profiles.values()):
            return
        self._mesh_unavailable_announced = True
        self._signal(
            MeshSignalKind.MESH_UNAVAILABLE,
            turn_id,
            from_agent=self.awake_agent,
            to_agent="",
            detail=(
                f"{type(self._adapter).__name__} cannot be offered tools, so "
                f"declared peers are unreachable; running the single-agent path"
            ),
        )

    def _signal(
        self,
        kind: MeshSignalKind,
        turn_id: str,
        *,
        from_agent: str,
        to_agent: str,
        detail: str = "",
    ) -> None:
        """Publish one mesh event to the sink, if a sink is attached (D-05).

        The same ``if ... is None: return`` shape as :meth:`_drain`, and for the
        same reason: observability is opt-in plumbing, so an agent built without
        it must take exactly the same path as one built with it.

        Fire-and-forget by contract — the turn's outcome never depends on a
        listener, which is why this returns nothing and awaits nothing.
        """
        if self._signals is None:
            return
        self._signals.signal(
            MeshSignal(
                kind=kind,
                turn_id=turn_id,
                from_agent=from_agent,
                to_agent=to_agent,
                detail=detail,
            )
        )

    def _drain(
        self,
        system: str,
        served_by: str,
        trail: list[Hop],
        usage: Usage,
        started_at: float,
        ended_at: float,
    ) -> None:
        """Record ONE run: the prompt sent, who served it, and every hop (D-06).

        ``emit`` is synchronous and fire-and-forget by contract — the trace
        store owns the writer task, and awaiting it here would put disk I/O on
        the turn's path, which is the exact thing ``paaf-trace`` is shaped to
        avoid.

        The trail is serialized as JSON because the ``runs`` column is TEXT: the
        store is a denormalized event log, not an object graph. An empty trail
        writes ``"[]"`` rather than ``NULL`` — "the active profile served it" is
        a fact worth recording, not an absence.
        """
        if self._trace is None:
            return
        self._trace.emit(
            RunEvent(
                prompts=system,
                model=served_by,
                started_at=started_at,
                ended_at=ended_at,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                served_by=served_by,
                fallback_trail=json.dumps(
                    [
                        {"from": frm, "to": to, "reason": reason}
                        for frm, to, reason in trail
                    ]
                ),
            )
        )

    async def _run_chain(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec] = (),
        *,
        awake: str | None = None,
        tool_path: bool = False,
    ) -> tuple[str, str, list[Hop]]:
        """Return ``(served_by, reply, trail)`` from the first profile to commit.

        ``tools`` is the handoff surface for this leg, empty on the single-agent
        path AND on the leg past the wall. Offering tools is not a different
        MODE: the deadline, the classification, and the
        committed-no-mid-stream-fallback rule are all identical either way — only
        the call shape differs, because the port keeps its tool vocabulary in a
        second protocol (D-02).

        ``tool_path`` selects the call shape and ``tools`` carries the payload,
        and they are two arguments rather than one on purpose. On the mesh path
        an EMPTY tool tuple is a statement — "you have no further move" (D-08) —
        not the absence of one, so the withdrawn leg still goes through
        ``stream_with_tools`` and is recorded as having been offered nothing. A
        shape derived from ``bool(tools)`` could not tell that apart from a
        Phase-3 single-agent turn, and the wall would then be unobservable at the
        port, which is where the budget test needs to see it.
        """
        chain = self._chain(awake)
        trail: list[Hop] = []
        # Feature detection, not configuration (Code Example 1). An adapter that
        # is not a ToolCallingChatAdapter takes the Phase-3 call; `turn` has
        # already said so on the signal channel.
        with_tools = tool_path and isinstance(self._adapter, ToolCallingChatAdapter)

        for index, (name, profile) in enumerate(chain):
            next_name = chain[index + 1][0] if index + 1 < len(chain) else ""
            gen = (
                self._adapter.stream_with_tools(profile, messages, tools)
                if with_tools
                else self._adapter.stream(profile, messages)
            )

            try:
                # The deadline covers ONLY time-to-first-token (D-04/D-05).
                async with asyncio.timeout(profile.first_token_budget_s):
                    first = await gen.__anext__()
            except TimeoutError:
                # Too slow is the USER's judgement, so only the engine may say
                # it — no adapter raises this reason (see ports.py).
                trail.append((name, next_name, FallbackReason.SLOW_FIRST_TOKEN.value))
                # Close the abandoned stream so a stalled provider's generator
                # is not left suspended. The port promises an AsyncIterator,
                # which does not guarantee aclose(), so ask before calling.
                aclose = getattr(gen, "aclose", None)
                if aclose is not None:
                    await aclose()
                continue
            except AdapterError as exc:
                trail.append((name, next_name, exc.reason.value))
                continue
            except StopAsyncIteration:
                # The provider succeeded and had nothing to say. That is a
                # served turn with an empty reply, not a degraded provider —
                # falling back here would hide a real (if useless) answer.
                return name, "", trail

            # Committed: this profile serves the turn. No mid-stream fallback.
            tokens = [first]
            async for token in gen:
                tokens.append(token)
            return name, "".join(tokens), trail

        raise AllProvidersFailed(
            "every profile in the chain degraded: "
            + ", ".join(f"{frm}({reason})" for frm, _to, reason in trail)
        )
