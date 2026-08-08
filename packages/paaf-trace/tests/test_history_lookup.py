# SPDX-License-Identifier: Apache-2.0
"""Tests for date_time_lookup and history_lookup tools (TOOL-01, TOOL-08)."""

from __future__ import annotations

import asyncio
from paaf_llm.tools import date_time_lookup, history_lookup
from paaf_trace.store import CustomEvent, RunEvent, ToolCallEvent, TraceStore


def test_date_time_lookup() -> None:
    res = date_time_lookup()
    assert isinstance(res, dict)
    expected_keys = {
        "local_iso",
        "utc_iso",
        "local_date",
        "local_time",
        "day_of_week",
        "timezone_name",
        "utc_offset",
        "timestamp_epoch",
    }
    assert expected_keys <= set(res.keys())
    assert isinstance(res["timestamp_epoch"], float)


async def test_history_lookup(tmp_path) -> None:
    db_path = str(tmp_path / "test_trace.db")
    store = TraceStore(db_path)
    await store.start()

    store.emit(
        RunEvent(
            id=1,
            prompts="What is the capital of France? Tell me about Paris.",
            model="test-model",
            started_at=1000.0,
            ended_at=1001.0,
            prompt_tokens=10,
            completion_tokens=5,
        )
    )
    store.emit(
        ToolCallEvent(
            run_id=1,
            name="search",
            args='{"q": "Paris"}',
            results='{"res": "Paris is the capital of France"}',
        )
    )
    store.emit(
        CustomEvent(
            event_type="system_health",
            summary="CPU load normal",
            payload='{"cpu": 15}',
            created_at=1005.0,
        )
    )

    await store.stop()

    # Query all
    all_records = history_lookup(db_path=db_path)
    assert len(all_records) == 3

    # Query by event_type 'conversation'
    runs = history_lookup(db_path=db_path, event_type="conversation")
    assert len(runs) == 1
    assert runs[0]["category"] == "conversation"
    assert "capital of France" in runs[0]["details"]["prompts"]

    # Query by event_type 'tool_call'
    tools = history_lookup(db_path=db_path, event_type="tool_call")
    assert len(tools) == 1
    assert tools[0]["category"] == "tool_call"
    assert tools[0]["details"]["name"] == "search"

    # Query by search text query
    filtered = history_lookup(db_path=db_path, query="Paris")
    assert len(filtered) == 2

    # Query by custom_event
    customs = history_lookup(db_path=db_path, event_type="custom_event")
    assert len(customs) == 1
    assert customs[0]["details"]["event_type"] == "system_health"


def test_history_lookup_docstring_explainer() -> None:
    doc = history_lookup.__doc__
    assert doc is not None
    assert "Tool Explainer & Schema Guide" in doc
    assert "conversation" in doc
    assert "tool_call" in doc
    assert "custom_event" in doc
