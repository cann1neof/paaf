# SPDX-License-Identifier: Apache-2.0
"""Tests for ToolRegistry and name collision resolution (TOOL-04)."""

from __future__ import annotations

from paaf_core.config import PermissionTier
from paaf_llm.ports import ToolSpec
from paaf_llm.registry import ToolRegistry


def test_tool_registry_registration() -> None:
    """ToolRegistry registers tools and preserves source and spec metadata."""
    registry = ToolRegistry()
    spec = ToolSpec(name="date_time_lookup", description="desc", parameters={})
    name = registry.register(
        spec, source="builtin", default_tier=PermissionTier.OBSERVE
    )

    assert name == "date_time_lookup"
    tool_entry = registry.get("date_time_lookup")
    assert tool_entry is not None
    assert tool_entry.source == "builtin"
    assert tool_entry.default_tier == PermissionTier.OBSERVE


def test_name_collision_scoped_prefix_fallback() -> None:
    """Collision on tool name triggers scoped prefix fallback (e.g. mcp_server1_search)."""
    registry = ToolRegistry()

    spec1 = ToolSpec(name="search", description="Builtin search", parameters={})
    reg1 = registry.register(spec1, source="builtin")
    assert reg1 == "search"

    spec2 = ToolSpec(name="search", description="MCP search", parameters={})
    reg2 = registry.register(spec2, source="mcp:server1", mcp_server="server1")
    assert reg2 == "mcp_server1_search"

    specs = registry.get_specs()
    names = [s.name for s in specs]
    assert "search" in names
    assert "mcp_server1_search" in names
