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

* **Ordered, user-owned.** ``[active_profile, *fallback_chain]`` in exactly the
  order the user wrote it (MODEL-03). No scoring, no reordering, no cleverness.
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
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

from .compose import PromptComposer
from .ports import (
    AdapterError,
    AllProvidersFailed,
    ChatAdapter,
    FallbackReason,
    Message,
    TurnResult,
    Usage,
)

if TYPE_CHECKING:
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
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._secret_store = secret_store
        self._trace = trace
        #: D-09 stub: fragments are injected. Real skill discovery is Phase 6,
        #: and it plugs into this same ``(name, text)`` shape.
        self._skill_fragments: list[tuple[str, str]] = list(skill_fragments)
        self._composer = PromptComposer()
        #: The ephemeral conversation, user/assistant only. The system message is
        #: composed fresh each turn so a live config edit takes effect (WARM).
        self.history: list[Message] = []

    @classmethod
    def build(
        cls,
        config: LlmConfig,
        adapter: ChatAdapter,
        *,
        secret_store: SecretResolver | None = None,
        trace: TraceSink | None = None,
        skill_fragments: Sequence[tuple[str, str]] = (),
    ) -> Agent:
        """Construct an agent for ``config`` served through ``adapter``."""
        return cls(
            config,
            adapter,
            secret_store=secret_store,
            trace=trace,
            skill_fragments=skill_fragments,
        )

    # ---------------------------------------------------------------- chain --

    def _chain(self) -> list[tuple[str, ModelProfile]]:
        """Return ``[(name, profile), ...]`` in the user's declared order.

        The NAME is carried alongside the profile because it is not *on* it:
        a profile's name is the key it sits under in ``LlmConfig.profiles`` and
        does not cross the adapter port. ``served_by`` and every hop reason are
        reported with these names, so the loop must hold them itself.
        """
        names = [self._config.active_profile, *self._config.fallback_chain]
        return [(name, self._config.profiles[name]) for name in names]

    def system_prompt(self) -> str:
        """Return THE system prompt for the next turn (D-02 — one composer).

        The CLI's prompt inspector calls this same path; there is no second
        derivation anywhere, which is what makes the inspector incapable of
        understating what was sent.
        """
        return self._composer.compose(self._config.base_prompt, self._skill_fragments)

    async def warmup(self) -> None:
        """Preload every profile in the chain so cold load is not charged later.

        The two-clock design (Pitfall 2): model cold-load time is paid HERE, at
        build/startup, and the per-turn deadline then measures only a warm
        model's time-to-first-token. An adapter that exposes no ``preload`` —
        the shipped fake, for instance — makes this a no-op; the real adapter
        wires an empty-prompt load in a later plan.
        """
        preload = getattr(self._adapter, "preload", None)
        if preload is None:
            return
        for _name, profile in self._chain():
            await preload(profile)

    # ----------------------------------------------------------------- turn --

    async def turn(self, user_text: str) -> TurnResult:
        """Serve one user turn, falling back down the chain as needed.

        Raises:
            AllProvidersFailed: every profile in the chain degraded.
        """
        system = self.system_prompt()
        messages: list[Message] = [
            Message("system", system),
            *self.history,
            Message("user", user_text),
        ]

        served_by, reply, trail = await self._run_chain(messages)

        # SPIKE-05: read usage ONCE, after the stream fully aggregated. Several
        # providers publish counts only on the final message, so a per-chunk
        # read reports None almost every time.
        usage: Usage = self._adapter.last_usage()

        self.history.append(Message("user", user_text))
        self.history.append(Message("assistant", reply))

        return TurnResult(
            text=reply,
            served_by=served_by,
            usage=usage,
            fallback_trail=trail,
            handoff=None,  # Phase-4 seam, inert here
        )

    async def _run_chain(
        self, messages: Sequence[Message]
    ) -> tuple[str, str, list[Hop]]:
        """Return ``(served_by, reply, trail)`` from the first profile to commit."""
        chain = self._chain()
        trail: list[Hop] = []

        for index, (name, profile) in enumerate(chain):
            next_name = chain[index + 1][0] if index + 1 < len(chain) else ""
            gen = self._adapter.stream(profile, messages)

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
