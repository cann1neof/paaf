# SPDX-License-Identifier: Apache-2.0
"""Tests for @tool decorator and reflection engine (TOOL-02)."""

from __future__ import annotations

import asyncio
import time
from paaf_llm import execute_tool_func, tool
from paaf_llm.ports import ToolSpec


def test_bare_tool_decorator() -> None:
    """Bare @tool decorator reflects function signature into ToolSpec."""

    @tool
    def add_numbers(a: int, b: int = 10) -> int:
        """Add two integers.

        Args:
            a (int): First number
            b (int): Second number
        """
        return a + b

    spec = getattr(add_numbers, "__tool_spec__")
    assert isinstance(spec, ToolSpec)
    assert spec.name == "add_numbers"
    assert "Add two integers" in spec.description
    assert spec.parameters["type"] == "object"
    assert spec.parameters["required"] == ["a"]

    props = spec.parameters["properties"]
    assert props["a"]["type"] == "integer"
    assert props["a"]["description"] == "First number"
    assert props["b"]["type"] == "integer"
    assert props["b"]["default"] == 10
    assert props["b"]["description"] == "Second number"


def test_parameterized_tool_decorator() -> None:
    """@tool(name=..., description=..., tier=...) overrides defaults."""

    @tool(name="calc_sum", description="Calculate sum of numbers", tier="math")
    def sum_func(x: float, y: float) -> float:
        return x + y

    spec = getattr(sum_func, "__tool_spec__")
    assert spec.name == "calc_sum"
    assert spec.description == "Calculate sum of numbers"
    assert getattr(sum_func, "__tool_tier__") == "math"


def test_sphinx_docstring_parsing() -> None:
    """Docstrings in Sphinx format are parsed for parameter descriptions."""

    @tool
    def search_query(query: str, limit: int = 5) -> list[str]:
        """Execute a text search.

        :param query: Search query text
        :param limit: Max items to return
        """
        return [query] * limit

    spec = getattr(search_query, "__tool_spec__")
    props = spec.parameters["properties"]
    assert props["query"]["description"] == "Search query text"
    assert props["limit"]["description"] == "Max items to return"


async def test_async_tool_execution() -> None:
    """Async tool functions execute directly on the active loop."""

    @tool
    async def async_greet(name: str) -> str:
        await asyncio.sleep(0.01)
        return f"Hello, {name}!"

    result = await execute_tool_func(async_greet, name="Alice")
    assert result == "Hello, Alice!"


async def test_sync_tool_offloaded_execution() -> None:
    """Sync tool functions run off-thread without blocking the event loop."""

    @tool
    def sync_blocking_call(duration: float) -> str:
        time.sleep(duration)
        return "done"

    start = time.time()
    result = await execute_tool_func(sync_blocking_call, duration=0.05)
    elapsed = time.time() - start

    assert result == "done"
    assert elapsed >= 0.04
