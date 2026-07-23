"""Grid-conformance self-check for the phase's single measuring instrument (SPIKE-01).

THROWAWAY (SC#5 / D-18) — but what it guards is not. The corpus it checks
(``.planning/phases/01-spike-gate/corpus/corpus.jsonl``) is declared **data** under
``.planning/`` and survives the deletion of ``spike/`` (D-07).

Why this file exists at all
---------------------------
D-01 makes one corpus serve SPIKE-01, 02, 04 and 08. A weak corpus therefore does not
fail loudly — it silently weakens four measurements at once, and the weakness is only
visible months later in Phase 7 when the numbers refuse to mean anything. D-02 (six
failure categories) and D-03 (every language in both matrix and embedded roles) are the
two properties that keep the grid a *grid* rather than twenty sentences someone felt like
writing. This module enforces both mechanically, which is the mitigation recorded against
threat T-01-02-INT (repudiation of measurement validity).

Written BEFORE the data (test-first): on first run it must fail because the corpus does
not yet exist. That red run is the proof the check is live.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# --------------------------------------------------------------------------------------
# Schema constants (authoritative copy lives here; spike/conftest.py mirrors it for its
# throwaway `tmp_corpus` fixture)
# --------------------------------------------------------------------------------------

#: Repo root — this file is spike/voice/test_corpus_grid.py, so up three parents.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The surviving fixture path (D-07). Deliberately NOT under spike/.
CORPUS_PATH = REPO_ROOT / ".planning" / "phases" / "01-spike-gate" / "corpus" / "corpus.jsonl"

#: The four languages the project claims (PROJECT.md) and this phase measures.
LANGUAGES = frozenset({"en", "ru", "he", "es"})

#: The six D-02 failure-grid categories, verbatim from 01-CONTEXT.md §D-02.
D02_CATEGORIES = frozenset(
    {
        "single-foreign-noun-in-english-frame",
        "mid-clause-switch",
        "hebrew-rtl-adjacent-to-latin-digits",
        "proper-nouns",
        "numbers-and-units",
        "same-script-russian-english-pair",
    }
)

#: The five-key record schema. Kept in lockstep with ``spike/conftest.py::_CORPUS_KEYS``.
CORPUS_KEYS = frozenset({"id", "text", "matrix_lang", "embedded_lang", "category"})

#: D-01 says "~20". Accept a small band so authoring is not brittle, but reject a corpus
#: that has quietly shrunk to a handful (which would still satisfy every other check).
MIN_RECORDS = 18
MAX_RECORDS = 24

_HEBREW = re.compile(r"[֐-׿]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_LATIN = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9]")

#: A Hebrew letter and an ASCII digit separated by at most three "joiner" characters
#: (space, hyphen/maqaf, geresh/gershayim, quote). This is the actual RTL-adjacency
#: stress of D-02 category 3 — a Hebrew sentence that merely *mentions* a number
#: somewhere else does not exercise the bidi boundary.
_HEBREW_DIGIT_ADJACENT = re.compile(
    r"(?:[֐-׿][\s\-־–—'\"׳״:]{0,3}[0-9])"
    r"|(?:[0-9][\s\-־–—'\"׳״:.]{0,3}[֐-׿])"
)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


def _load_records() -> list[dict[str, object]]:
    """Parse the corpus as JSONL, failing with a pointed message on each malformed line."""
    if not CORPUS_PATH.exists():
        pytest.fail(
            f"Corpus fixture missing: {CORPUS_PATH}\n"
            "This is the phase's single measuring instrument (D-01). Plan 01-02 Task 2 "
            "authors it; until then this red result is expected and correct."
        )

    raw = CORPUS_PATH.read_text(encoding="utf-8")
    records: list[dict[str, object]] = []
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue  # tolerate a trailing blank line, nothing else
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - message path
            pytest.fail(f"{CORPUS_PATH.name}:{lineno} is not valid JSON: {exc}")
        assert isinstance(obj, dict), f"{CORPUS_PATH.name}:{lineno} is not a JSON object"
        records.append(obj)
    return records


@pytest.fixture(scope="module")
def records() -> list[dict[str, object]]:
    return _load_records()


def _roles(record: dict[str, object]) -> set[str]:
    return {str(record["matrix_lang"]), str(record["embedded_lang"])}


# --------------------------------------------------------------------------------------
# Structural conformance
# --------------------------------------------------------------------------------------


def test_corpus_file_exists() -> None:
    assert CORPUS_PATH.exists(), (
        f"{CORPUS_PATH} does not exist. It must live under .planning/ (D-07) so it "
        "survives deletion of spike/, not inside the quarantine."
    )


def test_corpus_is_utf8_jsonl_with_expected_record_count(records: list[dict[str, object]]) -> None:
    assert MIN_RECORDS <= len(records) <= MAX_RECORDS, (
        f"Corpus has {len(records)} records; D-01 calls for ~20 "
        f"(accepted band {MIN_RECORDS}-{MAX_RECORDS})."
    )


def test_every_record_has_exactly_the_five_schema_keys(records: list[dict[str, object]]) -> None:
    for i, rec in enumerate(records):
        assert set(rec) == set(CORPUS_KEYS), (
            f"record {i} (id={rec.get('id')!r}) has keys {sorted(rec)}, "
            f"expected exactly {sorted(CORPUS_KEYS)}"
        )


def test_ids_are_non_empty_and_unique(records: list[dict[str, object]]) -> None:
    ids = [rec["id"] for rec in records]
    for rid in ids:
        assert isinstance(rid, str) and rid.strip(), f"id must be a non-empty string, got {rid!r}"
    duplicates = {rid for rid in ids if ids.count(rid) > 1}
    assert not duplicates, f"duplicate clip ids: {sorted(duplicates)}"


def test_text_is_non_empty(records: list[dict[str, object]]) -> None:
    for rec in records:
        text = rec["text"]
        assert isinstance(text, str) and text.strip(), f"{rec['id']}: text must be a non-empty string"


def test_language_tags_are_valid_and_the_sentence_is_actually_mixed(
    records: list[dict[str, object]],
) -> None:
    """Both tags must be known languages, and they must differ.

    A record whose matrix and embedded language are the same is not code-switched, so it
    cannot exercise anything this phase measures — and D-06 renders each sentence twice,
    once per tag, which degenerates to a duplicate render if the two tags coincide.
    """
    for rec in records:
        matrix, embedded = rec["matrix_lang"], rec["embedded_lang"]
        assert matrix in LANGUAGES, f"{rec['id']}: matrix_lang {matrix!r} not in {sorted(LANGUAGES)}"
        assert embedded in LANGUAGES, (
            f"{rec['id']}: embedded_lang {embedded!r} not in {sorted(LANGUAGES)}"
        )
        assert matrix != embedded, (
            f"{rec['id']}: matrix_lang == embedded_lang == {matrix!r}; the sentence is not mixed, "
            "so D-06's two-tag render would produce identical clips."
        )


def test_categories_are_valid(records: list[dict[str, object]]) -> None:
    for rec in records:
        assert rec["category"] in D02_CATEGORIES, (
            f"{rec['id']}: category {rec['category']!r} is not one of the six D-02 categories"
        )


# --------------------------------------------------------------------------------------
# The grid itself: D-02 coverage and D-03 matrix variation
# --------------------------------------------------------------------------------------


def test_all_six_d02_categories_are_present(records: list[dict[str, object]]) -> None:
    """D-02: the corpus is a deliberate failure grid, so no category may be missing."""
    present = {rec["category"] for rec in records}
    missing = set(D02_CATEGORIES) - present
    assert not missing, f"D-02 categories absent from the corpus: {sorted(missing)}"


@pytest.mark.parametrize("lang", sorted(LANGUAGES))
def test_every_language_appears_as_matrix(records: list[dict[str, object]], lang: str) -> None:
    """D-03, half one: each language must lead at least one sentence."""
    assert any(rec["matrix_lang"] == lang for rec in records), (
        f"D-03 violation: {lang!r} never appears as matrix_lang."
    )


@pytest.mark.parametrize("lang", sorted(LANGUAGES))
def test_every_language_appears_as_embedded(records: list[dict[str, object]], lang: str) -> None:
    """D-03, half two: each language must also be embedded inside another language's frame."""
    assert any(rec["embedded_lang"] == lang for rec in records), (
        f"D-03 violation: {lang!r} never appears as embedded_lang."
    )


# --------------------------------------------------------------------------------------
# Native script — a transliterated corpus would pass every check above while measuring
# nothing. Chatterbox routes Hebrew through add_hebrew_diacritics() and Russian through
# russian_text_stresser (01-RESEARCH §Pitfall 1); Latin transliteration bypasses both
# code paths entirely, so the spike would report on a pipeline it never ran.
# --------------------------------------------------------------------------------------


def test_hebrew_records_use_hebrew_script(records: list[dict[str, object]]) -> None:
    for rec in records:
        if "he" in _roles(rec):
            assert _HEBREW.search(str(rec["text"])), (
                f"{rec['id']} is tagged Hebrew but contains no Hebrew codepoint — "
                "transliteration is not acceptable (it bypasses add_hebrew_diacritics)."
            )


def test_russian_records_use_cyrillic_script(records: list[dict[str, object]]) -> None:
    for rec in records:
        if "ru" in _roles(rec):
            assert _CYRILLIC.search(str(rec["text"])), (
                f"{rec['id']} is tagged Russian but contains no Cyrillic codepoint — "
                "transliteration is not acceptable."
            )


def test_latin_language_records_contain_latin_script(records: list[dict[str, object]]) -> None:
    for rec in records:
        if _roles(rec) & {"en", "es"}:
            assert _LATIN.search(str(rec["text"])), (
                f"{rec['id']} is tagged en/es but contains no Latin letter."
            )


# --------------------------------------------------------------------------------------
# Per-category semantics — a record may only claim a category it actually exercises.
# --------------------------------------------------------------------------------------


def test_single_foreign_noun_records_have_an_english_frame(records: list[dict[str, object]]) -> None:
    for rec in records:
        if rec["category"] == "single-foreign-noun-in-english-frame":
            assert rec["matrix_lang"] == "en", (
                f"{rec['id']}: category says 'in-english-frame' but matrix_lang is "
                f"{rec['matrix_lang']!r}."
            )


def test_hebrew_rtl_records_put_a_digit_next_to_hebrew(records: list[dict[str, object]]) -> None:
    """The bidi boundary is the point; a stray number elsewhere in the sentence is not it."""
    for rec in records:
        if rec["category"] == "hebrew-rtl-adjacent-to-latin-digits":
            text = str(rec["text"])
            assert "he" in _roles(rec), f"{rec['id']}: Hebrew-RTL category without a Hebrew role"
            assert _HEBREW_DIGIT_ADJACENT.search(text), (
                f"{rec['id']}: no Latin digit adjacent to Hebrew script in {text!r} — "
                "the RTL/LTR boundary this category exists to stress is not present."
            )


def test_numbers_and_units_records_contain_a_digit(records: list[dict[str, object]]) -> None:
    for rec in records:
        if rec["category"] == "numbers-and-units":
            assert _DIGIT.search(str(rec["text"])), (
                f"{rec['id']}: numbers-and-units record contains no digit."
            )


def test_same_script_pair_records_are_russian_english_and_mix_both_scripts(
    records: list[dict[str, object]],
) -> None:
    """D-02's sixth category is about script *ambiguity*, not merely a ru/en mix.

    The stress is homoglyphic: Cyrillic РЕСТОРАН and Latin PECTOPAH are visually the same
    string in different scripts, so neither a tokenizer nor a language detector can tell
    them apart by shape. A record claiming this category must therefore carry both scripts
    in the same sentence.
    """
    for rec in records:
        if rec["category"] == "same-script-russian-english-pair":
            text = str(rec["text"])
            assert _roles(rec) == {"ru", "en"}, (
                f"{rec['id']}: same-script pair must be ru/en, got {sorted(_roles(rec))}"
            )
            assert _CYRILLIC.search(text) and _LATIN.search(text), (
                f"{rec['id']}: needs both Cyrillic and Latin in the same sentence to stress "
                f"script ambiguity, got {text!r}"
            )
