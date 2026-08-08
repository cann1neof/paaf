# SPDX-License-Identifier: Apache-2.0
"""Model-profile schema (MODEL-01/05/06) — the data contract the user owns.

A user names their models in one YAML tree with no code: each named
:class:`ModelProfile` says which provider, which model, which endpoint, and —
in plain language — what it handles and which peers it may later hand off to.

Three deliberate constraints shape this module:

* It **reuses** the Phase-2 substrate rather than reinventing it. Reload tiers
  ride on :class:`paaf_core.config.schema.ReloadTier`; declared endpoints are
  :class:`paaf_core.net.endpoint.Endpoint` values, so Phase-9's APP-08 offline
  check sees model endpoints through the same one interface as everything else.
* ``capabilities`` is **free text**, never structured fields (D-08/D-12).
  Structured capability fields would be a routing DSL by the back door; the mesh
  reads natural language, and the user can read it too. The Phase-4 prompt layer
  — ``system_prompt``, ``persona``, ``handoff_explainer`` and the config-level
  ``handoff_explainer_template`` — is free text for the identical reason: an
  explainer with a structured "hand off when…" field would be an if-then routing
  rule wearing a different hat.
* ``peers`` is **live** as of Phase 4 (MESH-02): it is the reachability graph the
  handoff tool surface is built from and validated against. ``constraints`` stays
  free text and is enforced by the observer (MESH-06, D-13).

The three mesh-shaped fields on this tree mean three different things and are
kept apart on purpose — see :class:`LlmConfig`'s docstring. ``hop_budget`` and
``default_agent`` are a counter and a name; **neither is, or can become, a
routing rule** (MESH-01). The observer's three knobs are the same shape: a grant
(``observer_grants``) and two window sizes. A grant says what the supervisor MAY
DO, never when to do it — the "when" is the observer's own judgement, read out of
free text, exactly as a handoff is the awake model's. ``extra="forbid"`` on both
models is the mechanism that keeps it that way, and it is asserted directly by
the tests.

Secret VALUES never live here: ``api_key_ref`` holds the NAME of a
``paaf_core`` SecretStore key (CORE-04), so no schema, YAML file, or log line
can carry the key itself.
"""

from __future__ import annotations

from typing import Literal

from paaf_core.config.schema import ReloadTier, SkillConfig
from paaf_core.net.endpoint import Endpoint
from pydantic import BaseModel, Field, model_validator

from .mesh import DEFAULT_HOP_BUDGET, HOP_BUDGET_FLOOR, OBSERVER_PROFILE_NAME


class ModelProfile(BaseModel):
    """One named model the user declared: provider, model, endpoint, manifest.

    ``extra="forbid"`` is load-bearing (threat T-03-02): a hand-edited config is
    untrusted input, and refusing unknown keys means no smuggled field — and so
    no hidden routing rule — can ride along in a profile.
    """

    model_config = {"extra": "forbid"}

    # RESTART: changing the provider re-wires the engine (matches the existing
    # ModelConfig.provider precedent in paaf_core).
    provider: Literal["ollama", "openai_compatible", "anthropic"] = Field(
        ..., json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    # COLD: a different model means re-initializing / re-loading it.
    model: str = Field(..., json_schema_extra={"reload_tier": ReloadTier.COLD})

    # RESTART: endpoint rewiring is not a live-swappable change.
    endpoint_host: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    endpoint_port: int | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    endpoint_scheme: str = Field(
        "http", json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    # RESTART: the URL path the declared server serves under — OpenAI-compatible
    # servers commonly serve at `/v1` (vLLM, llama.cpp's server, LM Studio all
    # do). Opt-in: PAAF appends only what the user wrote here, never a guess.
    endpoint_path: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    # RESTART: the user's EXPLICIT statement that this endpoint accepts requests
    # with no credential. It is a declared field rather than an inference from an
    # absent `api_key_ref` because an absent reference is ambiguous between "no
    # auth is needed" and "I forgot" — and guessing the first would send
    # unauthenticated requests to a server on the user's behalf.
    endpoint_unauthenticated: bool = Field(
        False, json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )

    # CORE-04: the NAME of a SecretStore key. Never the key value.
    api_key_ref: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )

    # WARM: a new temperature applies on the next turn.
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM / D-05: the per-profile slow-first-token budget. 10s is generous for
    # an already-warm model; model cold-load time is deliberately NOT charged
    # against it (that would guarantee false triggers on a cold Ollama model).
    first_token_budget_s: float = Field(
        10.0, gt=0.0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )

    # --- the mesh seam (MODEL-05, D-07/D-08): LIVE as of Phase 4 ---
    # `peers` now shapes the handoff tool surface the awake model is offered, and
    # `capabilities` is the text describing each peer on that surface. Both are
    # still FREE TEXT ONLY (D-12 is unchanged): structured capability or
    # constraint fields would be a routing DSL by the back door, and MESH-01
    # forbids one anywhere. The model reads this text and chooses; PAAF never
    # matches on it.
    # WARM: natural-language capability manifest. FREE TEXT ONLY.
    capabilities: str = Field("", json_schema_extra={"reload_tier": ReloadTier.WARM})
    # WARM: names of profiles this one MAY hand off to — the whole reachability
    # graph. `paaf_llm.mesh` builds one `transfer_to_<peer>` tool per name here
    # and validates the model's answer against the same list (MESH-02).
    peers: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: optional hard constraints. FREE TEXT ONLY, by D-12 — enforced by the
    # observer (D-13), which reads them the same way the model reads a manifest.
    constraints: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: THIS agent's own ordered resilience chain (SC#4) — the profiles to
    # try, in the user's order, when this agent's own provider is unreachable,
    # too slow to first token, or erroring on the leg it was asked to answer.
    # Resilience is per-agent because it is nested INSIDE the handoff loop: after
    # a handoff, the agent being asked to answer is the one whose chain applies.
    #
    # It grants NO handoff edge. That is `peers`, and the two are one keystroke
    # apart in a YAML file while meaning opposite things — "this provider broke,
    # try that one" versus "you may delegate this conversation on the merits"
    # (T-04-30). An empty list is not a gap: it means "use the global
    # `LlmConfig.fallback_chain`", which keeps every Phase-3 config behaving
    # exactly as it did.
    fallback_chain: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )

    # --- the per-agent prompt layer (D-16 layer 3, D-17, D-18) ---
    # All three are FREE TEXT, for the same reason `capabilities` is: a
    # structured version would be a routing DSL by the back door (MESH-01,
    # Phase-3 D-08). `extra="forbid"` is unchanged, so a smuggled sibling key is
    # still rejected at load.
    #
    # WARM: THIS agent's own base prompt. `None` means "use the shared
    # `LlmConfig.base_prompt`" — the global stays meaningful as the shared base
    # and these overrides are ADDITIVE rather than a replacement of the global
    # concept (Assumption A4). `None` and `""` are deliberately different: a user
    # who wrote an empty per-agent prompt asked for an empty one, and only an
    # absent declaration may fall back.
    system_prompt: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: how this agent talks to the user (D-16 layer 3) — voice and manner,
    # kept apart from `system_prompt` because "who you are" and "how you sound"
    # are separately editable in every assistant the user has ever configured,
    # and collapsing them would force a rewrite of one to change the other.
    persona: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: a PER-AGENT override of the generated handoff explainer (D-18). When
    # set it is used verbatim — PAAF renders no template around it — and it still
    # appears in `paaf prompt --provenance` under exactly the same label the
    # generated one does. Overriding the explainer changes what the user reads
    # by changing what the model was told, never only one of the two.
    handoff_explainer: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )

    def endpoint(self) -> Endpoint | None:
        """Return the declared endpoint, or ``None`` for a provider default.

        This is the CORE-05 declaration seam: a profile that names a host and
        port is visible to the endpoint registry (and therefore to Phase-9's
        offline refusal) as a `paaf_core` :class:`Endpoint`. A cloud profile
        that relies on the provider's own base URL declares nothing here — it
        is not hidden, it simply has no PAAF-declared endpoint to classify.

        A declared ``endpoint_path`` travels WITH the endpoint rather than being
        re-attached downstream, so the value Phase-9's offline check classifies
        is identical to the one actually dialed. ``path`` is addressing only:
        :meth:`Endpoint.is_lan` reads the host and never the path.
        """
        if self.endpoint_host is None or self.endpoint_port is None:
            return None
        return Endpoint(
            host=self.endpoint_host,
            port=self.endpoint_port,
            scheme=self.endpoint_scheme,
            path=self.endpoint_path or "",
        )

    @model_validator(mode="after")
    def _check_endpoint(self) -> ModelProfile:
        """Reject a malformed endpoint declaration at LOAD, and never repair one.

        A hand-edited config is untrusted input (T-03-02/T-03-36), and this
        field's value ends up inside a URL PAAF dials. So a malformed path is
        *reported* — named, with the offending value — rather than stripped,
        prepended, or rewritten into something plausible. Silently normalizing it
        would mean dialing a URL the user never wrote, which is the same hidden
        behavior a guessed ``/v1`` suffix would be.
        """
        if self.endpoint_path is not None:
            path = self.endpoint_path
            if self.endpoint_host is None or self.endpoint_port is None:
                raise ValueError(
                    f"endpoint_path {path!r} needs a declared endpoint_host and "
                    f"endpoint_port — a path alone addresses nothing"
                )
            if not path.startswith("/"):
                raise ValueError(f"endpoint_path {path!r} must start with '/'")
            if path.endswith("/"):
                raise ValueError(
                    f"endpoint_path {path!r} must not end with '/' — the path is "
                    f"appended verbatim, so a trailing slash would be dialed"
                )
            for character in ("?", "#"):
                if character in path:
                    raise ValueError(
                        f"endpoint_path {path!r} must not contain {character!r}; "
                        f"it is a path, not a query string or a fragment"
                    )
            if any(character.isspace() for character in path):
                raise ValueError(f"endpoint_path {path!r} must not contain whitespace")

        if self.endpoint_unauthenticated:
            if self.api_key_ref is not None:
                raise ValueError(
                    f"endpoint_unauthenticated is true but api_key_ref "
                    f"{self.api_key_ref!r} is also declared — a profile cannot "
                    f"both need no credential and name one"
                )
            if self.provider != "openai_compatible":
                raise ValueError(
                    f"endpoint_unauthenticated is not valid for provider "
                    f"{self.provider!r}; the flag exists for openai_compatible "
                    f"servers, because the local ollama binding already needs no "
                    f"credential and a hosted anthropic endpoint cannot be "
                    f"unauthenticated"
                )

        return self


class LlmConfig(BaseModel):
    """The LLM half of the one YAML tree the user owns.

    ``fallback_chain``, each profile's ``peers``, and ``default_agent`` are kept
    as SEPARATE fields on purpose: they mean three different things.
    ``fallback_chain`` is *resilience* — the ordered list of profiles to try when
    the active one is unreachable, too slow to first token, or erroring
    (MODEL-03). ``peers`` is *handoff* — the profiles a given model may delegate
    to on the merits (MESH-02). ``default_agent`` is the *terminator* — who
    speaks when the mesh has run out of moves and the hop budget is spent (D-09).
    Collapsing any pair would quietly make one mean the others: every fallback
    target a handoff target, or the home agent reachable from everywhere.

    **The GLOBAL ``fallback_chain`` and the PER-AGENT one are one concept at two
    scopes, not a fourth concept** (SC#4). This field is the default resilience
    order for any agent that named none of its own;
    :attr:`ModelProfile.fallback_chain` is that agent's override. It is an
    override rather than a replacement of the concept — exactly the shape
    ``ModelProfile.system_prompt`` follows over ``base_prompt`` (Assumption A4) —
    so every Phase-3 config, none of which declares a per-agent chain, behaves
    identically. What the two scopes never become is a *fourth* meaning: a chain
    entry at either scope still grants no handoff edge (T-04-30).

    **The observer is a RESERVED NAME in this same namespace, not a subsystem**
    (D-03, MESH-06). A profile keyed ``observer`` is the supervising model that
    judges every handoff attempt, and it is configured exactly like any other
    profile — same provider, same endpoint, same ``api_key_ref``, same reload
    tiers, down to its own ``system_prompt``. Declaring none is a legitimate
    configuration and not a gap PAAF fills in: "on by default" means the slot is
    reserved and wired, never that PAAF invents a model to put in it (D-07).

    Reserving the name is what stops enabling the observer from silently making
    every agent reachable from every agent. :meth:`_check_refs` refuses to let it
    be a handoff target, the ``active_profile``, or a ``fallback_chain`` entry at
    either scope — all three would put a supervisor into the conversation as a
    participant, which is a different thing from supervising it (T-04-36). Its
    powers over a handoff are ``observer_grants`` and nothing else.
    """

    model_config = {"extra": "forbid"}

    # PERS-01: the base system prompt, verbatim, owned by the user.
    base_prompt: str = Field("", json_schema_extra={"reload_tier": ReloadTier.WARM})
    active_profile: str = Field(
        ..., json_schema_extra={"reload_tier": ReloadTier.RESTART}
    )
    profiles: dict[str, ModelProfile]
    # MODEL-03: ordered profile names tried in turn when the active one degrades.
    fallback_chain: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )

    # --- mesh-level knobs (D-08/D-09): a counter and a name, never a rule ---
    # WARM: how many handoffs ONE user turn may make before the engine stops
    # offering the handoff tools (D-08). The floor is `mesh.HOP_BUDGET_FLOOR`
    # (3) because the legitimate A→B→A hand-back costs two hops, so anything
    # lower would stand the wall in front of the very behavior MESH-03 requires
    # — and since the wall works by WITHDRAWING the tool, the user would read
    # the failure as an agent that declined to hand back, not as a bad setting.
    # Raising it costs one full time-to-first-token per extra hop (Pitfall 6):
    # handoff is silent (D-10), so from the user's side a hopping turn is just
    # an assistant going quiet. Know that before turning the knob.
    hop_budget: int = Field(
        DEFAULT_HOP_BUDGET,
        ge=HOP_BUDGET_FLOOR,
        json_schema_extra={"reload_tier": ReloadTier.WARM},
    )
    # WARM: the home agent — who speaks when the budget is spent (D-09). A THIRD
    # concept, deliberately not collapsed into `fallback_chain` or `peers`; see
    # the class docstring. Optional, and `None` is not a gap PAAF fills in: with
    # no home agent declared, the currently-awake agent answers with the handoff
    # tools withdrawn (OQ-2). Defaulting to `active_profile` would be PAAF
    # picking an agent on the user's behalf, which D-09 rejects outright.
    default_agent: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: a GLOBAL override of the handoff explainer template (D-18). Free
    # text, and `paaf_llm.mesh` substitutes the peer list into it wherever the
    # user put `mesh.EXPLAINER_PEERS_PLACEHOLDER`; a template that omits the
    # placeholder simply gets no peer list, which is a legitimate thing to ask
    # for and not an error to correct.
    #
    # Precedence is per-agent, then global, then the generated default —
    # narrowest declaration wins, the same shape `ModelProfile.system_prompt`
    # follows over `base_prompt`.
    handoff_explainer_template: str | None = Field(
        None, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: what happens to a "let me get the cook" line an agent emitted just
    # before it handed off (D-11). The default is True, and the reason is the
    # reason rather than the value: PAAF does not silently edit what a model
    # said, so the default is to SHOW it. The user opts INTO dropping it, and
    # even then the text is not lost — the accepted `handoffs` row records the
    # prose verbatim, so the setting is a presentation choice rather than a
    # hidden edit (T-04-31).
    #
    # Two adjacent facts, so nobody reads this field as the whole story:
    # (1) the generated handoff explainer DISCOURAGES the style in prose, and
    # (2) mechanical enforcement — refusing or stripping a leg that spoke before
    #     calling handoff — is a deliberate v2 item the founder flagged as really
    #     important, NOT an oversight. Phase 4 ships no such mechanism, and this
    #     field is not one: it governs presentation only.
    keep_pre_handoff_prose: bool = Field(
        True, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    skills: dict[str, SkillConfig] = Field(
        default_factory=dict, json_schema_extra={"reload_tier": ReloadTier.HOT}
    )

    # --- the observer (MESH-06, D-03/D-04/D-15) ---
    # WARM: what the observer is ALLOWED to do about a handoff attempt. This is
    # a GRANT, never a mode: capability removal, never instruction, because a
    # model cannot talk its way past a tool it does not have (D-04) — the same
    # mechanism `hop_budget` uses at the wall, and the only one that holds
    # whatever the observer is persuaded of. The default is retry-only, so the
    # shipped observer can kill a handoff and can do nothing else; adding
    # "reroute" is a deliberate, readable edit to this line.
    #
    # The spelling is duplicated from `mesh.OBSERVER_GRANTS` because a Pydantic
    # `Literal` cannot be built from a variable; `test_observer.py` asserts the
    # two agree, so the duplication cannot drift unnoticed.
    observer_grants: list[Literal["generic_retry", "reroute"]] = Field(
        default_factory=lambda: ["generic_retry"],
        json_schema_extra={"reload_tier": ReloadTier.WARM},
    )
    # WARM: how much CONVERSATION the observer sees on each attempt (D-15). The
    # default window is 0 extra messages, meaning exactly what D-15 specifies:
    # the last user message, the handoff decision, and the calling agent's own
    # stated reasoning if it gave any. This widens it to the N last messages of
    # the conversation as well.
    #
    # Know this before turning it up (Pitfall 7): a CLOUD observer profile with a
    # wide window ships a slice of your conversation off-box on every single
    # handoff attempt, including the ones that are then rejected — a frequency
    # and a shape quite unlike a normal reply. The observer is an ordinary
    # profile, so its endpoint is declared and Phase-9's offline refusal sees it;
    # this knob is still the one that decides how much goes.
    observer_window_messages: int = Field(
        0, ge=0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: how many of THIS turn's earlier handoff attempts the observer sees
    # (D-15). It exists for one specific purpose rather than for symmetry: an
    # observer that can see it is inside a handoff loop can break the loop
    # gracefully, before the deterministic wall withdraws the tools and the turn
    # ends by exhaustion (D-08 — the budget guarantees termination, the observer
    # makes termination graceful). With 0 the observer judges each attempt with
    # no memory of the previous ones.
    observer_window_handoffs: int = Field(
        0, ge=0, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )

    @model_validator(mode="after")
    def _check_refs(self) -> LlmConfig:
        """Reject any name that does not resolve to a declared profile.

        The peer graph is *traversed* now, so it must be integral: a dangling
        edge discovered at handoff time is a runtime failure mid-conversation.
        Catching it at load turns it into a config error the user can read and
        fix, which is the whole point of validate-on-read.

        ``default_agent`` is held to the same rule, and it is the sharpest case:
        a dangling home agent would only be discovered at budget exhaustion —
        three hops into a turn, at the exact moment the mesh has no other move.

        **It also enforces the reserved observer name** (D-03, T-04-36). The
        observer is never awake, so it must never be reachable as a handoff
        target, must never be the ``active_profile``, and must never appear in a
        ``fallback_chain`` at either scope. Each of those would put a supervisor
        into the conversation as a participant, and the peer case is the one that
        actually matters: without it, enabling the observer would quietly add an
        edge every agent could take. Rejected by name, with the offending profile
        named, in this module's established style.
        """
        names = set(self.profiles)

        # Rule 3 (D-03): the reserved name is not a participant. Checked BEFORE
        # the reference-integrity rules below so the message says "reserved"
        # rather than "undeclared" — the user's mistake is the former, and
        # telling them to declare an `observer` profile they cannot use here
        # would send them in exactly the wrong direction.
        if self.active_profile == OBSERVER_PROFILE_NAME:
            raise ValueError(
                f"active_profile is the reserved name '{OBSERVER_PROFILE_NAME}'; "
                f"the observer supervises handoffs and is never awake, so it "
                f"cannot be the agent that answers"
            )

        for name in self.fallback_chain:
            if name == OBSERVER_PROFILE_NAME:
                raise ValueError(
                    f"fallback_chain references the reserved name "
                    f"'{OBSERVER_PROFILE_NAME}'; the observer is not a provider "
                    f"another agent falls back to"
                )

        if self.active_profile not in names:
            raise ValueError(
                f"active_profile '{self.active_profile}' is not a declared profile"
            )

        if self.default_agent is not None and self.default_agent not in names:
            raise ValueError(
                f"default_agent '{self.default_agent}' is not a declared profile"
            )

        for name in self.fallback_chain:
            if name not in names:
                raise ValueError(
                    f"fallback_chain references undeclared profile '{name}'"
                )

        for profile_name, profile in self.profiles.items():
            for peer in profile.peers:
                if peer == profile_name:
                    raise ValueError(f"profile '{profile_name}' lists itself as a peer")
                # Rule 2 (D-03/T-04-36): the reserved name is not a handoff
                # target. This is the load-bearing half of reserving it — the
                # observer judges attempts, and an agent that could hand the
                # conversation TO its supervisor would turn the supervisor into
                # a participant. It is also the case that would otherwise make
                # enabling the observer add an edge to the graph.
                if peer == OBSERVER_PROFILE_NAME:
                    raise ValueError(
                        f"profile '{profile_name}'.peers lists the reserved name "
                        f"'{OBSERVER_PROFILE_NAME}'; the observer is never awake "
                        f"and must not be a handoff target"
                    )
                if peer not in names:
                    raise ValueError(
                        f"profile '{profile_name}'.peers references "
                        f"undeclared profile '{peer}'"
                    )

            # Rule 4 (SC#4): a per-agent chain is held to the identical
            # reference-integrity rule the peer graph is, and for a sharper
            # version of the same reason — a dangling chain entry is discovered
            # only when the agent's own provider has ALREADY failed, so the user
            # would meet the config error at the exact moment resilience was
            # supposed to save the conversation. The check lives here rather than
            # on ModelProfile because a profile carries no name of its own (its
            # name is the key it sits under), which is why the self-PEER check
            # has always lived here too.
            for entry in profile.fallback_chain:
                if entry == OBSERVER_PROFILE_NAME:
                    raise ValueError(
                        f"profile '{profile_name}'.fallback_chain references the "
                        f"reserved name '{OBSERVER_PROFILE_NAME}'; the observer "
                        f"is not a provider another agent falls back to"
                    )
                if entry == profile_name:
                    raise ValueError(
                        f"profile '{profile_name}' lists itself in its own "
                        f"fallback_chain — falling back to the provider that "
                        f"just failed is not resilience"
                    )
                if entry not in names:
                    raise ValueError(
                        f"profile '{profile_name}'.fallback_chain references "
                        f"undeclared profile '{entry}'"
                    )

        return self
