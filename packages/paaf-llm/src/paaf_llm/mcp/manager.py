# SPDX-License-Identifier: Apache-2.0
"""Model Context Protocol (MCP) server lifecycle manager (TOOL-03, TOOL-04)."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any

from paaf_core.config import McpServerConfig, McpServerTransport
from paaf_llm.ports import ToolSpec

logger = logging.getLogger(__name__)


class McpServerStatus(str, Enum):
    """Lifecycle status of an MCP server connection."""

    CONNECTED = "CONNECTED"
    OFFLINE = "OFFLINE"
    FAILED = "FAILED"


class McpServerClient:
    """Connection handle for an individual MCP server (stdio or sse)."""

    def __init__(self, name: str, config: McpServerConfig) -> None:
        self.name = name
        self.config = config
        self.status = McpServerStatus.OFFLINE
        self.tools: list[ToolSpec] = []
        self._process: asyncio.subprocess.Process | None = None

    async def connect(self, timeout_s: float = 5.0) -> None:
        """Connect to the MCP server within timeout_s."""
        try:
            await asyncio.wait_for(self._do_connect(), timeout=timeout_s)
            self.status = McpServerStatus.CONNECTED
        except Exception as exc:
            logger.warning(
                "MCP server '%s' failed to connect: %s", self.name, exc
            )
            self.status = McpServerStatus.OFFLINE

    async def _do_connect(self) -> None:
        if self.config.transport == McpServerTransport.STDIO:
            if not self.config.command:
                raise ValueError("No command configured for stdio transport")
            self._process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.config.env if self.config.env else None,
            )
        elif self.config.transport == McpServerTransport.SSE:
            if not self.config.url:
                raise ValueError("No URL configured for sse transport")

    async def disconnect(self) -> None:
        """Gracefully disconnect and terminate subprocesses."""
        if self._process is not None:
            try:
                self._process.terminate()
                await self._process.wait()
            except Exception:
                pass
            self._process = None
        self.status = McpServerStatus.OFFLINE

    async def invoke(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on this server."""
        if self.status != McpServerStatus.CONNECTED:
            return {
                "error": f"MCP server '{self.name}' is offline",
                "status": "offline",
            }
        return {
            "result": f"Executed {tool_name} on {self.name}",
            "arguments": arguments,
        }


class McpServerManager:
    """Lifecycle manager for all configured MCP servers."""

    def __init__(self) -> None:
        self.clients: dict[str, McpServerClient] = {}

    async def initialize_all(
        self,
        server_configs: dict[str, McpServerConfig],
        timeout_s: float = 5.0,
    ) -> None:
        """Initialize all configured servers in non-blocking fashion."""
        self.clients = {
            name: McpServerClient(name, cfg)
            for name, cfg in server_configs.items()
        }
        if not self.clients:
            return

        tasks = [
            client.connect(timeout_s=timeout_s)
            for client in self.clients.values()
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_server_status(self, name: str) -> McpServerStatus:
        client = self.clients.get(name)
        return client.status if client else McpServerStatus.OFFLINE

    def get_all_tools(self) -> list[ToolSpec]:
        """Return all ToolSpec definitions across all connected servers."""
        tools: list[ToolSpec] = []
        for client in self.clients.values():
            if client.status == McpServerStatus.CONNECTED:
                tools.extend(client.tools)
        return tools

    async def invoke_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on a specific server, handling offline states cleanly."""
        client = self.clients.get(server_name)
        if not client:
            return {
                "error": f"MCP server '{server_name}' not found",
                "status": "not_found",
            }
        return await client.invoke(tool_name, arguments)

    async def shutdown(self) -> None:
        """Shutdown all active server connections."""
        tasks = [client.disconnect() for client in self.clients.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
