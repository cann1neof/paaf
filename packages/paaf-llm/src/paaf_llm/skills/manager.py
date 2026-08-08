# SPDX-License-Identifier: Apache-2.0
"""Skill lifecycle manager for enabling/disabling skills and resolving active persona fragments (SKILL-04, SKILL-05).

SECURITY NOTICE: Skills run in-process with no sandbox; manifest permissions
provide disclosure, not process isolation. For untrusted code, use MCP servers.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from paaf_llm.cli import load_llm_config
from paaf_llm.compose import PromptComposer
from paaf_llm.profiles import LlmConfig
from paaf_llm.registry import ToolRegistry
from paaf_llm.skills.loader import load_skill_tools
from paaf_llm.skills.manifest import SkillManifest


class SkillManager:
    """Manager for enabling, disabling, and discovering PAAF skills."""

    @staticmethod
    def enable_skill(
        skill_name: str,
        project_root: Path | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        """Enable a skill in paaf.yaml and hot-reload tool registry."""
        root = project_root or Path.cwd()
        config_path_str = str(root / "paaf.yaml")

        if not os.path.exists(config_path_str):
            raise FileNotFoundError(f"paaf.yaml not found at {config_path_str}")

        app_cfg = load_llm_config(config_path_str)
        if skill_name not in app_cfg.skills:
            raise KeyError(f"Skill '{skill_name}' is not registered in paaf.yaml")

        app_cfg.skills[skill_name].enabled = True
        with open(config_path_str, "w", encoding="utf-8") as f:
            yaml.dump(app_cfg.model_dump(mode="json"), f, sort_keys=False)

        if registry is not None:
            skill_dir = root / app_cfg.skills[skill_name].path
            load_skill_tools(skill_dir, skill_name, registry)

    @staticmethod
    def disable_skill(
        skill_name: str,
        project_root: Path | None = None,
        registry: ToolRegistry | None = None,
    ) -> None:
        """Disable a skill in paaf.yaml and hot-reload tool registry."""
        root = project_root or Path.cwd()
        config_path_str = str(root / "paaf.yaml")

        if not os.path.exists(config_path_str):
            raise FileNotFoundError(f"paaf.yaml not found at {config_path_str}")

        app_cfg = load_llm_config(config_path_str)
        if skill_name not in app_cfg.skills:
            raise KeyError(f"Skill '{skill_name}' is not registered in paaf.yaml")

        app_cfg.skills[skill_name].enabled = False
        with open(config_path_str, "w", encoding="utf-8") as f:
            yaml.dump(app_cfg.model_dump(mode="json"), f, sort_keys=False)

        if registry is not None:
            registry.unregister_source(f"skill:{skill_name}")

    @staticmethod
    def get_active_persona_fragments(
        config: LlmConfig, project_root: Path | None = None
    ) -> list[tuple[str, str]]:
        """Return list of (skill_name, fragment_text) pairs for all enabled skills in AppConfig."""
        root = project_root or Path.cwd()
        fragments: list[tuple[str, str]] = []

        for skill_name, skill_cfg in config.skills.items():
            if not skill_cfg.enabled:
                continue

            skill_dir = root / skill_cfg.path
            if not skill_dir.exists():
                continue

            manifest = SkillManifest.load(skill_dir)
            frag_filename = manifest.persona_fragment or "prompt.md"
            frag_path = skill_dir / frag_filename

            if frag_path.exists():
                with open(frag_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                fragment_text = f"--- Skill: {skill_name} ---\n{content}"
                fragments.append((skill_name, fragment_text))

        return fragments
