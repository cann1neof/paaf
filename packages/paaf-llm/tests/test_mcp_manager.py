# SPDX-License-Identifier: Apache-2.0
"""Tests for McpServerManager and paaf mcp CLI commands (TOOL-03, TOOL-04)."""

from __future__ import annotations

import asyncio
from click.testing import CliRunner
from paaf_core.config import McpServerConfig, McpServerTransport
from paaf_llm.cli import main
from paaf_llm.mcp import McpServerManager, McpServerStatus


async def test_mcp_server_manager_initialization() -> None:
    """Non-blocking initialize_all handles valid and failing server configs cleanly."""
    manager = McpServerManager()
    configs = {
        "valid_stdio": McpServerConfig(
            transport=McpServerTransport.STDIO,
            command="echo",
            args=["hello"],
        ),
        "failing_stdio": McpServerConfig(
            transport=McpServerTransport.STDIO,
            command="nonexistent_mcp_binary_xyz_123",
            args=[],
        ),
    }

    await manager.initialize_all(configs, timeout_s=1.0)

    # valid_stdio process launched
    assert manager.get_server_status("valid_stdio") == McpServerStatus.CONNECTED
    # failing_stdio caught error and set status to OFFLINE
    assert manager.get_server_status("failing_stdio") == McpServerStatus.OFFLINE

    await manager.shutdown()


async def test_invoke_tool_on_offline_server() -> None:
    """Invoking a tool on an offline server returns a clean error dict."""
    manager = McpServerManager()
    configs = {
        "offline_server": McpServerConfig(
            transport=McpServerTransport.STDIO,
            command="nonexistent_cmd",
        )
    }
    await manager.initialize_all(configs, timeout_s=0.5)

    res = await manager.invoke_tool("offline_server", "some_tool", {"param": 1})
    assert "error" in res
    assert res["status"] == "offline"

    # Non-existent server
    res_not_found = await manager.invoke_tool("ghost_server", "tool", {})
    assert res_not_found["status"] == "not_found"

    await manager.shutdown()


def test_cli_mcp_add_list_remove(tmp_path) -> None:
    """paaf mcp add, list, and remove work atomically on paaf.yaml."""
    runner = CliRunner()
    config_file = str(tmp_path / "paaf.yaml")

    # 1. Add stdio server
    res_add = runner.invoke(
        main,
        ["mcp", "add", "--config", config_file, "my_stdio", "python", "-m", "server"],
    )
    assert res_add.exit_code == 0
    assert "Added MCP server 'my_stdio'" in res_add.output

    # 2. Add sse server
    res_add_sse = runner.invoke(
        main,
        [
            "mcp",
            "add",
            "--config",
            config_file,
            "--transport",
            "sse",
            "--url",
            "http://localhost:8080/sse",
            "my_sse",
        ],
    )
    assert res_add_sse.exit_code == 0
    assert "Added MCP server 'my_sse'" in res_add_sse.output

    # 3. List servers
    res_list = runner.invoke(main, ["mcp", "list", "--config", config_file])
    assert res_list.exit_code == 0
    assert "my_stdio [stdio]" in res_list.output
    assert "my_sse [sse]" in res_list.output

    # 4. Remove server
    res_remove = runner.invoke(
        main, ["mcp", "remove", "my_stdio", "--config", config_file]
    )
    assert res_remove.exit_code == 0
    assert "Removed MCP server 'my_stdio'" in res_remove.output

    # Verify list after removal
    res_list2 = runner.invoke(main, ["mcp", "list", "--config", config_file])
    assert "my_stdio" not in res_list2.output
    assert "my_sse" in res_list2.output
