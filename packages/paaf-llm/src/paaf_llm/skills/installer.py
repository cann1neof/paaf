# SPDX-License-Identifier: Apache-2.0
"""Skill installation engine with staging, permission review, and config update (SKILL-02, SKILL-03, SKILL-05)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml
from click import ClickException
from paaf_core.config import SkillConfig
from paaf_llm.cli import load_llm_config
from paaf_llm.profiles import LlmConfig, ModelProfile
from paaf_llm.skills.manifest import SkillManifest
from rich.console import Console

SECURITY_DISCLOSURE_TEXT = (
    "SECURITY NOTICE: Skills run in-process with no sandbox; manifest permissions "
    "provide disclosure, not process isolation. For untrusted code, use MCP servers."
)


def install_skill(
    target: str,
    auto_approve: bool = False,
    project_root: Path | None = None,
    console: Console | None = None,
) -> SkillManifest:
    """Install a skill from a git URL or local directory path using staging."""
    root = project_root or Path.cwd()
    paaf_dir = root / ".paaf"
    staging_base = paaf_dir / "staging"
    skills_base = paaf_dir / "skills"

    staging_base.mkdir(parents=True, exist_ok=True)
    skills_base.mkdir(parents=True, exist_ok=True)

    staging_id = str(uuid.uuid4())
    staging_dir = staging_base / staging_id

    try:
        # Step 1: Copy or clone into staging
        target_path = Path(target)
        if target_path.exists() and target_path.is_dir():
            shutil.copytree(target_path, staging_dir)
        else:
            res = subprocess.run(
                ["git", "clone", target, str(staging_dir)],
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                raise ClickException(f"Git clone failed: {res.stderr.strip()}")

        # Step 2: Load and validate manifest
        manifest = SkillManifest.load(staging_dir)
        skill_name = manifest.name
        final_dir = skills_base / skill_name

        if final_dir.exists():
            raise ClickException(f"Skill '{skill_name}' is already installed at {final_dir}")

        # Step 3: Interactive permission review & security disclosure
        _console = console or Console()
        _console.print(f"\n[bold cyan]Skill Installation Review:[/] [bold]{manifest.name}[/] v{manifest.version}")
        _console.print(f"Description: {manifest.description or 'N/A'}")
        _console.print(f"Tools declared: {', '.join(manifest.tools) or 'None'}")
        _console.print(f"Dependencies declared: {', '.join(manifest.dependencies) or 'None'}")
        _console.print("Permissions requested:")
        if manifest.permissions:
            for perm, tier in manifest.permissions.items():
                tier_val = getattr(tier, "value", str(tier))
                _console.print(f"  - [yellow]{perm}[/]: [bold]{tier_val}[/]")
        else:
            _console.print("  - None")

        _console.print(f"\n[bold red]{SECURITY_DISCLOSURE_TEXT}[/]\n")

        if not auto_approve:
            if not sys.stdin.isatty():
                raise ClickException(
                    "Interactive permission review required in non-interactive environment. "
                    "Use --yes or --approve-permissions to auto-approve."
                )
            confirm = input(f"Approve installation of skill '{skill_name}'? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                raise ClickException("Skill installation cancelled by user.")

        # Step 4: Install declared Python dependencies if any
        if manifest.dependencies:
            cmd = ["uv", "pip", "install"] + manifest.dependencies
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                # fallback to pip if uv pip fails or is unavailable
                cmd = [sys.executable, "-m", "pip", "install"] + manifest.dependencies
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode != 0:
                    raise ClickException(f"Failed to install dependencies: {res.stderr.strip()}")

        # Step 5: Atomic move staging to final skills directory
        staging_dir.rename(final_dir)

        # Step 6: Update paaf.yaml config
        config_path_str = str(root / "paaf.yaml")
        if os.path.exists(config_path_str):
            app_cfg = load_llm_config(config_path_str)
        else:
            app_cfg = LlmConfig(
                active_profile="cloud",
                profiles={"cloud": ModelProfile(provider="ollama", model="llama3.1")},
            )

        app_cfg.skills[skill_name] = SkillConfig(
            enabled=True,
            path=f".paaf/skills/{skill_name}",
            permissions=manifest.permissions,
        )

        with open(config_path_str, "w", encoding="utf-8") as f:
            yaml.dump(app_cfg.model_dump(mode="json"), f, sort_keys=False)

        _console.print(f"[bold green]Successfully installed skill '{skill_name}' to .paaf/skills/{skill_name}[/]")
        return manifest

    except Exception:
        # Note: on failure, do NOT remove staging_dir to preserve it for debugging (D-08)
        raise
