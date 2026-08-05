# SPDX-License-Identifier: Apache-2.0
"""PERS-01/02/05: the one composer that builds the system prompt actually sent.

There is exactly ONE code path that turns the user's base system prompt (PERS-01)
plus their enabled skills' persona fragments (PERS-02) into the string handed to
the model. The live engine path calls :meth:`PromptComposer.compose`; so do
``paaf prompt`` and ``paaf chat --show-prompt`` (D-02). No caller re-derives the
prompt — a second derivation is a byte-drift risk that would silently make the
inspector lie about what was sent.

**The PERS-05 invariant this module exists to make mechanical (D-10):** the
composed string contains the base prompt and the skill fragments and *nothing
else*. PAAF adds no preamble, no trailing instruction, no safety wrapper, and no
hidden prompt-injection defense (the project's anti-feature list forbids exactly
that). "Nothing hidden from the user" is therefore a property of this function,
not a promise in a README — and ``tests/test_compose.py`` asserts it by splitting
the output back apart and demanding it equal ``[base, *fragments]``.

:meth:`PromptComposer.segments` returns the same text carrying provenance labels
for the opt-in ``--provenance`` view (D-03). Joining those segment texts with the
separator reproduces :meth:`compose` byte-for-byte, so the audit view can never
understate what crossed to the model.

Scope note: no runtime context is composed here — PERS-03 is deferred to Phase 10.
This phase's fragments come from a stub skill source (D-09); real skills land in
Phase 6 and plug into this same signature. Phase 4's generated handoff explainer
must also appear here verbatim — this composer is the PERS-05 enforcement point
across both phases.

The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the prompt the user audits cannot depend on anything swappable.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The separator between the base prompt and each skill fragment. It is part of
#: the byte-exact contract: ``compose`` joins with it and the provenance view
#: rejoins with it, so the two views cannot diverge.
SEGMENT_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class Segment:
    """One labeled span of the composed prompt.

    ``source`` is ``"base"`` for the user's base system prompt and
    ``f"skill:{name}"`` for a persona fragment contributed by an enabled skill.
    ``text`` is the fragment's text *as sent* — never a summary or a rewrite, so
    the ``--provenance`` view shows the same bytes the raw view does.
    """

    source: str
    text: str


class PromptComposer:
    """Composes the system prompt from a base prompt and ordered skill fragments.

    Pure and deterministic: same inputs, same bytes out, no I/O and no state.
    """

    def segments(
        self, base_prompt: str, fragments: list[tuple[str, str]]
    ) -> list[Segment]:
        """Return the prompt's labeled parts: base first, then fragments in order.

        ``fragments`` is an ordered list of ``(skill_name, fragment_text)`` pairs
        (PERS-02). Order is the user's — it is preserved exactly, because the
        order skills appear in the prompt is part of what the user controls.
        """
        segs = [Segment("base", base_prompt)]
        segs += [Segment(f"skill:{name}", text) for name, text in fragments]
        return segs

    def compose(self, base_prompt: str, fragments: list[tuple[str, str]]) -> str:
        """Return THE byte-exact system prompt to send — base + fragments only.

        This is the single authoritative string. Whatever this returns is what the
        model receives and what the prompt inspector prints; there is no other
        derivation (D-02). Nothing is appended, prepended, or interpolated beyond
        the caller's own text (PERS-05, D-10).
        """
        segs = self.segments(base_prompt, fragments)
        return SEGMENT_SEPARATOR.join(s.text for s in segs)
