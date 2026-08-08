# SPDX-License-Identifier: Apache-2.0
"""Tests for PermissionEngine resolution and CLI overrides (TOOL-05)."""

from __future__ import annotations

from click.testing import CliRunner
from paaf_core.config import AppConfig, PermissionTier, ToolsConfig
from paaf_llm.cli import main
from paaf_llm.permissions import PermissionEngine


def test_permission_engine_resolution_hierarchy() -> None:
    """Permission hierarchy resolves: CLI override -> AppConfig.tools.permissions -> defaults."""
    cfg = AppConfig(
        tools=ToolsConfig(
            permissions={
                "date_time_lookup": PermissionTier.ACT,
                "custom_tool": PermissionTier.CONFIRM,
            }
        )
    )
    engine = PermissionEngine(cfg)

    # date_time_lookup overridden in config to ACT
    assert engine.resolve_tier("date_time_lookup") == PermissionTier.ACT

    # custom_tool overridden in config to CONFIRM
    assert engine.resolve_tier("custom_tool") == PermissionTier.CONFIRM

    # default builtin observe rule
    assert engine.resolve_tier("history_lookup") == PermissionTier.OBSERVE

    # default fallback act rule
    assert engine.resolve_tier("other_tool") == PermissionTier.ACT

    # CLI runtime override takes highest priority
    engine.set_override("date_time_lookup", PermissionTier.CONFIRM)
    assert engine.resolve_tier("date_time_lookup") == PermissionTier.CONFIRM


def test_cli_tools_list_and_permission_override(tmp_path) -> None:
    """paaf tools list and paaf tools permission update paaf.yaml atomically."""
    runner = CliRunner()
    config_file = str(tmp_path / "paaf.yaml")

    # List tools
    res_list = runner.invoke(main, ["tools", "list", "--config", config_file])
    assert res_list.exit_code == 0
    assert "date_time_lookup" in res_list.output

    # Update permission tier
    res_perm = runner.invoke(
        main,
        [
            "tools",
            "permission",
            "date_time_lookup",
            "confirm",
            "--config",
            config_file,
        ],
    )
    assert res_perm.exit_code == 0
    assert "Updated permission for 'date_time_lookup' to 'confirm'" in res_perm.output

    # List tools again and check updated tier
    res_list2 = runner.invoke(main, ["tools", "list", "--config", config_file])
    assert "date_time_lookup [builtin] (tier: confirm)" in res_list2.output
