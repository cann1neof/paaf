# SPDX-License-Identifier: Apache-2.0
"""MODEL-08: the one port between PAAF and whatever agent framework serves a turn.

The project's founding constraint is that the agent framework stays swappable —
so the surface between PAAF and it must be narrow enough to re-implement, and
PAAF-typed enough that swapping it changes no caller. This module is that
surface, and it is deliberately small:

* **one method that matters** — :meth:`ChatAdapter.stream` yields reply tokens,
  plus :meth:`ChatAdapter.last_usage` for the post-aggregation token counts;
* **PAAF value types only** — :class:`Message`, :class:`Usage`,
  :class:`TurnResult`. No framework object appears in any signature here, so a
  caller can hold the whole contract in their head;
* **PAAF exceptions only** — every way a provider can degrade maps to exactly
  one :class:`AdapterError` subclass carrying exactly one :class:`FallbackReason`.
  An adapter translates its framework's exception zoo into these four; the
  fallback loop then classifies a hop by reading ``.reason`` and never by
  matching a foreign exception type.

**ZERO framework imports.** This module imports nothing but the standard library
(``ModelProfile`` is referenced under ``TYPE_CHECKING`` only). That is what lets
the shipped :class:`~paaf_llm.fake.FakeAdapter` — and therefore the entire test
suite — run with the agent framework uninstalled (SC#1). ``tests/test_ports.py``
asserts it against this file's source text, and import-linter asserts it against
the import graph.

**The Phase-4 mesh (MESH-01/02), and why it did not change the port.** The mesh
needs a tool vocabulary — a model must be *offered* the handoff tools and the
engine must read back the one it *called*. ``ChatAdapter`` can carry neither, and
D-02 forbids reshaping it. So the vocabulary lives in a SECOND protocol,
:class:`ToolCallingChatAdapter`, which EXTENDS ``ChatAdapter`` rather than
editing it: the two Phase-3 methods keep their exact signatures, and every
Phase-3 caller is untouched. The engine feature-detects with ``isinstance`` and,
on an adapter that is *not* a :class:`ToolCallingChatAdapter`, runs the
single-agent path and says so out loud (:attr:`MeshSignalKind.MESH_UNAVAILABLE`)
rather than behaving as if no peer were ever declared.

:attr:`TurnResult.handoff` is the seam Phase 3 declared for exactly this, and it
now carries a real :class:`HandoffRequest` instead of a placeholder alias — which
is the whole point of having declared it early: adding handoff added no method to
``ChatAdapter`` and moved no signature.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .profiles import ModelProfile

#: Who authored a message. Deliberately a closed set: an adapter maps these
#: three onto whatever role vocabulary its provider uses, never the reverse.
Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class Message:
    """One turn of conversation, as PAAF represents it.

    Frozen because the message list crosses the port into third-party code: an
    adapter must not be able to rewrite what the user said on the way out, and
    the trace must be able to record the same object the model was handed.
    """

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Token counts for one turn, read AFTER the stream is aggregated.

    Both counts are optional because they honestly may be unknown: several local
    providers report no usage at all (SPIKE-05). ``None`` means "the provider did
    not say", which is information the user should see — it is not the same as
    zero, and inventing a number here would make the trace lie.
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One tool offered to a model, in PAAF terms — no framework type anywhere.

    Frozen for the same reason :class:`Message` is: a spec crosses the port into
    third-party adapter code, and an adapter must not be able to rewrite what the
    model was offered on the way out. In Phase 4 the only specs that exist are the
    mesh's own (one ``transfer_to_<peer>`` per declared peer, plus the observer's
    grant); the user-facing tool registry is Phase 5 and is a separate thing.

    ``parameters`` is a JSON Schema object. An empty dict means "no arguments",
    which is what every handoff tool uses: the target lives in the tool's NAME,
    so there is no argument for a model to get wrong.
    """

    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool call a model emitted, read AFTER the stream is aggregated.

    The same post-aggregation rule — and the same reason — as
    :meth:`ChatAdapter.last_usage`: providers publish tool-call arguments as
    partial JSON fragments across chunks, so a mid-stream read yields an
    unparseable fragment rather than a call. Only the assembled message carries
    ``arguments`` as a dict.

    ``call_id`` is optional because it honestly may not exist: several providers
    emit no id at all. PAAF never needs one — a handoff call is answered by
    running the next leg, not by a tool message (see :data:`Role`) — so it is
    recorded for provenance and never depended on.
    """

    name: str
    arguments: dict[str, object]
    call_id: str | None = None


class FallbackReason(str, Enum):
    """Why the engine moved on from a profile (MODEL-03/04, D-04/D-05).

    A ``str`` enum so a reason serializes into the trace's JSON fallback trail
    and prints in the CLI's ``↳ fell back to <profile> (<reason>)`` notice
    without a lookup table.
    """

    CONNECTION = "connection"  # hard reach failure (MODEL-03)
    TIMEOUT = "timeout"  # request timeout (MODEL-04)
    HTTP_5XX = "http_5xx"  # server error (MODEL-04)
    HTTP_429 = "http_429"  # rate limited / overloaded (MODEL-04)
    SLOW_FIRST_TOKEN = "slow_first_token"  # missed the budget (D-04/D-05)


class AdapterError(Exception):
    """Base for every PAAF-typed adapter failure; carries a :class:`FallbackReason`.

    An adapter raises one of the four concrete subclasses; it never lets a
    framework exception escape. The engine catches this base and reads
    ``.reason`` — so adding a provider adds a translation, never a new branch in
    the fallback loop.

    The base itself declares ``reason`` without a value: there is no such thing
    as a generically-degraded provider, so an unclassified failure should fail
    loudly rather than silently pick a reason.
    """

    reason: ClassVar[FallbackReason]


class ConnectionFailed(AdapterError):
    """The provider could not be reached at all (DNS, refused, unreachable)."""

    reason: ClassVar[FallbackReason] = FallbackReason.CONNECTION


class RequestTimedOut(AdapterError):
    """The provider accepted the request but the call timed out."""

    reason: ClassVar[FallbackReason] = FallbackReason.TIMEOUT


class ServerError(AdapterError):
    """The provider answered with a server-side (5xx) failure."""

    reason: ClassVar[FallbackReason] = FallbackReason.HTTP_5XX


class RateLimited(AdapterError):
    """The provider refused for rate-limit / overload reasons (429)."""

    reason: ClassVar[FallbackReason] = FallbackReason.HTTP_429


# NOTE: there is deliberately no adapter error for SLOW_FIRST_TOKEN. That
# reason is produced by the ENGINE's per-profile first-token deadline, because
# "too slow" is the USER's judgement (``ModelProfile.first_token_budget_s``),
# not the provider's. An adapter that could raise it would be defining the
# budget on the user's behalf (D-04/D-05).


class AllProvidersFailed(Exception):
    """Every profile in the ordered chain degraded — the turn cannot be served.

    Terminal, and pointedly NOT an :class:`AdapterError`: an ``AdapterError``
    means "try the next profile", whereas this means there is no next profile.
    Subclassing it under ``AdapterError`` would let a fallback loop swallow the
    end of the chain as one more hop.
    """


class EngineError(Exception):
    """A configuration or unknown failure — NOT a degraded provider.

    A missing or unresolvable API key, a model name the provider does not have,
    or a bug in the real adapter all surface here. None of those is a provider
    having a bad minute; each is something the user must fix, and each stays
    broken however many models the chain tries next.

    Deliberately NOT an :class:`AdapterError`, for the same reason
    :class:`AllProvidersFailed` is not one: an ``AdapterError`` means "try the
    next profile", so the ordered fallback loop would absorb a config error as
    one more plausible hop and print ``↳ fell back to cloud (connection)`` at
    someone whose real problem is a typo — a confident, wrong explanation, which
    is exactly the hidden behavior this project refuses.

    It lives HERE, in the port, rather than beside the real adapter that raises
    it, and that placement is load-bearing rather than tidy. The adapter package
    is behind an optional extra and is unimportable without the agent framework,
    so a caller running framework-uninstalled — the CLI — could not name this
    class in an ``except`` clause at all if it were defined there. Being a port
    type is what lets the CLI catch a bind failure and print one readable line
    instead of a traceback. The adapter package imports this exact class object;
    there is no second definition of it anywhere.
    """


class UndeclaredPeer(Exception):
    """A model asked to hand off to an agent it was never given (MESH-02).

    A SIBLING of :class:`AllProvidersFailed` and :class:`EngineError`, and
    pointedly not an :class:`AdapterError`. The taxonomy above partitions failure
    into three meanings — "try the next profile", "there is no next profile",
    "the user must fix something" — and a routing violation is none of them.
    Filing it under ``AdapterError`` would let the fallback loop absorb it as one
    more plausible hop and print ``↳ fell back to cloud (connection)`` at what is
    actually a model naming a peer that does not exist for it: a confident, wrong
    explanation, which is the hidden behavior this project refuses. Nor is it an
    ``EngineError``: :class:`~paaf_llm.profiles.LlmConfig` already proved the
    declared graph integral at load, so there is nothing in the YAML for the user
    to fix — the model reached OUTSIDE the graph.

    It lives HERE, in the port, for the same load-bearing reason
    :class:`EngineError` does. The framework-free CLI must be able to name it in
    an ``except`` clause, and the adapter package is behind an optional extra and
    unimportable without the agent framework — so a class defined beside the
    adapter could not be caught by a caller running framework-uninstalled at all.

    Raising it is deliberately NOT the only guard. The mesh removes the
    capability first (only declared peers are ever offered as tools) and then
    checks the answer anyway, because models routinely emit tool names that were
    never bound. A guard that fires only when a third party misbehaves is still a
    guard that must exist — and it is the one mesh guarantee that holds in every
    configuration, observed or not (D-13).
    """


class MeshSignalKind(str, Enum):
    """The externally-observable mesh events (D-05 — "light a flashlight").

    A ``str`` enum for the same reason :class:`FallbackReason` is one: a kind
    serializes into the trace's JSON and prints in a CLI notice with no lookup
    table in between.

    All six members are declared together even though later plans in this phase
    are what trigger four of them. ``ports.py`` is edited by exactly one plan, so
    declaring the vocabulary once is what stops a later wave from having to
    serialize behind another edit to this file.
    """

    UNDECLARED_PEER = "undeclared_peer"  # MESH-02: a target outside the graph
    BUDGET_EXHAUSTED = "budget_exhausted"  # D-08/D-09: the hop wall was reached
    OBSERVER_RETRY = "observer_retry"  # D-05: the attempt was bounced back
    OBSERVER_REROUTE = "observer_reroute"  # D-05: the observer picked a peer
    UNOBSERVED = "unobserved"  # D-07: the mesh is running unsupervised
    MESH_UNAVAILABLE = "mesh_unavailable"  # the adapter cannot be offered tools


@dataclass(frozen=True, slots=True)
class MeshSignal:
    """One mesh event, correlated to the user turn it happened inside.

    ``turn_id`` is an engine-generated identifier, never a database row id: the
    trace store's writer is fire-and-forget and never surfaces ``lastrowid``, so
    correlating on one would force a writer redesign (Finding 5).

    ``to_agent`` is the target the event is ABOUT — for
    :attr:`MeshSignalKind.UNDECLARED_PEER` that is the target the model attempted
    and did not get, which is precisely the value worth surfacing.
    """

    kind: MeshSignalKind
    turn_id: str
    from_agent: str
    to_agent: str
    detail: str = ""


class MeshSignalSink(Protocol):
    """The one method the engine needs to make a mesh event externally visible.

    Narrow on purpose, and modelled on :class:`~paaf_llm.agent.TraceSink` for the
    same reason: a sink is the contract, and a test — or Phase 10's WebSocket
    channel — can satisfy it in four lines without ``paaf_llm`` ever learning what
    a WebSocket is.

    Synchronous and fire-and-forget by contract. A signal is a notification, not
    a request: the engine must never wait on a listener, and the turn's outcome
    must never depend on one being attached.
    """

    def signal(self, event: MeshSignal) -> None: ...


@dataclass(frozen=True, slots=True)
class HandoffRequest:
    """An ACCEPTED handoff — the one that actually happened (MESH-01/02).

    Frozen, and named at both ends so "which agent answered me, and who passed it
    to them?" is answerable from the :class:`TurnResult` itself, in the same
    spirit as ``served_by`` and ``fallback_trail``.

    A *rejected* attempt is never one of these: it raises
    :class:`UndeclaredPeer`. Representing a refused handoff as a
    ``HandoffRequest`` would make the type ambiguous about whether the transfer
    took place, which is the one thing it exists to state.
    """

    from_agent: str
    to_agent: str


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The outcome of one completed turn, with its provenance attached.

    ``served_by`` names the profile that ACTUALLY produced the reply and
    ``fallback_trail`` lists the ``(from_profile, to_profile, reason)`` hops that
    preceded it — so "which model answered me, and why not the one I picked?" is
    answerable from the result itself rather than reconstructed from logs (D-06,
    SC#4).

    ``handoff`` is the seam Phase 3 declared and Phase 4 filled in. It names the
    accepted transfer when one happened (MESH-01) and stays ``None`` when the
    awake agent simply answered — the common case. A REFUSED handoff is never
    reported here; it raises :class:`UndeclaredPeer`, so this field cannot be
    read as "something was attempted".
    """

    text: str
    served_by: str
    usage: Usage
    #: Ordered ``(from_profile, to_profile, reason)`` hops taken before
    #: ``served_by`` committed. Empty when the active profile served the turn.
    fallback_trail: list[tuple[str, str, str]] = field(default_factory=list)
    handoff: HandoffRequest | None = None


@runtime_checkable
class ChatAdapter(Protocol):
    """The durable contract every model backend is reached through.

    Two methods, both PAAF-typed. An implementation may be the shipped
    :class:`~paaf_llm.fake.FakeAdapter` or a real framework-backed adapter; the
    engine cannot tell the difference, which is the whole point (SC#1).
    """

    def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        """Yield the reply's tokens in order for ``profile``.

        Raises:
            AdapterError: one of the four concrete subclasses when the provider
                is unreachable, times out, errors, or rate-limits. A framework
                exception must never escape this call — translating it is the
                adapter's job, and the reason it exists.
        """
        ...

    def last_usage(self) -> Usage:
        """Return token usage for the most recently completed stream.

        Read AFTER aggregation, never per chunk: several providers only report
        usage on the final message, so sampling mid-stream yields ``None`` or a
        partial count (SPIKE-05).
        """
        ...


@runtime_checkable
class ToolCallingChatAdapter(ChatAdapter, Protocol):
    """A :class:`ChatAdapter` that can additionally be offered tools (D-01).

    Deliberately a SECOND protocol rather than two more methods on
    ``ChatAdapter``: the Phase-3 port keeps exactly the shape it declared, so
    D-02 is satisfied literally — no method added to it, no signature moved, no
    existing caller touched. The engine feature-detects with
    ``isinstance(adapter, ToolCallingChatAdapter)``.

    An adapter that is NOT one is not a bug and is not silently degraded: the
    engine runs the Phase-3 single-agent path and emits
    :attr:`MeshSignalKind.MESH_UNAVAILABLE`, so a user who declared peers and got
    no mesh is told why rather than left to infer it from an assistant that never
    hands off.

    ``runtime_checkable`` checks method PRESENCE only, which is all the engine
    needs here — it is choosing between two call shapes, not validating a
    contract.
    """

    def stream_with_tools(
        self,
        profile: ModelProfile,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> AsyncIterator[str]:
        """Yield the reply's tokens for ``profile``, with ``tools`` offered.

        Semantically :meth:`ChatAdapter.stream` plus a tool surface: the same
        token stream, the same :class:`AdapterError` translation contract, and no
        framework type in or out. An empty ``tools`` must behave exactly like
        ``stream`` — offering nothing is not a different mode.

        Raises:
            AdapterError: one of the four concrete subclasses, on exactly the
                same terms as :meth:`ChatAdapter.stream`.
        """
        ...

    def last_tool_calls(self) -> tuple[ToolCall, ...]:
        """Return the tool calls from the most recently completed stream.

        Read AFTER aggregation, never per chunk — the same rule and the same
        reason as :meth:`ChatAdapter.last_usage`, but with sharper teeth here:
        mid-stream a provider emits tool-call ARGUMENTS as partial JSON
        fragments, so a per-chunk read does not return a half-filled call, it
        returns unparseable text. Only the assembled message carries the call
        with its arguments as a dict.

        Empty when the model called nothing, which is the ordinary case — a turn
        in which the awake agent simply answered.
        """
        ...
