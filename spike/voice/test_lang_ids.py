"""Language-tag contract for Chatterbox — the tags SPIKE-01's render depends on.

D-06 renders every corpus sentence once per `language_id`. That plan is only sound if
(a) `en`/`ru`/`he`/`es` are genuinely accepted tags and (b) a typo'd tag is REJECTED
rather than silently ignored. If an unknown tag were quietly accepted, a mis-typed render
would produce plausible-sounding audio under a tag that did nothing, and SPIKE-01 would
read "the tag had no effect" as a property of the model instead of a bug in the harness.

These tests are deliberately FAST — no `slow` marker, no model download, no inference.
`generate()` validates `language_id` as its very first statement, before it touches `self`
at all, so the validation branch can be exercised by calling the *unbound* function with a
sentinel `self`. That is not a trick for its own sake: it means this contract can be
checked in CI and on a machine with no 3.2 GB of weights, which is the only way a
contract test gets run often enough to be worth having.
"""

from __future__ import annotations

import pytest

from chatterbox import SUPPORTED_LANGUAGES, ChatterboxMultilingualTTS

#: The four languages this project promises. RESEARCH says all four are present; this
#: asserts it against the installed wheel rather than against the research note.
PAAF_LANGUAGES = {"en", "ru", "he", "es"}

#: Any `self`. `generate()` validates `language_id` before dereferencing `self`, so the
#: validation path never touches this object.
SENTINEL_SELF = object()


def test_supported_languages_is_a_superset_of_the_paaf_four():
    missing = PAAF_LANGUAGES - set(SUPPORTED_LANGUAGES)
    assert not missing, (
        f"chatterbox SUPPORTED_LANGUAGES is missing {sorted(missing)} — the project's "
        "four-language promise is not implementable with this engine"
    )


@pytest.mark.parametrize("tag", sorted(PAAF_LANGUAGES))
def test_each_paaf_language_is_individually_present(tag):
    # Parametrized so a failure names the offending language instead of a set diff.
    assert tag in SUPPORTED_LANGUAGES


def test_supported_languages_maps_tags_to_readable_names():
    # The render harness and the blind-judgment join both key on the TAG. If upstream
    # ever turned this into a list of names, `"he" in SUPPORTED_LANGUAGES` would silently
    # become False and every Hebrew render would raise mid-corpus.
    assert isinstance(SUPPORTED_LANGUAGES, dict)
    assert SUPPORTED_LANGUAGES["he"] == "Hebrew"
    assert SUPPORTED_LANGUAGES["ru"] == "Russian"
    assert SUPPORTED_LANGUAGES["es"] == "Spanish"
    assert SUPPORTED_LANGUAGES["en"] == "English"


@pytest.mark.parametrize("bad_tag", ["xx", "iw", "heb", "hebrew", "EN-GB", "ru_RU"])
def test_unknown_language_id_raises_value_error(bad_tag):
    # `iw` and `heb` are the realistic typos: `iw` is Hebrew's deprecated ISO code and
    # `heb` its ISO 639-2 form. Both must be rejected, not silently treated as Hebrew.
    with pytest.raises(ValueError) as exc:
        ChatterboxMultilingualTTS.generate(SENTINEL_SELF, "probe", bad_tag)
    assert bad_tag in str(exc.value)


def test_the_value_error_names_the_supported_set():
    # A rejection that does not say what IS supported sends the reader to the source.
    with pytest.raises(ValueError) as exc:
        ChatterboxMultilingualTTS.generate(SENTINEL_SELF, "probe", "xx")
    msg = str(exc.value)
    for tag in sorted(PAAF_LANGUAGES):
        assert tag in msg


@pytest.mark.parametrize("tag", sorted(PAAF_LANGUAGES))
def test_valid_tags_pass_validation(tag):
    # Proves validation is the FIRST thing generate() does: a valid tag gets past the
    # ValueError branch and only then trips over the sentinel `self`. Without this, the
    # rejection tests above could pass for the wrong reason (e.g. if validation had moved
    # after some other guard that raised ValueError for unrelated reasons).
    with pytest.raises(AttributeError):
        ChatterboxMultilingualTTS.generate(SENTINEL_SELF, "probe", tag)


def test_language_id_none_is_accepted_as_the_untagged_control_condition():
    # RESEARCH §Code Examples: `generate()` guards with `if language_id and ...`, so None
    # skips both the language-token prepend and per-language normalization. That is
    # SPIKE-01's free third condition ("no tag at all"), and it only exists if None gets
    # past validation rather than raising.
    with pytest.raises(AttributeError):
        ChatterboxMultilingualTTS.generate(SENTINEL_SELF, "probe", None)


def test_case_insensitivity_is_upstream_behaviour_not_ours():
    # generate() lowercases before the membership test, so "HE" is accepted. Recorded as
    # a test so the render harness can rely on it — and so a future upstream change that
    # removes the .lower() is caught here rather than mid-corpus.
    with pytest.raises(AttributeError):
        ChatterboxMultilingualTTS.generate(SENTINEL_SELF, "probe", "HE")
