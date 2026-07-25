# SPDX-License-Identifier: Apache-2.0
"""A fake TTS engine for the TTFA regression gate (TRACE-04, D-08/D-09).

:class:`FakeTTS` stands in for a real speech engine so ``time_to_first_audio`` can be
*measured* — and CI can defend that measurement — before Phase 7's real Chatterbox exists.

It is driven entirely by an **injected controllable clock** (the ``frozen_clock`` fixture
from Plan 01: ``.now()`` / ``.advance(seconds)``), never wall-clock. When asked to
synthesize it:

1. records ``started_at`` = ``clock.now()``,
2. advances the clock by the injected first-audio ``delay`` and yields the FIRST audio
   chunk, recording ``first_audio_at`` at that instant,
3. keeps advancing the clock as it yields the remaining ("tail") chunks, so the *whole
   round trip* is strictly longer than the first-audio latency — which is exactly what
   lets the negative control distinguish a correct first-audio measurement from a broken
   recorder that times the entire synthesis.

Because the clock only moves when :meth:`synthesize` advances it, the recorded TTFA is
deterministic to the injected ``delay`` with zero measurement noise — no ``time.sleep``,
no flaky wall-clock (the rejected Anti-Pattern).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol


class _Clock(Protocol):
    """The slice of the ``frozen_clock`` fixture FakeTTS depends on."""

    def now(self) -> float: ...

    def advance(self, seconds: float) -> float: ...


class FakeTTS:
    """A deterministic fake TTS that emits first audio after an injected delay.

    Args:
        clock: a controllable clock exposing ``now()`` and ``advance(seconds)`` (the
            deterministic ``frozen_clock`` fixture — never wall-clock).
        delay: seconds of injected latency before the FIRST audio chunk is emitted. This
            is the ground-truth ``time_to_first_audio`` a correct recorder must reproduce.
        tail_step: seconds the clock advances between each subsequent ("tail") chunk.
            Defaults to ``0.1``; kept smaller than ``delay`` so the whole round trip stays
            realistic yet strictly exceeds first-audio latency.
        tail_chunks: how many chunks follow the first one.

    After :meth:`synthesize` is consumed, ``started_at`` / ``first_audio_at`` / ``ended_at``
    expose the three clock readings the recorder needs.
    """

    #: A placeholder PCM-ish payload; contents are irrelevant to a timing gate.
    _CHUNK = b"\x00\x01\x02\x03"

    def __init__(
        self,
        clock: _Clock,
        delay: float,
        *,
        tail_step: float = 0.1,
        tail_chunks: int = 3,
    ) -> None:
        self._clock = clock
        self._delay = float(delay)
        self._tail_step = float(tail_step)
        self._tail_chunks = int(tail_chunks)
        self.started_at: float | None = None
        self.first_audio_at: float | None = None
        self.ended_at: float | None = None

    def synthesize(self, text: str = "") -> Iterator[bytes]:
        """Yield audio chunks, advancing the injected clock as a real engine would.

        The first chunk is emitted after ``delay`` seconds of clock time; each tail chunk
        advances the clock a further ``tail_step``. Consuming the whole iterator sets
        ``ended_at``, so a (broken) whole-round-trip recorder is distinguishable from a
        correct first-audio one.
        """
        self.started_at = self._clock.now()
        # First audio arrives after the injected latency — this is the number under test.
        self._clock.advance(self._delay)
        self.first_audio_at = self._clock.now()
        yield self._CHUNK
        # Remaining audio: the round trip is strictly longer than first-audio latency.
        for _ in range(self._tail_chunks):
            self._clock.advance(self._tail_step)
            yield self._CHUNK
        self.ended_at = self._clock.now()
