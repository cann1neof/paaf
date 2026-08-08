# SPDX-License-Identifier: Apache-2.0
"""Unified Tool Registry for built-in, custom @tool, and MCP sources (TOOL-04, TOOL-05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from paaf_core.config import PermissionTier
from paaf_llm.permissions import PermissionEngine
from paaf_llm.ports import ToolSpec


@dataclass(slots=True)
class RegisteredTool:
    """Metadata and execution handle for a registered tool."""

    spec: ToolSpec
    source: str
    func: Callable[..., Any] | None = None
    default_tier: PermissionTier = PermissionTier.ACT
    mcp_server: str | None = None

    def get_tier(
        self, engine: PermissionEngine | None = None
    ) -> PermissionTier:
        if engine is not None:
            return engine.resolve_tier(
                self.spec.name,
                source=self.source,
                default_tier=self.default_tier,
            )
        return self.default_tier


class ToolRegistry:
    """Unified Tool Registry supporting collision-resilient namespacing and source metadata."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}
        self._raw_names: dict[str, str] = {}

    def register(
        self,
        spec: ToolSpec,
        source: str = "custom",
        func: Callable[..., Any] | None = None,
        default_tier: PermissionTier = PermissionTier.ACT,
        mcp_server: str | None = None,
    ) -> str:
        """Register a tool. On name collision, apply scoped prefix fallback."""
        name = spec.name
        reg_name = name

        if reg_name in self._tools:
            prefix = source.replace(":", "_")
            reg_name = f"{prefix}_{name}"
            spec = ToolSpec(
                name=reg_name,
                description=spec.description,
                parameters=spec.parameters,
            )

        tool_entry = RegisteredTool(
            spec=spec,
            source=source,
            func=func,
            default_tier=default_tier,
            mcp_server=mcp_server,
        )
        self._tools[reg_name] = tool_entry
        self._raw_names[name] = reg_name
        return reg_name

    def unregister_source(self, source: str) -> list[str]:
        """Unregister all tools registered under a specific source. Returns list of removed tool names."""
        to_remove = [
            reg_name
            for reg_name, tool in self._tools.items()
            if tool.source == source
        ]
        for reg_name in to_remove:
            del self._tools[reg_name]
        self._raw_names = {
            raw: reg
            for raw, reg in self._raw_names.items()
            if reg not in to_remove
        }
        return to_remove

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[RegisteredTool]:
        return list(self._tools.values())

    def get_specs(self) -> list[ToolSpec]:
        return [t.spec for t in self._tools.values()]
