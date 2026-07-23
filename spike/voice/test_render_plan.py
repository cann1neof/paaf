"""The render PLAN is checkable without a GPU — so it is checked before one is spent.

THROWAWAY (SC#5 / D-18). No torch, no chatterbox, no audio: ``render_corpus`` keeps every
engine import inside a function precisely so its job planning can be tested in the base
venv. That matters because a wrong plan is the most expensive possible failure here — a
plan that quietly renders 20 clips instead of 40, or that skips a D-02 category in the
untagged control, produces a *complete-looking* corpus whose gaps are only discoverable
after the irreplaceable unprimed listening pass has already been spent on it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import render_corpus as rc
import shuffle_blind as sb

CORPUS = rc.load_corpus()
CORPUS_IDS = [r["id"] for r in CORPUS]
JOBS = rc.build_jobs(CORPUS)


# --------------------------------------------------------------------------------------
# D-06: matrix + embedded, every sentence, twice
# --------------------------------------------------------------------------------------


def test_every_sentence_is_rendered_under_its_matrix_and_its_embedded_tag() -> None:
    for rec in CORPUS:
        tags = {j["language_id"] for j in JOBS if j["clip_id"] == rec["id"] and j["language_id"]}
        assert tags == {rec["matrix_lang"], rec["embedded_lang"]}, rec["id"]


def test_the_tagged_render_is_exactly_two_clips_per_sentence() -> None:
    tagged = [j for j in JOBS if j["condition"] != rc.CONDITION_NONE]
    assert len(tagged) == 2 * len(CORPUS) == 40


def test_no_clip_is_planned_twice() -> None:
    names = [j["filename"] for j in JOBS]
    assert len(set(names)) == len(names)


# --------------------------------------------------------------------------------------
# RESEARCH Open Q5: the untagged control
# --------------------------------------------------------------------------------------


def test_the_untagged_control_exists_and_passes_a_real_none() -> None:
    controls = [j for j in JOBS if j["condition"] == rc.CONDITION_NONE]
    assert controls, "the control condition is what separates 'the tag did nothing' from "
    assert all(j["language_id"] is None for j in controls)


def test_the_untagged_control_spans_every_failure_grid_category() -> None:
    """A control that only covers one category cannot explain a result in another."""
    controls = {j["category"] for j in JOBS if j["condition"] == rc.CONDITION_NONE}
    assert controls == {r["category"] for r in CORPUS}


def test_the_control_subset_is_derived_from_the_corpus_not_hard_coded() -> None:
    """Editing the corpus must move the control set, or coverage silently rots."""
    edited = [dict(r) for r in CORPUS]
    edited[0]["category"] = "a-brand-new-category"
    assert "a-brand-new-category" in {
        r["category"] for r in edited if r["id"] in set(rc.none_control_ids(edited))
    }


def test_the_control_ids_are_real_corpus_ids() -> None:
    assert set(rc.none_control_ids(CORPUS)) <= set(CORPUS_IDS)


# --------------------------------------------------------------------------------------
# Naming: one definition, called — never re-implemented (01-02)
# --------------------------------------------------------------------------------------


def test_every_planned_filename_comes_from_the_shared_convention() -> None:
    for job in JOBS:
        assert job["filename"] == sb.clip_filename(job["clip_id"], job["language_id"])


def test_every_planned_filename_parses_back_to_its_clip_and_tag() -> None:
    for job in JOBS:
        tag = sb.parse_clip_name(job["filename"])
        assert tag.clip_id == job["clip_id"]
        expected = sb.UNTAGGED_TAG if job["language_id"] is None else job["language_id"]
        assert tag.language_id == expected


def test_the_whole_plan_is_shufflable_by_the_blind_harness(tmp_path: Path) -> None:
    """The blind pass must be able to consume the render, controls included (D-14)."""
    src = tmp_path / "clips"
    src.mkdir()
    for job in JOBS:
        (src / job["filename"]).write_bytes(b"RIFF-fake")
    mapping = sb.shuffle_blind(src, tmp_path / "blind", seed=1, mapping_path=tmp_path / "mapping.json")
    records = sb.join_back(mapping)
    assert len(records) == len(JOBS)


# --------------------------------------------------------------------------------------
# Reproducibility and leak isolation are properties of the harness, not of good intentions
# --------------------------------------------------------------------------------------


def test_the_seed_is_fixed_and_recorded() -> None:
    assert isinstance(rc.FIXED_SEED, int)


def test_the_batch_size_is_inside_the_pattern_2_band() -> None:
    """Pitfall 5 prescribes N≈5–8 clips per fresh process on Apple Silicon."""
    assert 5 <= rc.BATCH_SIZE <= 8


def test_batching_covers_every_job_exactly_once() -> None:
    flat = [j for b in rc.batched(JOBS, rc.BATCH_SIZE) for j in b]
    assert flat == JOBS


def test_the_device_is_passed_as_a_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pitfall 4: from_pretrained does `device == "mps"`, a string comparison."""
    assert all(isinstance(d, str) for d in rc.DEVICE_ORDER)
    assert rc.DEVICE_ORDER[0] == "mps"
    assert "cpu" in rc.DEVICE_ORDER, "an unusable MPS must have somewhere to fall to (D-11/D-12)"


def test_every_generation_parameter_is_stated_explicitly() -> None:
    """A default inherited silently is a knob that is not in the record (D-07)."""
    assert set(rc.GEN_PARAMS) == {
        "exaggeration",
        "cfg_weight",
        "temperature",
        "repetition_penalty",
        "min_p",
        "top_p",
    }


def test_the_render_writes_where_the_data_survives_spike_deletion() -> None:
    """D-07: clips are declared DATA under .planning/, not throwaway code under spike/."""
    assert ".planning" in rc.CLIPS_DIR.parts
    assert "spike" not in rc.CLIPS_DIR.parts
    assert rc.TIMINGS_PATH.parent == rc.CLIPS_DIR.parent


# --------------------------------------------------------------------------------------
# Resumability — a 40-minute render that cannot resume gets restarted from zero
# --------------------------------------------------------------------------------------


def test_already_rendered_clips_are_skipped(tmp_path: Path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / JOBS[0]["filename"]).write_bytes(b"x")
    todo = rc.pending(JOBS, clips, force=False)
    assert len(todo) == len(JOBS) - 1
    assert rc.pending(JOBS, clips, force=True) == JOBS


def test_timings_rows_append_rather_than_replace(tmp_path: Path) -> None:
    path = tmp_path / "timings.jsonl"
    rc.append_rows(path, [{"a": 1}])
    rc.append_rows(path, [{"a": 2}])
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [{"a": 1}, {"a": 2}]


def test_a_device_failure_is_recorded_as_data_with_the_verbatim_exception() -> None:
    row = rc._failure_row(JOBS[:2], "mps", rc.FIXED_SEED, "RuntimeError: Placeholder storage", 0)
    assert row["ok"] is False
    assert "Placeholder storage" in row["exception_verbatim"]
    assert row["device"] == "mps"
