# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the paaf-llm suite: the programmable fake and a trace store.

Every fixture here is deliberately framework-free. The whole point of the fake
adapter (SC#1) is that this suite proves the library correct with the agent
framework UNINSTALLED, so a fixture that reached for a real provider — or for a
real network — would quietly dissolve the guarantee the suite exists to make.

**Profile naming convention (load-bearing, read this before writing a test).**
:class:`~paaf_llm.profiles.ModelProfile` carries no ``name`` field: a profile's
name is the key it sits under in ``LlmConfig.profiles``, so the name does not
travel with the profile object across the ``ChatAdapter`` port. The fake
therefore keys its programs by ``profile.model`` (see
:mod:`paaf_llm.fake`), and :func:`make_profile` sets ``model`` to the profile's
name so that ``fake_adapter.program("local", ...)`` drives the profile
``make_profile("local")`` produces.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

import pytest
from paaf_llm.fake import FakeAdapter
from paaf_llm.mesh import OBSERVER_PROFILE_NAME
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_trace.store import TraceStore


@pytest.fixture
def fake_adapter() -> FakeAdapter:
    """A fresh, unprogrammed :class:`FakeAdapter` per test.

    Fresh per test on purpose: a shared adapter would carry one test's scripted
    program into the next, and a fallback test that passes because of a stale
    program is worse than no test at all.
    """
    return FakeAdapter()


@pytest.fixture
def make_profile() -> Callable[..., ModelProfile]:
    """Build a minimal valid :class:`ModelProfile` named ``name``.

    ``model`` is set to ``name`` (see the module docstring) so the profile is
    addressable through :meth:`FakeAdapter.program`. Any field can be overridden
    — ``make_profile("slow", first_token_budget_s=0.01)`` is the usual shape for
    a slow-first-token test.
    """

    def _make(name: str, **overrides: Any) -> ModelProfile:
        fields: dict[str, Any] = {"provider": "ollama", "model": name}
        fields.update(overrides)
        return ModelProfile(**fields)

    return _make


@pytest.fixture
def make_llm_config(
    make_profile: Callable[..., ModelProfile],
) -> Callable[..., LlmConfig]:
    """Build a minimal :class:`LlmConfig` with an active profile and a chain.

    Every name in ``fallbacks`` is declared as a profile too, because
    ``LlmConfig`` rejects a chain entry that names no declared profile — the
    fixture cannot hand back a config the schema would refuse.
    """

    def _make(
        active: str = "local",
        fallbacks: Sequence[str] = (),
        base_prompt: str = "",
    ) -> LlmConfig:
        names = [active, *fallbacks]
        return LlmConfig(
            base_prompt=base_prompt,
            active_profile=active,
            profiles={name: make_profile(name) for name in names},
            fallback_chain=list(fallbacks),
        )

    return _make


@pytest.fixture
def make_mesh_config(
    make_profile: Callable[..., ModelProfile],
) -> Callable[..., LlmConfig]:
    """Build an :class:`LlmConfig` whose profiles carry a declared peer graph.

    ``peers`` is the graph itself — ``{"host": ["chef"], "chef": []}`` reads as
    "host may hand off to chef; chef may hand off to nobody". Every key AND every
    named peer is declared as a profile, for the same reason
    :func:`make_llm_config` declares every fallback entry: ``LlmConfig`` rejects a
    peer that names no declared profile, so the fixture cannot hand back a config
    the schema would refuse.

    Declaring a profile that is in NO peer list is deliberately possible — pass it
    as a key with an empty list. That is the shape MESH-02's guard test needs: a
    profile that exists in ``LlmConfig.profiles`` and is still not reachable from
    the awake agent. A guard written against ``profiles`` instead of
    ``awake.peers`` passes every other test and fails that one (Pitfall 4).

    ``capabilities`` maps a profile name to its free-text manifest (D-08), which
    is what the generated handoff tool descriptions are built from.

    ``hop_budget`` and ``default_agent`` are the two mesh-level knobs (D-08/D-09).
    They are passed straight through rather than defaulted here, so a budget test
    reads the value it is testing in its own body and the schema's own default
    (and its floor) stay the single source of truth.

    ``keep_pre_handoff_prose`` is D-11's user setting, passed straight through
    for the same reason ``hop_budget`` is: the schema's own default stays the
    single source of truth, so a test that cares about the default reads it from
    the model rather than from this fixture.

    ``system_prompts``, ``personas`` and ``explainers`` are the per-agent prompt
    layer (D-16 layer 3 / D-17 / D-18), keyed by profile name exactly as
    ``capabilities`` is. A name absent from a mapping declares nothing and gets
    ``None``, which is the case that falls back to the shared base — so a test
    can express "this agent has its own prompt and that one does not" without
    hand-building an :class:`LlmConfig`. ``explainer_template`` is the global
    override that a per-agent ``explainers`` entry outranks.

    ``observer=True`` declares a profile under the reserved name (D-03), and it
    is OPT-IN here rather than on by default so that every existing mesh test
    keeps taking the unobserved path byte for byte — "with no observer declared
    the mesh behaves exactly as it did before" is a claim this fixture must not
    quietly make untrue. ``observer_grants`` / ``observer_window_messages`` /
    ``observer_window_handoffs`` pass straight through for the same reason
    ``hop_budget`` does: the schema's own defaults stay the single source of
    truth, so a test that cares about a default reads it off the model.

    The observer profile is deliberately given NO peers and is listed in nobody
    else's ``peers`` — ``LlmConfig`` would refuse it, which is the point of the
    reservation (T-04-36).
    """

    def _make(
        active: str = "host",
        peers: Mapping[str, Sequence[str]] | None = None,
        base_prompt: str = "",
        capabilities: Mapping[str, str] | None = None,
        hop_budget: int | None = None,
        default_agent: str | None = None,
        keep_pre_handoff_prose: bool | None = None,
        system_prompts: Mapping[str, str] | None = None,
        personas: Mapping[str, str] | None = None,
        explainers: Mapping[str, str] | None = None,
        explainer_template: str | None = None,
        observer: bool = False,
        observer_grants: Sequence[str] | None = None,
        observer_window_messages: int | None = None,
        observer_window_handoffs: int | None = None,
    ) -> LlmConfig:
        graph = dict(peers or {})
        manifests = dict(capabilities or {})
        prompts = dict(system_prompts or {})
        voices = dict(personas or {})
        overrides = dict(explainers or {})

        # dict.fromkeys preserves declaration order while de-duplicating, so the
        # profiles dict reads in the order the test wrote the graph.
        names = dict.fromkeys(
            [
                active,
                *graph,
                *(peer for edges in graph.values() for peer in edges),
                *([default_agent] if default_agent else []),
                *([OBSERVER_PROFILE_NAME] if observer else []),
            ]
        )
        extra: dict[str, Any] = {}
        if observer_grants is not None:
            extra["observer_grants"] = list(observer_grants)
        if observer_window_messages is not None:
            extra["observer_window_messages"] = observer_window_messages
        if observer_window_handoffs is not None:
            extra["observer_window_handoffs"] = observer_window_handoffs
        if hop_budget is not None:
            extra["hop_budget"] = hop_budget
        if default_agent is not None:
            extra["default_agent"] = default_agent
        if keep_pre_handoff_prose is not None:
            extra["keep_pre_handoff_prose"] = keep_pre_handoff_prose
        if explainer_template is not None:
            extra["handoff_explainer_template"] = explainer_template
        return LlmConfig(
            base_prompt=base_prompt,
            active_profile=active,
            profiles={
                name: make_profile(
                    name,
                    peers=list(graph.get(name, ())),
                    capabilities=manifests.get(name, ""),
                    # `.get(name)` — NOT `.get(name, "")`. An absent declaration
                    # must stay `None`, because only `None` falls back to the
                    # shared base prompt (A4); `""` is a deliberate empty one.
                    system_prompt=prompts.get(name),
                    persona=voices.get(name),
                    handoff_explainer=overrides.get(name),
                )
                for name in names
            },
            **extra,
        )

    return _make


@pytest.fixture
async def trace_store(tmp_path: Any) -> AsyncIterator[TraceStore]:
    """A started :class:`TraceStore` over a per-test temp DB, stopped on teardown.

    ``stop()`` is awaited in a ``finally`` so the writer task is drained and the
    connection closed even when the test body raises — an abandoned writer task
    would leak into the next test's event loop.
    """
    store = TraceStore(str(tmp_path / "trace.db"))
    await store.start()
    try:
        yield store
    finally:
        await store.stop()
