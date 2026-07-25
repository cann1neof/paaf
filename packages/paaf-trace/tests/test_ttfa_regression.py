# SPDX-License-Identifier: Apache-2.0
"""TTFA regression gate (TRACE-04, D-08/D-09) — measured with a FAKE TTS.

This is the CI half of SC#5: make ``time_to_first_audio`` a number CI defends
*before any real audio engine exists*. A :class:`~paaf_trace._testing.fake_tts.FakeTTS`
emits its first audio chunk after a fixed injected delay ``D`` on the deterministic
``frozen_clock`` (never wall-clock), and we record ``time_to_first_audio`` through the
Plan-07 trace store, then assert:

* **accuracy** (the load-bearing half, D-08a/D-09): ``abs(recorded_ttfa - D) < TOL`` —
  proves the *measurement* is correct with no real engine.
* **overhead**: framework/measurement overhead beyond ``D`` stays under a small ceiling.
* **budget** (D-08b): ``recorded_ttfa < BUDGET``.
* **negative control** (Pitfall 3): a broken recorder that returns a constant, or that
  times the *whole round trip* instead of first-audio, MUST FAIL the accuracy assertion —
  even when it slips under BUDGET. This is what a budget-only gate would miss.

D-09 / Phase-1 evidence: ``BUDGET`` here is a **measurement/overhead-regression
guardrail, explicitly NOT a claim about shipped latency**. Real TTFA was 6.27 s on mps
with a ~10x tail; a fixed cold ceiling is not a promise about the shipped engine, it is
a tripwire for a regression in how we *account for* first-audio latency.

Nothing sleeps and no wall-clock is read anywhere — the clock is driven explicitly so
accuracy is deterministic (Anti-Pattern: flaky wall-clock accuracy test).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import aiosqlite
import pytest
from paaf_trace._testing.fake_tts import FakeTTS
from paaf_trace.metrics import compute_time_to_first_audio, record_time_to_first_audio
from paaf_trace.store import RunEvent, TraceStore

# Injected first-audio delay the fake emits after (deterministic clock ticks).
INJECTED_DELAY = 0.5
# Tight accuracy tolerance: a correct recorder reproduces D exactly on a frozen clock.
TOL = 1e-9
# Framework/measurement overhead beyond D must stay negligible (0 on a frozen clock).
OVERHEAD_CEILING = 1e-6
# Overhead-regression guardrail, NOT a shipped-latency claim (D-09). The fake's whole
# round trip (0.8 s) sits UNDER this on purpose, so budget alone can't catch the
# wrong-measurement pitfall — only the accuracy assertion can.
BUDGET = 2.0

# A recorder maps (started_at, first_audio_at, ended_at) -> recorded seconds. This seam
# lets the negative control swap in a BROKEN recorder against the same fake TTS drive.
Recorder = Callable[[float, float, float], float]


def _good_recorder(started_at: float, first_audio_at: float, ended_at: float) -> float:
    """Correct: TTFA is (first_audio - start), ignoring the tail (round trip)."""
    return compute_time_to_first_audio(started_at, first_audio_at)


def _constant_recorder(started_at: float, first_audio_at: float, ended_at: float) -> float:
    """Broken (Pitfall 3): returns a constant, ignoring the measurement entirely."""
    return 0.0


def _round_trip_recorder(started_at: float, first_audio_at: float, ended_at: float) -> float:
    """Broken (Pitfall 3): times the WHOLE round trip instead of first-audio."""
    return ended_at - started_at


async def _drive_and_record(db_path: Path, clock: object, delay: float, recorder: Recorder) -> float:
    """Drive FakeTTS on ``clock``, record TTFA via the Plan-07 store, read it back.

    Records through the real :class:`TraceStore` + ``record_time_to_first_audio`` so the
    number the gate defends is the one that actually lands on the ``runs`` row.
    """
    tts = FakeTTS(clock, delay)
    chunks = list(tts.synthesize("hello world"))
    assert chunks, "FakeTTS must emit at least one audio chunk"
    assert tts.first_audio_at is not None and tts.ended_at is not None
    seconds = recorder(tts.started_at, tts.first_audio_at, tts.ended_at)

    store = TraceStore(str(db_path))
    await store.start()
    store.emit(RunEvent(id=1, prompts="hi", model="fake-tts", started_at=tts.started_at))
    record_time_to_first_audio(store, run_id=1, seconds=seconds)
    await store.stop()

    async with aiosqlite.connect(str(db_path)) as db, db.execute(
        "SELECT time_to_first_audio FROM runs WHERE id = 1"
    ) as cur:
        (recorded,) = await cur.fetchone()
    return recorded


async def test_ttfa_accuracy(tmp_path: Path, frozen_clock: object) -> None:
    """Load-bearing (D-08a/D-09): recorded TTFA matches the injected delay tightly."""
    recorded = await _drive_and_record(
        tmp_path / "trace.db", frozen_clock, INJECTED_DELAY, _good_recorder
    )
    assert abs(recorded - INJECTED_DELAY) < TOL


async def test_ttfa_overhead_under_ceiling(tmp_path: Path, frozen_clock: object) -> None:
    """Framework/measurement overhead beyond D stays under a small ceiling."""
    recorded = await _drive_and_record(
        tmp_path / "trace.db", frozen_clock, INJECTED_DELAY, _good_recorder
    )
    overhead = recorded - INJECTED_DELAY
    assert 0.0 <= overhead < OVERHEAD_CEILING


async def test_ttfa_under_budget(tmp_path: Path, frozen_clock: object) -> None:
    """Budget guardrail (D-08b): recorded TTFA is under the fixed ceiling."""
    recorded = await _drive_and_record(
        tmp_path / "trace.db", frozen_clock, INJECTED_DELAY, _good_recorder
    )
    assert recorded < BUDGET


@pytest.mark.parametrize(
    "broken_recorder",
    [_constant_recorder, _round_trip_recorder],
    ids=["constant-zero", "whole-round-trip"],
)
async def test_accuracy_fails_for_broken_recorder(
    tmp_path: Path, frozen_clock: object, broken_recorder: Recorder
) -> None:
    """Negative control (Pitfall 3): the accuracy assertion is non-vacuous.

    A recorder that returns a constant, or that measures the whole round trip, produces
    a value that (for round-trip) still slips UNDER BUDGET yet is WRONG — so the accuracy
    assertion MUST fail. If this test stopped raising, the accuracy guard would be vacuous
    and a budget-only gate would silently pass a mis-measured metric.
    """
    recorded = await _drive_and_record(
        tmp_path / "trace.db", frozen_clock, INJECTED_DELAY, broken_recorder
    )
    # The round-trip breakage stays under budget — proving budget alone cannot catch it.
    if broken_recorder is _round_trip_recorder:
        assert recorded < BUDGET
    with pytest.raises(AssertionError):
        assert abs(recorded - INJECTED_DELAY) < TOL
