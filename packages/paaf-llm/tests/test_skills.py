# SPDX-License-Identifier: Apache-2.0
"""Tests for skill manifest parsing, tool autodiscovery, staging installation, and CLI commands."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from click import ClickException
from click.testing import CliRunner

from paaf_core.config import AppConfig, PermissionTier
from paaf_llm.cli import main
from paaf_llm.registry import ToolRegistry
from paaf_llm.skills.installer import install_skill
from paaf_llm.skills.loader import load_skill_tools
from paaf_llm.skills.manifest import SkillManifest


@pytest.fixture
def sample_skill_dir(tmp_path: Path) -> Path:
    skill_dir = tmp_path / "my_sample_skill"
    skill_dir.mkdir()

    manifest_data = {
        "name": "sample_skill",
        "version": "1.0.0",
        "description": "A sample skill for testing",
        "tools": ["sample_tool"],
        "permissions": {"file_access": "confirm"},
        "dependencies": [],
    }

    with open(skill_dir / "skill.yaml", "w", encoding="utf-8") as f:
        yaml.dump(manifest_data, f)

    tool_code = '''# sample tool file
from paaf_llm.tools.decorator import tool

@tool(description="A sample tool function")
def sample_tool(query: str) -> str:
    """Run sample query."""
    return f"Result for {query}"
'''
    with open(skill_dir / "tools.py", "w", encoding="utf-8") as f:
        f.write(tool_code)

    return skill_dir


def test_manifest_validation(sample_skill_dir: Path) -> None:
    manifest = SkillManifest.load(sample_skill_dir)
    assert manifest.name == "sample_skill"
    assert manifest.version == "1.0.0"
    assert manifest.permissions["file_access"] == PermissionTier.CONFIRM

    # Test invalid skill name
    invalid_dir = sample_skill_dir.parent / "invalid_skill"
    invalid_dir.mkdir()
    with open(invalid_dir / "skill.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"name": "invalid/skill/name!", "version": "0.1.0"}, f)

    with pytest.raises(ValueError, match="Invalid skill name"):
        SkillManifest.load(invalid_dir)


def test_loader_autodiscovery(sample_skill_dir: Path) -> None:
    registry = ToolRegistry()
    load_skill_tools(sample_skill_dir, "sample_skill", registry)

    specs = registry.get_specs()
    assert len(specs) == 1
    assert specs[0].name == "sample_tool"

    # Test collision namespacing
    load_skill_tools(sample_skill_dir, "another_skill", registry)
    tool_names = [t.name for t in registry.get_specs()]
    assert "sample_tool" in tool_names
    assert "skill_another_skill_sample_tool" in tool_names


def test_staging_installation(tmp_path: Path, sample_skill_dir: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Initial paaf.yaml
    with open(project_root / "paaf.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"active_profile": "cloud", "profiles": {"cloud": {"provider": "ollama", "model": "llama3.1"}}}, f)

    manifest = install_skill(
        target=str(sample_skill_dir),
        auto_approve=True,
        project_root=project_root,
    )

    assert manifest.name == "sample_skill"
    installed_dir = project_root / ".paaf" / "skills" / "sample_skill"
    assert installed_dir.exists()
    assert (installed_dir / "skill.yaml").exists()

    # Verify paaf.yaml updated
    with open(project_root / "paaf.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert "skills" in data
    assert "sample_skill" in data["skills"]
    assert data["skills"]["sample_skill"]["enabled"] is True


def test_installation_failure_staging_retention(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()

    bad_skill_dir = tmp_path / "bad_skill"
    bad_skill_dir.mkdir()
    with open(bad_skill_dir / "skill.yaml", "w", encoding="utf-8") as f:
        f.write("invalid yaml: [")

    with pytest.raises(Exception):
        install_skill(
            target=str(bad_skill_dir),
            auto_approve=True,
            project_root=project_root,
        )

    # Verify staging directory exists and is retained for debugging (D-08)
    staging_dir = project_root / ".paaf" / "staging"
    assert staging_dir.exists()
    staging_folders = list(staging_dir.iterdir())
    assert len(staging_folders) == 1

    # Verify skills dir remains clean
    skills_dir = project_root / ".paaf" / "skills"
def test_cli_skill_commands(tmp_path: Path, sample_skill_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with open(tmp_path / "paaf.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"active_profile": "cloud", "profiles": {"cloud": {"provider": "ollama", "model": "llama3.1"}}}, f)

    runner = CliRunner()
    res = runner.invoke(main, ["skill", "install", "-y", str(sample_skill_dir)])
    assert res.exit_code == 0
    assert "Successfully installed skill 'sample_skill'" in res.output

    res_list = runner.invoke(main, ["skill", "list"])
    assert res_list.exit_code == 0
    assert "sample_skill" in res_list.output

    # Disable skill
    res_disable = runner.invoke(main, ["skill", "disable", "sample_skill"])
    assert res_disable.exit_code == 0
    assert "Disabled skill 'sample_skill'" in res_disable.output

    # Enable skill
    res_enable = runner.invoke(main, ["skill", "enable", "sample_skill"])
    assert res_enable.exit_code == 0
    assert "Enabled skill 'sample_skill'" in res_enable.output


def test_enable_disable_registry_and_compose(tmp_path: Path, sample_skill_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    with open(sample_skill_dir / "prompt.md", "w", encoding="utf-8") as f:
        f.write("System instructions from sample skill.")

    with open(tmp_path / "paaf.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"active_profile": "cloud", "profiles": {"cloud": {"provider": "ollama", "model": "llama3.1"}}}, f)

    runner = CliRunner()
    runner.invoke(main, ["skill", "install", "-y", str(sample_skill_dir)])

    from paaf_llm.cli import load_llm_config
    from paaf_llm.skills.manager import SkillManager

    app_cfg = load_llm_config(str(tmp_path / "paaf.yaml"))
    fragments = SkillManager.get_active_persona_fragments(app_cfg, project_root=tmp_path)
    assert len(fragments) == 1
    assert fragments[0][0] == "sample_skill"
    assert "--- Skill: sample_skill ---" in fragments[0][1]

    registry = ToolRegistry()
    load_skill_tools(tmp_path / app_cfg.skills["sample_skill"].path, "sample_skill", registry)
    assert len(registry.get_specs()) == 1

    # Disable
    SkillManager.disable_skill("sample_skill", project_root=tmp_path, registry=registry)
    assert len(registry.get_specs()) == 0

    app_cfg_disabled = load_llm_config(str(tmp_path / "paaf.yaml"))
    fragments_disabled = SkillManager.get_active_persona_fragments(app_cfg_disabled, project_root=tmp_path)
    assert len(fragments_disabled) == 0

    # Skill files still intact on disk
    assert (tmp_path / ".paaf" / "skills" / "sample_skill" / "skill.yaml").exists()

