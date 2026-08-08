# SPDX-License-Identifier: Apache-2.0
"""Reload-tier discovery (CORE-06).

`reload_tiers(model_cls)` walks a Pydantic model's fields (recursing into nested
models with dotted key paths) and returns every leaf key mapped to its
`ReloadTier`. A field carrying no explicit `reload_tier` annotation is reported
with `DEFAULT_TIER` rather than omitted, so the map is exhaustive: the desktop
app can classify *every* key it might edit without special-casing gaps.
"""

from __future__ import annotations

from pydantic import BaseModel

from .schema import ReloadTier

# The conservative default: a key with no declared tier is treated as
# restart-only until it is classified, so nothing is assumed hot-swappable.
DEFAULT_TIER: ReloadTier = ReloadTier.RESTART


def _extract_tier(json_schema_extra: object) -> ReloadTier:
    if isinstance(json_schema_extra, dict):
        tier = json_schema_extra.get("reload_tier")
        if tier is not None:
            return tier if isinstance(tier, ReloadTier) else ReloadTier(tier)
    return DEFAULT_TIER


def reload_tiers(
    model_cls: type[BaseModel], _prefix: str = ""
) -> dict[str, ReloadTier]:
    """Return {dotted_key_path: ReloadTier} for every leaf field of ``model_cls``.

    Nested `BaseModel` fields are recursed into; scalar fields read their
    ``json_schema_extra["reload_tier"]`` and fall back to ``DEFAULT_TIER``.
    """
    result: dict[str, ReloadTier] = {}
    for name, field in model_cls.model_fields.items():
        key = f"{_prefix}{name}"
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            result.update(reload_tiers(annotation, _prefix=f"{key}."))
        else:
            result[key] = _extract_tier(field.json_schema_extra)
    return result
