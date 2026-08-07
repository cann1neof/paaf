# SPDX-License-Identifier: Apache-2.0
"""PERS-01/02/05: the composed prompt is base + skills + mesh, and nothing else.

The load-bearing property here is *negative*: PAAF must not be able to slip text
into the prompt the user did not write (PERS-05, D-10). That is asserted
structurally — the composed string, split on the join separator, must equal
exactly ``[base, *fragment_texts, *mesh_texts]`` — so any added preamble, safety
wrapper, or hidden defense turns these tests red rather than passing unnoticed.

**Phase 4 WIDENED that assertion; it did not replace it.** The composer gained a
third ordered input for the per-agent mesh layer (persona + handoff explainer,
D-16 layer 3 / D-17 / D-18), so the split now has to recover three groups instead
of two. :func:`test_no_hidden_prompt` keeps its Phase-3 name on purpose: deleting
or weakening it is the documented PERS-05 failure mode, and a rename would make
that deletion look like a refactor in a diff.

The second property is that the ``--provenance`` audit view cannot understate
what was sent: ``"\\n\\n".join(seg.text for seg in segments(...)) == compose(...)``
byte-for-byte (D-02/D-03, one composer, no re-derivation). Phase 4 asserts that
identity directly, over a matrix that includes every empty combination, because
the cheapest way to break it is a well-meaning branch that skips an empty mesh
layer in ``compose`` but not in ``segments``.

The third property is new and is D-17's whole point: two agents composed through
the SAME composer come out genuinely different. A per-agent prompt system that
quietly collapsed to one prompt would pass every other test in this file.
"""

from __future__ import annotations

from paaf_llm.compose import PromptComposer, Segment
from paaf_llm.profiles import ModelProfile

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

#: The Phase-4 third group: the per-agent mesh layer (D-16 layer 3). Two entries,
#: because a single one would not catch a composer that dropped all but the last.
MESH_PERSONA = ("mesh:persona", "Speak warmly, and never in bullet points.")
MESH_EXPLAINER = (
    "mesh:explainer",
    "You may hand this conversation to chef, who handles the kitchen.",
)


def test_no_hidden_prompt() -> None:
    """PERS-05: the prompt is base + fragments + mesh, and NOTHING else.

    This is the enforcement point for "nothing hidden from the user" (D-10). If
    anyone ever adds a framework preamble, a safety wrapper, or a prompt-injection
    defense (an explicit project anti-feature), the split below stops equalling
    ``[base, f1, f2, *mesh]`` and this test goes red.

    **Phase 4 widened this test rather than replacing it.** The mesh layer — the
    per-agent persona and the generated handoff explainer (MESH-04, D-18) — is
    held to exactly the same standard the skill fragments always were: it appears
    verbatim, in a known position, or it does not appear at all. An explainer
    smuggled in *behind* the composer would be precisely the hidden steering text
    this assertion exists to catch, and it would be worse than a preamble because
    it changes where the conversation goes.
    """
    composer = PromptComposer()
    fragments = [FRAG_WEATHER, FRAG_TIMER]
    mesh_fragments = [MESH_PERSONA, MESH_EXPLAINER]
    f1, f2 = FRAG_WEATHER[1], FRAG_TIMER[1]
    m1, m2 = MESH_PERSONA[1], MESH_EXPLAINER[1]

    composed = composer.compose(BASE, fragments, mesh_fragments)

    # Positive: it is exactly the concatenation, in order.
    assert composed == BASE + SEP + f1 + SEP + f2 + SEP + m1 + SEP + m2

    # Negative: taken apart again, there is no extra part hiding anywhere.
    assert composed.split(SEP) == [BASE, f1, f2, m1, m2]

    # The audit view rejoins to the same bytes that were sent (D-02/D-03).
    segs = composer.segments(BASE, fragments, mesh_fragments)
    assert SEP.join(s.text for s in segs) == composed


def test_compose_is_byte_exact_the_joined_segments() -> None:
    """``compose(...) == SEP.join(segment texts)`` for every shape of input.

    The identity is asserted DIRECTLY here, rather than only as a side effect of
    a realistic case, and over a matrix that includes each empty combination. The
    cheapest way to break the composer is a branch that treats an empty mesh
    layer specially in one method and not in the other — which is exactly why
    :meth:`PromptComposer.compose` is one branchless expression, and why the
    two-argument call has to stay byte-identical to Phase 3.
    """
    composer = PromptComposer()
    bases = ["", BASE]
    fragment_sets: list[list[tuple[str, str]]] = [[], [FRAG_WEATHER, FRAG_TIMER]]
    mesh_sets: list[list[tuple[str, str]]] = [
        [],
        [MESH_PERSONA],
        [MESH_PERSONA, MESH_EXPLAINER],
    ]

    for base in bases:
        for fragments in fragment_sets:
            for mesh_fragments in mesh_sets:
                composed = composer.compose(base, fragments, mesh_fragments)
                segs = composer.segments(base, fragments, mesh_fragments)
                assert composed == SEP.join(s.text for s in segs)
                assert composed.split(SEP) == [
                    base,
                    *(text for _name, text in fragments),
                    *(text for _source, text in mesh_fragments),
                ]

    # Phase-3 callers passed two arguments and must get the Phase-3 bytes back.
    for base in bases:
        for fragments in fragment_sets:
            assert composer.compose(base, fragments) == composer.compose(
                base, fragments, []
            )
            assert composer.segments(base, fragments) == composer.segments(
                base, fragments, []
            )


def test_per_agent_prompts_differ_through_one_composer() -> None:
    """D-17: two profiles with their own prompt and persona compose differently.

    The requirement is blunt — "two agents can have genuinely different prompts" —
    and the failure mode is just as blunt: a per-agent layer that is declared,
    stored, validated, and then never reaches the composer. Both prompts are built
    by the SAME :class:`PromptComposer` here (D-02, there is only one), so the
    difference can only come from the profiles themselves.
    """
    composer = PromptComposer()
    host = ModelProfile(
        provider="ollama",
        model="host",
        system_prompt="You are the host. Greet, then delegate.",
        persona="Warm, unhurried, never technical.",
    )
    chef = ModelProfile(
        provider="ollama",
        model="chef",
        system_prompt="You are the cook. Answer in weights and minutes.",
        persona="Blunt. No pleasantries.",
    )

    # `system_prompt` is the agent's own base; `persona` rides in the mesh layer.
    host_prompt = composer.compose(
        host.system_prompt or "", [], [("mesh:persona", host.persona or "")]
    )
    chef_prompt = composer.compose(
        chef.system_prompt or "", [], [("mesh:persona", chef.persona or "")]
    )

    assert host_prompt != chef_prompt
    assert host.system_prompt in host_prompt
    assert host.persona in host_prompt
    assert chef.system_prompt in chef_prompt
    assert chef.persona in chef_prompt
    # Neither agent can see the other's layer — that is what "genuinely" means.
    assert chef.system_prompt not in host_prompt
    assert chef.persona not in host_prompt


def test_a_profile_declaring_no_prompt_layer_leaves_both_fields_none() -> None:
    """The per-agent layer is ADDITIVE: absent means "use the shared base" (A4).

    ``LlmConfig.base_prompt`` stays meaningful as the shared base. A profile that
    says nothing gets ``None`` rather than ``""`` so the two cases stay
    distinguishable — a user who deliberately wrote an empty per-agent prompt is
    not the same as a user who wrote none, and only ``None`` may fall back.
    """
    plain = ModelProfile(provider="ollama", model="m")

    assert plain.system_prompt is None
    assert plain.persona is None
    assert plain.handoff_explainer is None

    declared = ModelProfile(
        provider="ollama", model="m", system_prompt="you are the cook"
    )
    assert declared.system_prompt == "you are the cook"


def test_provenance_labels() -> None:
    """--provenance labels the same text the raw view sends — it cannot diverge.

    The raw prompt is authoritative (D-03); provenance is an annotation of it. So
    every segment's ``text`` must be the caller's own text, unmodified, and the
    labels must attribute it correctly.

    The mesh sources carry the label the CALLER chose, not one this module
    invents. ``mesh.py`` owns those spellings (``mesh:persona``,
    ``mesh:explainer``, ``mesh:tool:<name>``) because it owns the layer; the
    composer's job is to pass them through unchanged, which is what keeps a new
    mesh source from needing a change here at all.
    """
    composer = PromptComposer()
    fragments = [FRAG_WEATHER, FRAG_TIMER]
    mesh_fragments = [MESH_PERSONA, MESH_EXPLAINER]

    segs = composer.segments(BASE, fragments, mesh_fragments)

    assert [s.source for s in segs] == [
        "base",
        "skill:weather",
        "skill:timer",
        "mesh:persona",
        "mesh:explainer",
    ]
    assert [s.text for s in segs] == [
        BASE,
        FRAG_WEATHER[1],
        FRAG_TIMER[1],
        MESH_PERSONA[1],
        MESH_EXPLAINER[1],
    ]

    # Every labeled span really is present verbatim in what gets sent.
    composed = composer.compose(BASE, fragments, mesh_fragments)
    for seg in segs:
        assert seg.text in composed
