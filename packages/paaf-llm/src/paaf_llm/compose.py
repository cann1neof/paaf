# SPDX-License-Identifier: Apache-2.0
"""PERS-01/02/05: the one composer that builds the system prompt actually sent.

There is exactly ONE code path that turns the user's base system prompt (PERS-01)
plus their enabled skills' persona fragments (PERS-02) into the string handed to
the model. The live engine path calls :meth:`PromptComposer.compose`; so do
``paaf prompt`` and ``paaf chat --show-prompt`` (D-02). No caller re-derives the
prompt — a second derivation is a byte-drift risk that would silently make the
inspector lie about what was sent.

**The PERS-05 invariant this module exists to make mechanical (D-10):** the
composed string contains the base prompt, the skill fragments, and the per-agent
mesh layer, and *nothing else*. PAAF adds no preamble, no trailing instruction,
no safety wrapper, and no hidden prompt-injection defense (the project's
anti-feature list forbids exactly that). "Nothing hidden from the user" is
therefore a property of this function, not a promise in a README — and
``tests/test_compose.py`` asserts it by splitting the output back apart and
demanding it equal ``[base, *fragments, *mesh_fragments]``.

:meth:`PromptComposer.segments` returns the same text carrying provenance labels
for the opt-in ``--provenance`` view (D-03). Joining those segment texts with the
separator reproduces :meth:`compose` byte-for-byte, so the audit view can never
understate what crossed to the model.

**Phase 4's mesh layer (D-16 layer 3, D-17, D-18) is the third ordered input,
and it needed no philosophical change here.** ``compose`` always took the base
prompt as an *argument* rather than reading a config, so per-agent composition
was already expressible; all that was missing was somewhere to put an agent's own
persona and its generated handoff explainer. Those arrive as
``(source, text)`` pairs whose labels — ``mesh:persona`` and ``mesh:explainer``
— are chosen by :mod:`paaf_llm.mesh`, not invented here. This module stays
ignorant of what a mesh is, which is why a future mesh source costs it nothing.

The Phase-3 promise that "Phase 4's generated handoff explainer must also appear
here verbatim" is now kept: it is a segment like any other, held to the same
split-and-compare invariant, and the prompt inspector renders it under its own
label. This composer is the PERS-05 enforcement point across both phases.

Scope note: no runtime context is composed here — PERS-03 is deferred to Phase 10.
This phase's fragments come from a stub skill source (D-09); real skills land in
Phase 6 and plug into this same signature.

**One thing this composer deliberately does NOT cover, and it matters.** A tool's
name and description are also sent to the model and also steer it, and they are
not prompt text — so they cannot be segments here. Rendering them is
``paaf prompt --provenance``'s job, from :func:`paaf_llm.mesh.handoff_tools`
(RESEARCH Finding 1). An inspector that showed only this module's output would
satisfy PERS-05 for the prompt and quietly miss the tool surface.

The module is stdlib-only by design: it imports no agent framework and no other
PAAF package, so the prompt the user audits cannot depend on anything swappable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The separator between the base prompt and each skill fragment. It is part of
#: the byte-exact contract: ``compose`` joins with it and the provenance view
#: rejoins with it, so the two views cannot diverge.
SEGMENT_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class Segment:
    """One labeled span of the composed prompt.

    ``source`` is one of:

    * ``"base"`` — the base prompt this agent was composed against, which is the
      profile's own ``system_prompt`` when it declared one and the shared
      ``LlmConfig.base_prompt`` otherwise (D-17).
    * ``f"skill:{name}"`` — a persona fragment contributed by an enabled skill.
    * ``paaf_llm.mesh.MESH_PERSONA_SOURCE`` (``"mesh:persona"``) — how this
      specific agent talks to the user (D-16 layer 3).
    * ``paaf_llm.mesh.MESH_EXPLAINER_SOURCE`` (``"mesh:explainer"``) — the
      handoff explainer generated from this agent's peers and their manifests,
      or the user's own override of it (MESH-04, D-18).

    The mesh spellings live in :mod:`paaf_llm.mesh` rather than here, and this
    module never compares against them: a source is whatever the caller labelled
    it. That is what keeps the composer from acquiring an opinion about the mesh.

    A fourth label, ``paaf_llm.mesh.MESH_TOOL_SOURCE_PREFIX``
    (``"mesh:tool:<name>"``), is used by the prompt inspector for the bound tool
    surface. It is deliberately NOT a ``Segment``: a tool description is steering
    text that reaches the model *beside* the system prompt, never inside it, and
    inventing a segment for it would make ``compose`` claim to have sent bytes it
    did not send.

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
        self,
        base_prompt: str,
        fragments: list[tuple[str, str]],
        mesh_fragments: Sequence[tuple[str, str]] = (),
    ) -> list[Segment]:
        """Return the labeled parts: base, then skills, then the mesh layer.

        ``fragments`` is an ordered list of ``(skill_name, fragment_text)`` pairs
        (PERS-02). Order is the user's — it is preserved exactly, because the
        order skills appear in the prompt is part of what the user controls.

        ``mesh_fragments`` is an ordered list of ``(source, text)`` pairs for the
        per-agent layer (D-16 layer 3). Unlike ``fragments`` these carry their
        FULL source label rather than a name to be prefixed, because
        :mod:`paaf_llm.mesh` owns those spellings and adding one there must not
        require a change here.

        It comes last, and the position is a decision rather than an accident:
        the explainer describes the moves available to *this* agent, so it reads
        as the closing paragraph of a persona the earlier layers established. It
        is also the layer PAAF generates, so putting it last keeps everything the
        user hand-wrote above everything PAAF assembled — which is the order a
        reader of ``--provenance`` is looking for.
        """
        segs = [Segment("base", base_prompt)]
        segs += [Segment(f"skill:{name}", text) for name, text in fragments]
        segs += [Segment(source, text) for source, text in mesh_fragments]
        return segs

    def compose(
        self,
        base_prompt: str,
        fragments: list[tuple[str, str]],
        mesh_fragments: Sequence[tuple[str, str]] = (),
    ) -> str:
        """Return THE byte-exact system prompt: base, skills, mesh, nothing more.

        This is the single authoritative string. Whatever comes out of here is
        what the model receives and what the prompt inspector prints; there is no
        other derivation (D-02). Nothing is appended, prepended, or interpolated
        beyond the caller's own text (PERS-05, D-10).

        **One branchless expression, deliberately.** A branch here — even an
        innocuous-looking one skipping an empty mesh layer — would let the
        composed bytes and the labeled segments drift apart, and the
        ``--provenance`` view could then understate what crossed to the model.
        ``tests/test_compose.py`` splits the output back apart and demands it
        equal ``[base, *fragments, *mesh_fragments]``; Phase 4 WIDENED that
        assertion to cover the mesh layer, and weakening or deleting it is the
        PERS-05 failure mode this method exists to prevent.

        Omitting the third argument reproduces Phase 3 byte for byte, so every
        caller written before the mesh existed still gets the prompt it did then.
        """
        return SEGMENT_SEPARATOR.join(
            s.text for s in self.segments(base_prompt, fragments, mesh_fragments)
        )
