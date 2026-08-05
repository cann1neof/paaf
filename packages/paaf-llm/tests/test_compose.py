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
