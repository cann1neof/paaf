"""Tests for the SPIKE-08 round-trip harness (``roundtrip.py``).

Two layers:

* FAST, engine-free — the per-stage accounting: the residual closes the books against the
  wall (``stages_reconstruct_wall``) and is ~0 (``residual_is_small``), WITH negative
  controls (a mis-computed residual, and a large residual, must both be flagged). These run
  in the base venv.
* SLOW, real STT->LLM->TTS — one actual round trip, asserting the stages sum to the wall
  and the unattributed residual is ~0. Gated on the voice-venv interpreter (and needs the
  Ollama daemon), so a missing engine is a loud failure THERE and a clean skip elsewhere.

``roundtrip`` imports the engines INSIDE functions, so importing it here is safe in the base
venv; only the slow test touches a model.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import roundtrip as rt  # noqa: E402

IN_VOICE_VENV = Path(sys.prefix).resolve() == (Path(__file__).resolve().parent / ".venv").resolve()
voice_only = pytest.mark.skipif(
    not IN_VOICE_VENV,
    reason="needs the voice venv (chatterbox/torch/faster-whisper) + the Ollama daemon",
)


# --------------------------------------------------------------------------------------
# FAST — accounting logic + negative controls
# --------------------------------------------------------------------------------------


def test_make_iteration_closes_the_books():
    row = rt.make_iteration(t_stt=3.0, t_llm=1.0, t_tts=6.0, wall=10.25)
    # residual = 10.25 - 10.0 = 0.25, and the four parts reconstruct the wall exactly.
    assert row["t_unattributed"] == pytest.approx(0.25)
    assert rt.stages_reconstruct_wall(row) is True


def test_negative_control_wrong_residual_fails_reconstruction():
    row = rt.make_iteration(t_stt=3.0, t_llm=1.0, t_tts=6.0, wall=10.0)
    row["t_unattributed"] += 5.0  # corrupt the books
    assert rt.stages_reconstruct_wall(row) is False


def test_residual_near_zero_is_honest_accounting():
    row = rt.make_iteration(t_stt=3.0, t_llm=1.0, t_tts=6.0, wall=10.01)
    assert rt.residual_is_small(row) is True


def test_negative_control_large_residual_is_not_small():
    # 4s of unaccounted time on a 14s wall — the per-stage budget cannot be trusted.
    row = rt.make_iteration(t_stt=3.0, t_llm=1.0, t_tts=6.0, wall=14.0)
    assert row["t_unattributed"] == pytest.approx(4.0)
    assert rt.residual_is_small(row) is False


def test_build_budget_shares_sum_to_one():
    cold = rt.make_iteration(5.0, 2.0, 12.0, 19.5)
    warm = [rt.make_iteration(3.0, 1.0, 6.0, 10.1),
            rt.make_iteration(3.2, 1.1, 6.4, 10.8)]
    budget = rt.build_budget(cold, warm)
    shares = [budget["stages"][s]["share"]
              for s in ("stt", "llm", "tts", "unattributed")]
    assert sum(shares) == pytest.approx(1.0, abs=1e-3)
    assert budget["dominant_stage"] == "tts"


def test_build_budget_requires_warm_samples():
    cold = rt.make_iteration(3.0, 1.0, 6.0, 10.0)
    with pytest.raises(ValueError):
        rt.build_budget(cold, [])


# --------------------------------------------------------------------------------------
# SLOW — a real WAV-in -> WAV-out round trip
# --------------------------------------------------------------------------------------


@pytest.mark.slow
@voice_only
def test_real_roundtrip_stages_sum_to_wall():
    result = rt.run(n_warm=1)
    assert result["warmup_asserted"] is True
    assert result["stages_reconstruct_wall"] is True
    # every warm row must have a ~0 residual, else the budget is fiction.
    for row in result["warm_iterations"]:
        assert rt.residual_is_small(row), f"residual too large: {row['t_unattributed']}"
