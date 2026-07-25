"""Tests for the SPIKE-03 TTFA harness (``measure_ttfa.py``).

Two layers:

* FAST, engine-free — the ``warm_beats_cold`` / ``summarize`` accounting, WITH a negative
  control (a result where warm == cold must NOT read as a pass). These run in the base venv.
* SLOW, real Chatterbox — one actual ``mps`` measurement, asserting warm < cold OR (if mps
  is unusable on this box) that the failure was recorded verbatim per D-11/D-12. Gated on
  the voice-venv interpreter so a missing engine is a loud failure THERE and a clean skip
  elsewhere — never a silently vanishing check.

``measure_ttfa`` imports torch/chatterbox INSIDE functions, so importing it here is safe in
the base venv; only the slow tests touch a model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_ttfa as mt  # noqa: E402

IN_VOICE_VENV = Path(sys.prefix).resolve() == (Path(__file__).resolve().parent / ".venv").resolve()
voice_only = pytest.mark.skipif(
    not IN_VOICE_VENV,
    reason="needs the voice venv (chatterbox/torch); run under spike/voice/.venv",
)


# --------------------------------------------------------------------------------------
# FAST — accounting logic + negative control
# --------------------------------------------------------------------------------------


def _result(cold_total: float, warm: list[float]) -> dict:
    return {"ok": True, **mt.summarize(cold_total, warm)}


def test_warm_below_cold_reads_as_pass():
    r = _result(cold_total=40.0, warm=[18.0, 19.0, 20.0])
    assert mt.warm_beats_cold(r) is True


def test_negative_control_warm_equal_cold_is_not_a_pass():
    # If the warmup discipline did nothing (warm p50 == cold total), the check MUST fail —
    # otherwise it is vacuous. cold_total set equal to the warm median.
    r = _result(cold_total=19.0, warm=[18.0, 19.0, 20.0])
    assert r["warm_p50_seconds"] == r["cold_total_seconds"]
    assert mt.warm_beats_cold(r) is False


def test_negative_control_a_failed_result_is_not_a_pass():
    assert mt.warm_beats_cold({"ok": False, "error_type": "RuntimeError"}) is False


def test_summarize_rejects_empty_warm():
    with pytest.raises(ValueError):
        mt.summarize(10.0, [])


def test_summarize_reports_p50_p95_min_max():
    s = mt.summarize(50.0, [10.0, 12.0, 14.0, 16.0, 100.0])
    assert s["warm_min_seconds"] == 10.0
    assert s["warm_max_seconds"] == 100.0
    assert s["warm_p50_seconds"] == 14.0
    # p95 on 5 samples (nearest-rank) is the worst case — variance is not hidden.
    assert s["warm_p95_seconds"] == 100.0


# --------------------------------------------------------------------------------------
# SLOW — a real Chatterbox mps measurement
# --------------------------------------------------------------------------------------


@pytest.mark.slow
@voice_only
def test_real_mps_measurement_warm_beats_cold():
    r = mt.measure_one_device("mps", n_warm=2)
    if r["ok"]:
        # The steady-state latency must beat the cold start by the model-load margin.
        assert r["warm_p50_seconds"] < r["cold_total_seconds"]
        assert mt.warm_beats_cold(r) is True
        assert r["warm_n"] == 2
        assert r["watermark_inside_timed_region"] is True
    else:
        # mps unusable is a VALID result (D-11/D-12) — assert it was captured verbatim.
        assert r["error_type"]
        assert r["traceback"]
