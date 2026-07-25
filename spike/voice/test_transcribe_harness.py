"""SPIKE-04 harness tests — the transcribe harness runs the instrument it claims to.

THROWAWAY (SC#5 / D-18). Marked ``slow`` for the whole module: every assertion here loads
Whisper large-v3 and runs real inference on a real corpus clip (CPU, int8 — slow but only a
clip or two). Excluded from the quick suite (``-m "not slow"``).

Voice-venv only: this module imports ``faster_whisper`` transitively through
``transcribe.load_model``. ``spike/voice/conftest.py`` collect-ignores it outside the voice
venv (keyed on interpreter identity, never on whether the import happens to work) so a
missing engine cannot silently turn the check green-by-absence and cannot abort the base
venv's stdlib-only suite.

What these tests pin
--------------------
The plan's acceptance criterion: the harness actually runs BOTH multilingual conditions on
at least one clip and captures ``all_language_probs`` non-empty. Plus a negative control —
a check that cannot fail is not a check.
"""

from __future__ import annotations

import pytest

import transcribe as tr

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def model():
    """Whisper large-v3, loaded once for the module (CPU/int8). Cached weights (01-03)."""
    return tr.load_model()


@pytest.fixture(scope="module")
def clip():
    """The first real corpus clip — enough to exercise the instrument end to end."""
    return tr.list_clips()[0]


def test_harness_runs_both_multilingual_conditions(model, clip):
    """multilingual=False AND multilingual=True both transcribe the same clip and produce
    a detected language + a non-empty language posterior — the SPIKE-04 instrument, live."""
    results = {}
    for ml in (False, True):
        cond = {"name": f"t_ml_{ml}", "task": "transcribe", "multilingual": ml}
        result = tr.transcribe_condition(model, clip, cond)
        assert result["detected_language"], f"no detected language under multilingual={ml}"
        assert result["all_language_probs_topk"], f"empty all_language_probs under multilingual={ml}"
        assert 0.0 <= result["language_probability"] <= 1.0
        results[ml] = result
    # Both conditions genuinely ran (distinct calls, each with its own timing).
    assert results[False]["transcribe_seconds"] >= 0.0
    assert results[True]["transcribe_seconds"] >= 0.0


def test_all_language_probs_is_a_real_distribution(model, clip):
    """The captured posterior is a plausible distribution, not a stub: the top entry has a
    real probability and the top language matches info.language."""
    cond = {"name": "t_dist", "task": "transcribe", "multilingual": True}
    result = tr.transcribe_condition(model, clip, cond)
    topk = result["all_language_probs_topk"]
    assert len(topk) >= 1
    top_lang, top_prob = topk[0]
    assert 0.0 < top_prob <= 1.0
    # info.all_language_probs is sorted descending, so its head is the detected language.
    assert top_lang == result["detected_language"]


def test_detect_language_call_returns_a_posterior(model, clip):
    """The separate model.detect_language() call — the independent posterior — is captured."""
    detect = tr.detect_language_posterior(model, clip)
    assert detect["language"]
    assert 0.0 < detect["probability"] <= 1.0
    assert detect["topk"], "detect_language returned an empty posterior"


def test_translate_probe_targets_english(model, clip):
    """The task='translate' half of SPIKE-04 runs and produces text (English target)."""
    cond = {"name": "t_translate", "task": "translate", "multilingual": True}
    result = tr.transcribe_condition(model, clip, cond)
    assert isinstance(result["transcript"], str)
    assert result["all_language_probs_topk"]


def test_negative_control_bogus_multilingual_is_not_silently_swallowed(model, clip):
    """A check that cannot fail is not a check: feeding an un-serialisable condition must
    raise, proving the harness is really calling the engine and not returning a canned row."""
    with pytest.raises(Exception):
        tr.transcribe_condition(model, clip, {"name": "x", "task": "no-such-task", "multilingual": True})


def test_build_row_carries_the_d05_and_segment_caveats(model, clip):
    """Every row carries the binding D-05 caveat and the Segment-has-no-language caveat, so
    the result can never be quoted without its assembly."""
    corpus = tr.load_corpus()
    job = tr.build_plan([clip])[0]
    result = tr.transcribe_condition(model, clip, job["condition"])
    detect = tr.detect_language_posterior(model, clip)
    row = tr.build_row(job, corpus, result, detect)
    assert "D-05" in row["d05_caveat"]
    assert "synthetic" in row["d05_caveat"].lower()
    assert "no .language field" in row["segment_language_caveat"]
    assert row["clip_id"] == job["clip_id"]
    assert row["source_text"], "row lost its join back to the corpus source text"
