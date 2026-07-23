"""Reversibility check for the D-14 blind-shuffle harness (SPIKE-02).

THROWAWAY (SC#5 / D-18). No model inference, no real WAVs — the clips here are a few
bytes of synthetic content each. 01-05 owns the real render; this file proves the
bookkeeping is sound *before* there is anything expensive to lose.

The property under test is narrow and total: for a fixed seed, the shuffle is a bijection
from tagged clips to opaque names, and ``join_back`` inverts it exactly — every clip id
recovers its ``language_id``, with no collisions and no drops. If that fails, the SPIKE-02
listening pass produces verbatim impressions attached to the wrong tags, which is worse
than no impressions at all: it looks like data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import shuffle_blind as sb

SEED = 20260723

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = REPO_ROOT / ".planning" / "phases" / "01-spike-gate" / "corpus" / "corpus.jsonl"


# --------------------------------------------------------------------------------------
# Synthetic clip fixtures
# --------------------------------------------------------------------------------------


def _make_clips(directory: Path, tags: list[sb.ClipTag]) -> dict[sb.ClipTag, bytes]:
    """Write one tiny file per tag; content encodes the tag so copies can be traced."""
    directory.mkdir(parents=True, exist_ok=True)
    contents: dict[sb.ClipTag, bytes] = {}
    for tag in tags:
        payload = f"RIFF-fake:{tag.clip_id}:{tag.language_id}".encode()
        (directory / sb.clip_filename(tag.clip_id, tag.language_id)).write_bytes(payload)
        contents[tag] = payload
    return contents


def _corpus_tags() -> list[sb.ClipTag]:
    """The real D-06 clip set: each corpus sentence tagged matrix, then embedded (~40)."""
    tags: list[sb.ClipTag] = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        tags.append(sb.ClipTag(rec["id"], rec["matrix_lang"]))
        tags.append(sb.ClipTag(rec["id"], rec["embedded_lang"]))
    return tags


@pytest.fixture
def clip_set(tmp_path: Path) -> tuple[Path, dict[sb.ClipTag, bytes]]:
    """40 synthetic clips: 20 sentence ids, each tagged twice (D-06)."""
    tags = [
        sb.ClipTag(f"c{i:02d}", lang)
        for i in range(1, 21)
        for lang in (["en", "ru", "he", "es"][i % 4], ["ru", "he", "es", "en"][i % 4])
    ]
    src = tmp_path / "clips"
    return src, _make_clips(src, tags)


# --------------------------------------------------------------------------------------
# Name convention
# --------------------------------------------------------------------------------------


def test_clip_filename_and_parse_are_inverses() -> None:
    for clip_id in ("c01", "c20", "edge_case"):
        for lang in sorted(sb.LANGUAGES):
            name = sb.clip_filename(clip_id, lang)
            assert sb.parse_clip_name(name) == sb.ClipTag(clip_id, lang)


def test_clip_filename_rejects_a_separator_in_the_clip_id() -> None:
    with pytest.raises(ValueError, match="separator"):
        sb.clip_filename("c__01", "he")


def test_clip_filename_rejects_an_unknown_language() -> None:
    with pytest.raises(ValueError, match="not one of"):
        sb.clip_filename("c01", "iw")  # the deprecated ISO code for Hebrew


@pytest.mark.parametrize("bad", ["c01.wav", "justtext.wav", "__he.wav"])
def test_parse_clip_name_rejects_malformed_names(bad: str) -> None:
    with pytest.raises(ValueError):
        sb.parse_clip_name(bad)


def test_parse_clip_name_rejects_an_unknown_tag() -> None:
    """A typo'd tag must not be judged as if it were real."""
    with pytest.raises(ValueError, match="typo"):
        sb.parse_clip_name("c01__xx.wav")


# --------------------------------------------------------------------------------------
# The untagged control condition (RESEARCH Open Q5) — 01-05 renders it, so the shared
# naming convention has to carry it or the renderer would have to re-implement the
# convention, which is the one thing clip_filename() exists to prevent.
# --------------------------------------------------------------------------------------


def test_none_language_id_names_the_untagged_control() -> None:
    assert sb.clip_filename("c08", None) == f"c08__{sb.UNTAGGED_TAG}.wav"


def test_the_untagged_tag_round_trips_like_any_language() -> None:
    name = sb.clip_filename("c08", None)
    assert sb.parse_clip_name(name) == sb.ClipTag("c08", sb.UNTAGGED_TAG)


def test_passing_the_untagged_tag_as_a_string_is_equivalent_to_none() -> None:
    """A renderer that has already stringified its condition must not have to convert back."""
    assert sb.clip_filename("c08", sb.UNTAGGED_TAG) == sb.clip_filename("c08", None)


def test_untagged_is_a_condition_not_a_language() -> None:
    """`LANGUAGES` must stay the set of languages: downstream code counts languages with it."""
    assert sb.UNTAGGED_TAG not in sb.LANGUAGES
    assert sb.JUDGABLE_TAGS == sb.LANGUAGES | {sb.UNTAGGED_TAG}


def test_widening_the_tag_set_did_not_widen_it_to_typos() -> None:
    """The guard's whole purpose survives: 'none' is admitted, 'nonw' still is not."""
    for bad in ("nonw", "non", "null", "xx", "iw"):
        with pytest.raises(ValueError, match="not one of|typo"):
            sb.clip_filename("c01", bad)
        with pytest.raises(ValueError, match="not one of|typo"):
            sb.parse_clip_name(f"c01__{bad}.wav")


def test_untagged_clips_shuffle_and_join_back_alongside_tagged_ones(tmp_path: Path) -> None:
    """The blind pass must judge the control clips too, or the control is not blind."""
    tags = [
        sb.ClipTag("c08", "he"),
        sb.ClipTag("c08", "en"),
        sb.ClipTag("c08", sb.UNTAGGED_TAG),
        sb.ClipTag("c01", "en"),
        sb.ClipTag("c01", "ru"),
        sb.ClipTag("c01", sb.UNTAGGED_TAG),
    ]
    src = tmp_path / "clips"
    contents = _make_clips(src, tags)
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)

    records = sb.join_back(mapping_path)
    assert {sb.ClipTag(r["clip_id"], r["language_id"]) for r in records} == set(contents)
    # No blind name may leak the condition it is hiding.
    for name in (tmp_path / "clips_blind").iterdir():
        assert sb.UNTAGGED_TAG not in name.stem


# --------------------------------------------------------------------------------------
# The core property: bijection + exact inversion
# --------------------------------------------------------------------------------------


def test_round_trip_restores_every_clip_id_and_language_id(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, contents = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)

    records = sb.join_back(mapping_path)

    recovered = [sb.ClipTag(r["clip_id"], r["language_id"]) for r in records]
    assert len(recovered) == len(contents), "clip dropped or duplicated by the shuffle"
    assert set(recovered) == set(contents), "join_back did not restore the original tag set"
    assert len(set(recovered)) == len(recovered), "join_back produced a duplicate tag"


def test_blind_names_are_unique_and_cover_every_clip(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, contents = clip_set
    blind = tmp_path / "clips_blind"
    mapping_path = sb.shuffle_blind(src, blind, seed=SEED)

    data = sb.load_mapping(mapping_path)
    blind_names = list(data["clips"])
    on_disk = sorted(p.name for p in blind.iterdir())

    assert len(blind_names) == len(contents)
    assert len(set(blind_names)) == len(blind_names), "blind name collision"
    assert on_disk == sorted(blind_names), "mapping and blind directory disagree"
    assert data["seed"] == SEED
    assert data["count"] == len(contents)


def test_blind_copies_carry_the_original_bytes(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    """The mapping is only trustworthy if the file it names is the file that was judged."""
    src, contents = clip_set
    blind = tmp_path / "clips_blind"
    mapping_path = sb.shuffle_blind(src, blind, seed=SEED)

    for record in sb.join_back(mapping_path):
        tag = sb.ClipTag(record["clip_id"], record["language_id"])
        assert (blind / record["blind_name"]).read_bytes() == contents[tag]


def test_source_clips_are_copied_not_moved(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    """The tagged render is committed evidence (D-07); the shuffle must not consume it."""
    src, contents = clip_set
    sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    assert len(list(src.iterdir())) == len(contents)


# --------------------------------------------------------------------------------------
# Blindness
# --------------------------------------------------------------------------------------


def test_blind_names_leak_neither_clip_id_nor_language_tag(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, contents = clip_set
    blind = tmp_path / "clips_blind"
    sb.shuffle_blind(src, blind, seed=SEED)

    for name in (p.name for p in blind.iterdir()):
        stem = Path(name).stem
        assert stem.startswith("blind_")
        assert not any(tag.clip_id in stem for tag in contents)
        assert not any(stem.endswith(f"_{lang}") for lang in sb.LANGUAGES)


def test_shuffle_actually_permutes(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    """A no-op 'shuffle' would pass every reversibility check while blinding nothing."""
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    data = sb.load_mapping(mapping_path)

    sorted_sources = sorted(p.name for p in src.iterdir())
    shuffled_sources = [info["source_name"] for info in data["clips"].values()]
    assert shuffled_sources != sorted_sources, "the blind order equals the sorted order"


def test_mapping_may_not_be_written_inside_the_blind_directory(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    blind = tmp_path / "clips_blind"
    with pytest.raises(ValueError, match="D-14"):
        sb.shuffle_blind(src, blind, seed=SEED, mapping_path=blind / "mapping.json")


# --------------------------------------------------------------------------------------
# Determinism (01-RESEARCH: the shuffle needs a fixed, recorded seed)
# --------------------------------------------------------------------------------------


def test_same_seed_produces_the_same_mapping(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    first = sb.load_mapping(sb.shuffle_blind(src, tmp_path / "a", seed=SEED, mapping_path=tmp_path / "a.json"))
    second = sb.load_mapping(sb.shuffle_blind(src, tmp_path / "b", seed=SEED, mapping_path=tmp_path / "b.json"))
    assert first["clips"] == second["clips"]


def test_a_different_seed_produces_a_different_mapping(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    base = sb.load_mapping(
        sb.shuffle_blind(src, tmp_path / "base", seed=SEED, mapping_path=tmp_path / "base.json")
    )["clips"]
    others = []
    for i, other_seed in enumerate((1, 2, 3, 4, 5)):
        others.append(
            sb.load_mapping(
                sb.shuffle_blind(
                    src,
                    tmp_path / f"s{i}",
                    seed=other_seed,
                    mapping_path=tmp_path / f"s{i}.json",
                )
            )["clips"]
        )
    assert any(o != base for o in others), "seed has no effect on the shuffle"


# --------------------------------------------------------------------------------------
# Guards against a silently invalid listening pass
# --------------------------------------------------------------------------------------


def test_duplicate_tags_in_the_source_are_rejected(tmp_path: Path) -> None:
    src = tmp_path / "clips"
    _make_clips(src, [sb.ClipTag("c01", "he")])
    (src / "c01__he.flac").write_bytes(b"second render of the same tag")
    with pytest.raises(ValueError, match="Duplicate"):
        sb.shuffle_blind(src, tmp_path / "blind", seed=SEED, pattern="*")


def test_empty_source_directory_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "clips"
    src.mkdir()
    with pytest.raises(ValueError, match="nothing to shuffle"):
        sb.shuffle_blind(src, tmp_path / "blind", seed=SEED)


def test_non_empty_blind_directory_requires_overwrite(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    blind = tmp_path / "clips_blind"
    sb.shuffle_blind(src, blind, seed=SEED)
    with pytest.raises(FileExistsError):
        sb.shuffle_blind(src, blind, seed=SEED + 1)
    sb.shuffle_blind(src, blind, seed=SEED + 1, overwrite=True)  # explicit is fine


def test_load_mapping_rejects_a_hand_edited_truncated_mapping(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    dropped = next(iter(data["clips"]))
    del data["clips"][dropped]
    mapping_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="truncated"):
        sb.load_mapping(mapping_path)


def test_load_mapping_rejects_two_blind_names_for_one_clip(tmp_path: Path) -> None:
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(
        json.dumps(
            {
                "clips": {
                    "blind_000.wav": {"clip_id": "c01", "language_id": "he", "source_name": "a"},
                    "blind_001.wav": {"clip_id": "c01", "language_id": "he", "source_name": "b"},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="same clip"):
        sb.load_mapping(mapping_path)


# --------------------------------------------------------------------------------------
# Judgments (D-13 verbatim impressions)
# --------------------------------------------------------------------------------------


def test_judgment_template_is_blind_and_covers_every_clip(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, contents = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    out = sb.judgment_template(mapping_path, tmp_path / "judgments.json")

    template = json.loads(out.read_text(encoding="utf-8"))
    assert len(template) == len(contents)
    assert set(template) == set(sb.load_mapping(mapping_path)["clips"])
    assert all(v == "" for v in template.values())
    text = out.read_text(encoding="utf-8")
    assert not any(f'"{tag.clip_id}' in text for tag in contents), "template leaks clip ids"


def test_join_back_attaches_verbatim_judgments(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    blind_names = sorted(sb.load_mapping(mapping_path)["clips"])
    notes = {name: f"impression of {name}" for name in blind_names}

    records = sb.join_back(mapping_path, notes)
    assert all(r["judgment"] == f"impression of {r['blind_name']}" for r in records)


def test_join_back_reads_judgments_from_a_file(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    template = sb.judgment_template(mapping_path, tmp_path / "judgments.json")
    filled = {name: "כמעט מובן" for name in json.loads(template.read_text(encoding="utf-8"))}
    template.write_text(json.dumps(filled, ensure_ascii=False), encoding="utf-8")

    records = sb.join_back(mapping_path, template, require_complete=True)
    assert all(r["judgment"] == "כמעט מובן" for r in records)


def test_join_back_rejects_judgments_from_a_different_shuffle(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    with pytest.raises(ValueError, match="different shuffles"):
        sb.join_back(mapping_path, {"blind_999.wav": "stale note"})


def test_require_complete_flags_an_unjudged_clip(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    names = sorted(sb.load_mapping(mapping_path)["clips"])
    notes = {name: "fine" for name in names[:-1]}
    with pytest.raises(ValueError, match="No judgment recorded"):
        sb.join_back(mapping_path, notes, require_complete=True)


def test_records_pair_matrix_and_embedded_renders_of_the_same_sentence(
    clip_set: tuple[Path, dict[sb.ClipTag, bytes]], tmp_path: Path
) -> None:
    """D-06 renders each sentence twice; the join must put the pair side by side."""
    src, _ = clip_set
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)
    records = sb.join_back(mapping_path)
    clip_ids = [r["clip_id"] for r in records]
    assert clip_ids == sorted(clip_ids)
    for i in range(0, len(records), 2):
        assert records[i]["clip_id"] == records[i + 1]["clip_id"]
        assert records[i]["language_id"] != records[i + 1]["language_id"]


# --------------------------------------------------------------------------------------
# Against the real corpus (still no audio — filenames only)
# --------------------------------------------------------------------------------------


def test_round_trip_over_the_real_corpus_clip_set(tmp_path: Path) -> None:
    """~40 clips derived from the committed corpus, tagged matrix + embedded per D-06."""
    tags = _corpus_tags()
    assert len(tags) == 2 * len(set(t.clip_id for t in tags))

    src = tmp_path / "clips"
    contents = _make_clips(src, tags)
    mapping_path = sb.shuffle_blind(src, tmp_path / "clips_blind", seed=SEED)

    records = sb.join_back(mapping_path)
    assert {sb.ClipTag(r["clip_id"], r["language_id"]) for r in records} == set(contents)
    assert len(records) == len(tags)
