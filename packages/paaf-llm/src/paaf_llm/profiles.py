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
  reads natural language, and the user can read it too.
* ``peers`` is **live** as of Phase 4 (MESH-02): it is the reachability graph the
  handoff tool surface is built from and validated against. ``constraints`` stays
  free text and is enforced by the observer (MESH-06, D-13).

The three mesh-shaped fields on this tree mean three different things and are
kept apart on purpose — see :class:`LlmConfig`'s docstring. ``hop_budget`` and
``default_agent`` are a counter and a name; **neither is, or can become, a
routing rule** (MESH-01). ``extra="forbid"`` on both models is the mechanism
that keeps it that way, and it is asserted directly by the tests.

Secret VALUES never live here: ``api_key_ref`` holds the NAME of a
``paaf_core`` SecretStore key (CORE-04), so no schema, YAML file, or log line
can carry the key itself.
"""
from __future__ import annotations

from typing import Literal

from paaf_core.config.schema import ReloadTier
from paaf_core.net.endpoint import Endpoint
from pydantic import BaseModel, Field, model_validator

from .mesh import DEFAULT_HOP_BUDGET, HOP_BUDGET_FLOOR


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
    capabilities: str = Field(
        "", json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
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
                raise ValueError(
                    f"endpoint_path {path!r} must not contain whitespace"
                )

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
        """
        names = set(self.profiles)

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
                if peer not in names:
                    raise ValueError(
                        f"profile '{profile_name}'.peers references "
                        f"undeclared profile '{peer}'"
                    )

        return self
