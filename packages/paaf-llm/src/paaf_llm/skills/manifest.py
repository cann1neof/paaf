# SPDX-License-Identifier: Apache-2.0
"""Skill manifest schema (skill.yaml) and parser."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from paaf_core.config.schema import PermissionTier
from pydantic import BaseModel, Field, field_validator

NAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


class SkillManifest(BaseModel):
    """Manifest definition for a PAAF skill (skill.yaml)."""

    model_config = {"extra": "forbid"}

    name: str
    version: str
    description: str = ""
    persona_fragment: str = "prompt.md"
    tools: list[str] = Field(default_factory=list)
    permissions: dict[str, PermissionTier] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not NAME_REGEX.match(v):
            raise ValueError(
                f"Invalid skill name '{v}': must match regex ^[a-zA-Z0-9_-]+$"
            )
        return v

    @classmethod
    def load(cls, skill_dir: Path) -> SkillManifest:
        """Load and parse skill.yaml from skill directory."""
        manifest_path = skill_dir / "skill.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Skill manifest not found at {manifest_path}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse YAML from {manifest_path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Manifest in {manifest_path} must be a YAML mapping/dict")

        return cls.model_validate(data)
