# SPDX-License-Identifier: Apache-2.0
"""Helpers for the first-class ``time_to_first_audio`` metric (TRACE-03).

``compute_time_to_first_audio`` is a pure function (start + first-audio timestamps ->
seconds); ``record_time_to_first_audio`` emits a :class:`TtfaUpdate` onto a store so the
value lands on the run row via the single writer — still off the hot path (emit never
blocks). Plan 09's CI gate reads back this column to assert accounting accuracy.
"""

from __future__ import annotations

from .store import TraceStore, TtfaUpdate


def compute_time_to_first_audio(started_at: float, first_audio_at: float) -> float:
    """Return TTFA in seconds = ``first_audio_at - started_at``.

    Raises ``ValueError`` if first audio precedes the run start (a timing bug we want
    surfaced, not silently recorded as negative latency).
    """
    ttfa = first_audio_at - started_at
    if ttfa < 0:
        raise ValueError(
            f"first_audio_at ({first_audio_at}) precedes started_at ({started_at})"
        )
    return ttfa


def record_time_to_first_audio(store: TraceStore, run_id: int, seconds: float) -> None:
    """Record ``seconds`` as the run's time_to_first_audio (non-blocking emit)."""
    store.emit(TtfaUpdate(run_id=run_id, seconds=seconds))
