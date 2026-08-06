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

**Phase-4 seam (design-only).** :attr:`TurnResult.handoff` exists now and is
always ``None`` in Phase 3. Phase 4 (MESH-02) sets it from a parsed handoff
signal and the serving profile's declared ``peers``. It is declared here so that
adding handoff does not change the port's shape — no method is added, no
signature moves, and no existing caller is touched.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing import Any

    from .profiles import ModelProfile

    # The Phase-4 handoff payload. It does not exist yet, by design: Phase 3
    # ships the SEAM (an always-``None`` field), not the behavior. Aliasing it
    # here keeps the port's shape final while leaving the payload's definition
    # to MESH-02.
    type HandoffRequest = Any

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


@dataclass(frozen=True, slots=True)
class TurnResult:
    """The outcome of one completed turn, with its provenance attached.

    ``served_by`` names the profile that ACTUALLY produced the reply and
    ``fallback_trail`` lists the ``(from_profile, to_profile, reason)`` hops that
    preceded it — so "which model answered me, and why not the one I picked?" is
    answerable from the result itself rather than reconstructed from logs (D-06,
    SC#4).

    ``handoff`` is the Phase-4 seam and is ALWAYS ``None`` in Phase 3. It is
    declared now so that when MESH-02 adds handoff, the port's shape does not
    change: no new method, no changed signature, no touched caller.
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
