# SPDX-License-Identifier: Apache-2.0
"""The shipped fake chat adapter — the substrate the whole suite runs on (SC#1).

This package **ships in the wheel** and **MUST run with the agent framework
uninstalled**. That is not a convenience; it is the proof that
:class:`~paaf_llm.ports.ChatAdapter` is a port rather than a mirror of whatever
framework happens to be underneath. ``pip install paaf-llm`` (no ``[engine]``
extra, so no LangChain anywhere) has to import this module and run the entire
fallback / composition / trace suite green. Consequently **no framework import
may ever appear under this package** — asserted by
``tests/test_fake_adapter.py`` against this file's source and by import-linter
against the import graph.

It is driven entirely by an **injected script**, never by wall-clock luck or a
live provider: :meth:`FakeAdapter.program` records, per profile, the tokens to
emit, an optional degraded failure to raise, an optional first-token delay, the
usage to report, and — since Phase 4 — the tool calls to emit. Every fallback and
mesh test in these phases is a different program.

**Phase 4 (MESH-01/02): this fake is also a**
:class:`~paaf_llm.ports.ToolCallingChatAdapter`. That is what makes SC#5 reach the
mesh rather than stopping at the single-agent loop — the whole handoff suite runs
here, framework-uninstalled. Two properties are load-bearing and easy to lose:
:attr:`FakeAdapter.tool_offers` records what was OFFERED (so capability removal is
provable, not merely asserted), and ``program(tool_calls=...)`` deliberately does
**not** validate its names against the offered set (so the runtime peer guard has
a negative control — a model calling a tool nobody bound is a routine failure
mode, not a hypothetical).

**The one thing this fake deliberately does NOT do** is decide that a first token
was too slow. ``first_token_delay_s`` makes the fake *slow*; classifying that as
:attr:`~paaf_llm.ports.FallbackReason.SLOW_FIRST_TOKEN` is the engine's job,
because the budget belongs to the user (``ModelProfile.first_token_budget_s``,
D-04/D-05). A fake that raised the reason itself would let a broken engine —
one with no deadline at all — pass the very test written to catch it.

**Profile addressing.** :class:`~paaf_llm.profiles.ModelProfile` carries no
``name`` field: a profile's name is the key it sits under in
``LlmConfig.profiles``, so it does not travel with the profile across the port.
Programs are therefore keyed by :attr:`PROFILE_KEY_FIELD` (``model``), which the
test fixtures set equal to the profile's name. A profile object that does happen
to expose ``.name`` — a future schema, or a caller's own type — is honored first.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..ports import AdapterError, Message, ToolCall, ToolSpec, Usage

if TYPE_CHECKING:
    from ..profiles import ModelProfile

#: The ``ModelProfile`` field a program is keyed by. See the module docstring:
#: the profile's *name* lives in the ``LlmConfig.profiles`` dict key and does not
#: cross the port, so the fake addresses profiles by this field instead.
PROFILE_KEY_FIELD = "model"

#: Reported by :meth:`FakeAdapter.last_usage` when a program named no usage.
#: Concrete counts on purpose: a default of ``Usage()`` (both ``None``) would let
#: an aggregated-usage test pass against an engine that never read usage at all.
DEFAULT_USAGE = Usage(prompt_tokens=7, completion_tokens=3)


@dataclass(slots=True)
class _Program:
    """One profile's scripted behavior for a single :meth:`FakeAdapter.stream`."""

    tokens: list[str] = field(default_factory=list)
    fail: type[AdapterError] | None = None
    first_token_delay_s: float = 0.0
    usage: Usage = DEFAULT_USAGE
    #: MESH-01: the tool calls this profile emits once its stream has drained.
    #: Published ONLY on the :meth:`FakeAdapter.stream_with_tools` path — a
    #: provider that was offered no tools cannot call one.
    tool_calls: tuple[ToolCall, ...] = ()


class FakeAdapter:
    """A deterministic :class:`~paaf_llm.ports.ChatAdapter` driven by a script.

    Program a profile, then stream it::

        adapter.program("local", tokens=["hel", "lo"])
        adapter.program("cloud", fail=ServerError)

    Un-programmed profiles raise :class:`LookupError` rather than streaming
    nothing. That is deliberate: an empty stream is indistinguishable from a
    working provider that had nothing to say, so a forgotten ``program()`` call
    would silently weaken whatever test forgot it. ``LookupError`` is pointedly
    NOT an :class:`~paaf_llm.ports.AdapterError`, so a fallback loop cannot
    swallow the mistake as one more plausible-looking hop.
    """

    def __init__(self) -> None:
        self._programs: dict[str, _Program] = {}
        self._last_usage: Usage = DEFAULT_USAGE
        self._last_tool_calls: tuple[ToolCall, ...] = ()
        #: Every ``(profile_key, messages)`` this adapter was asked to stream, in
        #: order — the substrate for multi-turn history and composed-prompt
        #: assertions (a test can prove what actually crossed the port).
        self.calls: list[tuple[str, tuple[Message, ...]]] = []
        #: Every ``(profile_key, offered_tool_names)`` this adapter was asked to
        #: stream WITH tools, in order. This is the substrate for proving
        #: capability removal (MESH-02): a test reads it to show the peer graph —
        #: and nothing else — shaped what the model could even call. Without a
        #: record of what was OFFERED, "only declared peers are reachable" could
        #: only be tested through the guard, which is the second line of defence,
        #: not the first.
        self.tool_offers: list[tuple[str, tuple[str, ...]]] = []

    def program(
        self,
        profile_name: str,
        *,
        tokens: list[str] | None = None,
        fail: type[AdapterError] | None = None,
        first_token_delay_s: float = 0.0,
        usage: Usage | None = None,
        tool_calls: Sequence[ToolCall] | None = None,
    ) -> None:
        """Script what ``profile_name`` does on its next (and every) stream.

        Args:
            profile_name: the profile this script answers for.
            tokens: the reply tokens to emit, in order.
            fail: an :class:`~paaf_llm.ports.AdapterError` subclass to raise on
                the first token instead of streaming — one of the four degraded
                triggers the fallback loop must classify.
            first_token_delay_s: seconds to wait before the FIRST token. The
                engine's deadline decides whether that is too slow; this adapter
                never does (D-04/D-05).
            usage: what :meth:`last_usage` reports once the stream is aggregated.
            tool_calls: what :meth:`last_tool_calls` reports once the stream is
                aggregated, on the :meth:`stream_with_tools` path (MESH-01). The
                names here are NOT checked against what was offered, and that is
                the point: scripting a call to a tool the engine never bound is
                how the MESH-02 runtime guard gets a negative control at all
                (Pitfall 4). A real model does this; the fake must be able to.
        """
        self._programs[profile_name] = _Program(
            tokens=list(tokens or []),
            fail=fail,
            first_token_delay_s=first_token_delay_s,
            usage=usage if usage is not None else DEFAULT_USAGE,
            tool_calls=tuple(tool_calls or ()),
        )

    async def _scripted(self, key: str, *, tools_offered: bool) -> AsyncIterator[str]:
        """Run ``key``'s program — the ONE body both entry points share.

        Extracted rather than duplicated so :meth:`stream` and
        :meth:`stream_with_tools` cannot drift: a degraded trigger, a delay, or
        the publish-after-drain rule fixed on one path but not the other would
        make half the suite quietly test a different adapter.
        """
        program = self._programs.get(key)
        if program is None:
            raise LookupError(
                f"FakeAdapter has no program for profile {key!r}; "
                f"call program({key!r}, ...) before streaming it. "
                f"Programmed profiles: {sorted(self._programs)}"
            )

        if program.fail is not None:
            raise program.fail(f"programmed {program.fail.__name__} for {key!r}")

        if program.first_token_delay_s:
            # Slow, not classified: the engine's asyncio.timeout cancels this
            # sleep and records SLOW_FIRST_TOKEN itself (D-04/D-05).
            await asyncio.sleep(program.first_token_delay_s)

        for token in program.tokens:
            yield token

        # Usage is published only after the whole stream drained — several real
        # providers report it on the final message only (SPIKE-05), so reading it
        # mid-stream would be an anti-pattern this fake must not reward. Tool
        # calls are published in the SAME place for a sharper version of the same
        # reason: mid-stream a real provider emits argument JSON in fragments, so
        # there is no call to read until the stream is aggregated.
        self._last_usage = program.usage
        # A provider that was offered no tools cannot have called one. Publishing
        # the scripted calls on the plain `stream` path would let an engine that
        # never offers tools still "receive" a handoff — and the test written to
        # catch exactly that would pass.
        #
        # `tools_offered` is the count, not the code path, and that distinction
        # matters at the hop wall: the engine withdraws the handoff tools by
        # calling `stream_with_tools` with an EMPTY tuple (D-08 — the withdrawal
        # is a statement, so it is made at the port). Keying on the path alone
        # would have this fake publish a scripted handoff for a leg that was
        # offered nothing, which is precisely the engine bug
        # `test_budget_stops_a_loop_and_withdraws_the_tool` exists to catch.
        self._last_tool_calls = program.tool_calls if tools_offered else ()

    async def stream(
        self, profile: ModelProfile, messages: Sequence[Message]
    ) -> AsyncIterator[str]:
        """Emit ``profile``'s scripted tokens, or raise its scripted failure.

        Raises:
            AdapterError: the subclass the program named, on the first token.
            LookupError: when ``profile`` was never programmed.
        """
        key = self.program_key(profile)
        self.calls.append((key, tuple(messages)))
        async for token in self._scripted(key, tools_offered=False):
            yield token

    async def stream_with_tools(
        self,
        profile: ModelProfile,
        messages: Sequence[Message],
        tools: Sequence[ToolSpec],
    ) -> AsyncIterator[str]:
        """Stream ``profile`` with ``tools`` offered, recording what was offered.

        Behaviorally identical to :meth:`stream` — same script, same degraded
        triggers, same publish-after-drain rule — plus the :attr:`tool_offers`
        recording and the scripted :meth:`last_tool_calls` publication.

        ``tools`` may be EMPTY, and that is a meaningful call rather than a
        pointless one: it is how the engine withdraws the handoff surface at the
        hop wall (D-08). The offer is recorded as an empty tuple — evidence that
        the leg ran and was given no moves — and nothing is published to
        :meth:`last_tool_calls`, because a provider offered no tools cannot have
        called one.

        Raises:
            AdapterError: the subclass the program named, on the first token.
            LookupError: when ``profile`` was never programmed. Pointedly not an
                ``AdapterError``, for the reason the class docstring gives.
        """
        key = self.program_key(profile)
        self.calls.append((key, tuple(messages)))
        self.tool_offers.append((key, tuple(tool.name for tool in tools)))
        async for token in self._scripted(key, tools_offered=bool(tools)):
            yield token

    def last_usage(self) -> Usage:
        """Return the usage published by the most recently aggregated stream."""
        return self._last_usage

    def last_tool_calls(self) -> tuple[ToolCall, ...]:
        """Return the tool calls published by the most recently aggregated stream.

        Empty unless the last stream went through :meth:`stream_with_tools` with
        at least one tool AND its program scripted calls — the ordinary case
        being a profile that just answered.
        """
        return self._last_tool_calls

    @staticmethod
    def program_key(profile: ModelProfile) -> str:
        """Return the key ``profile``'s program is registered under.

        Prefers a ``name`` attribute when the profile type has one, and falls
        back to :data:`PROFILE_KEY_FIELD`. See the module docstring for why the
        profile's own name is not available here.
        """
        name = getattr(profile, "name", None)
        if isinstance(name, str) and name:
            return name
        return str(getattr(profile, PROFILE_KEY_FIELD))
