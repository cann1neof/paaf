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
* ``capabilities`` is **free text**, never structured fields (D-08). Structured
  capability fields would be a routing DSL by the back door; the mesh Phase 4
  builds reads natural language, and the user can read it too.
* ``peers`` and ``constraints`` are **inert** in this phase — validated data
  with no behavior attached. Phase 4 (MESH-02/MESH-06) makes them live.

Secret VALUES never live here: ``api_key_ref`` holds the NAME of a
``paaf_core`` SecretStore key (CORE-04), so no schema, YAML file, or log line
can carry the key itself.
"""
from __future__ import annotations

from typing import Literal

from paaf_core.config.schema import ReloadTier
from paaf_core.net.endpoint import Endpoint
from pydantic import BaseModel, Field


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

    # --- inert mesh seam (MODEL-05, D-07/D-08): validated data, no behavior ---
    # WARM: natural-language capability manifest. FREE TEXT ONLY.
    capabilities: str = Field(
        "", json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: names of profiles this one MAY hand off to. Inert in Phase 3;
    # Phase 4 (MESH-02) reads it to constrain handoff targets.
    peers: list[str] = Field(
        default_factory=list, json_schema_extra={"reload_tier": ReloadTier.WARM}
    )
    # WARM: optional hard constraints, declarable now, enforced in Phase 4
    # (MESH-06). Free text for the same reason `capabilities` is.
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
        """
        if self.endpoint_host is None or self.endpoint_port is None:
            return None
        return Endpoint(
            host=self.endpoint_host,
            port=self.endpoint_port,
            scheme=self.endpoint_scheme,
        )
