# SPDX-License-Identifier: Apache-2.0
"""PERS-01/02/05: the composed system prompt is base + skill fragments, nothing else.

The load-bearing property here is *negative*: PAAF must not be able to slip text
into the prompt the user did not write (PERS-05, D-10). That is asserted
structurally — the composed string, split on the join separator, must equal
exactly ``[base, *fragment_texts]`` — so any added preamble, safety wrapper, or
hidden defense turns these tests red rather than passing unnoticed.

The second property is that the ``--provenance`` audit view cannot understate
what was sent: ``"\\n\\n".join(seg.text for seg in segments(...)) == compose(...)``
byte-for-byte (D-02/D-03, one composer, no re-derivation).
"""

from __future__ import annotations

from paaf_llm.compose import PromptComposer, Segment

SEP = "\n\n"


def test_base_only() -> None:
    """With no skills enabled the prompt is EXACTLY the base — no wrapping."""
    composer = PromptComposer()
    base = "You are a terse assistant."

    assert composer.compose(base, []) == base
    assert composer.segments(base, []) == [Segment("base", base)]


def test_segments_order_follows_fragment_order() -> None:
    """Segments are base first, then skill fragments in the order given (PERS-02)."""
    composer = PromptComposer()
    base = "B"
    fragments = [("weather", "W"), ("timer", "T")]

    assert composer.segments(base, fragments) == [
        Segment("base", "B"),
        Segment("skill:weather", "W"),
        Segment("skill:timer", "T"),
    ]
    assert composer.compose(base, fragments) == "B\n\nW\n\nT"


# The realistic case the next two tests share: a persona the user wrote plus two
# enabled skills. None of these strings contains SEP, so splitting the composed
# prompt back on SEP recovers the parts exactly — that is what makes "and nothing
# else" checkable rather than merely asserted.
BASE = "You are Ada. Answer in at most two sentences."
FRAG_WEATHER = ("weather", "When asked about weather, state the temperature first.")
FRAG_TIMER = ("timer", "Confirm every timer you set by repeating its duration.")


def test_no_hidden_prompt() -> None:
    """PERS-05: the prompt is base + fragments and NOTHING the user did not write.

    This is the enforcement point for "nothing hidden from the user" (D-10). If
    anyone ever adds a framework preamble, a safety wrapper, or a prompt-injection
    defense (an explicit project anti-feature), the split below stops equalling
    ``[base, f1, f2]`` and this test goes red. Phase 4's generated handoff
    explainer must satisfy this same invariant — it has to appear verbatim in the
    inspector, not be smuggled in behind it.
    """
    composer = PromptComposer()
    fragments = [FRAG_WEATHER, FRAG_TIMER]
    f1, f2 = FRAG_WEATHER[1], FRAG_TIMER[1]

    composed = composer.compose(BASE, fragments)

    # Positive: it is exactly the concatenation, in order.
    assert composed == BASE + SEP + f1 + SEP + f2

    # Negative: taken apart again, there is no extra part hiding anywhere.
    assert composed.split(SEP) == [BASE, f1, f2]

    # The audit view rejoins to the same bytes that were sent (D-02/D-03).
    segs = composer.segments(BASE, fragments)
    assert SEP.join(s.text for s in segs) == composed


def test_provenance_labels() -> None:
    """--provenance labels the same text the raw view sends — it cannot diverge.

    The raw prompt is authoritative (D-03); provenance is an annotation of it. So
    every segment's ``text`` must be the caller's own text, unmodified, and the
    labels must attribute it correctly.
    """
    composer = PromptComposer()
    fragments = [FRAG_WEATHER, FRAG_TIMER]

    segs = composer.segments(BASE, fragments)

    assert [s.source for s in segs] == ["base", "skill:weather", "skill:timer"]
    assert [s.text for s in segs] == [BASE, FRAG_WEATHER[1], FRAG_TIMER[1]]

    # Every labeled span really is present verbatim in what gets sent.
    composed = composer.compose(BASE, fragments)
    for seg in segs:
        assert seg.text in composed
