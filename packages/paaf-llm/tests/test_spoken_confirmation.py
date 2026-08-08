# SPDX-License-Identifier: Apache-2.0
"""Tests for spoken confirmation turn loop and clean prompt invariants (TOOL-06)."""

from __future__ import annotations

import asyncio
from paaf_llm.permissions import (
    ConfirmationResult,
    format_spoken_confirmation_prompt,
    request_spoken_confirmation,
)
from paaf_trace.store import TraceStore


def test_format_spoken_confirmation_prompt() -> None:
    """Clean spoken prompt invariant (D-06): 'Can I use tool <name>?' without extra noise."""
    prompt = format_spoken_confirmation_prompt("delete_database")
    assert prompt == "Can I use tool delete_database?"


async def test_spoken_confirmation_granted(tmp_path) -> None:
    """Affirmative response grants permission and emits trace event."""
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()

    res = await request_spoken_confirmation(
        "deploy_code",
        user_response_provider=lambda: "yes",
        timeout_s=1.0,
        trace=store,
    )
    assert res == ConfirmationResult.GRANTED

    await store.stop()

    events = await store.query_custom_events()
    event_types = [e["event_type"] for e in events]
    assert "tool_call_permission_requested" in event_types
    assert "tool_call_permission_granted" in event_types


async def test_spoken_confirmation_denied(tmp_path) -> None:
    """Negative response denies permission and emits trace event."""
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()

    res = await request_spoken_confirmation(
        "delete_database",
        user_response_provider=lambda: "no",
        timeout_s=1.0,
        trace=store,
    )
    assert res == ConfirmationResult.DENIED

    await store.stop()

    events = await store.query_custom_events()
    event_types = [e["event_type"] for e in events]
    assert "tool_call_permission_requested" in event_types
    assert "tool_call_permission_denied" in event_types


async def test_spoken_confirmation_timeout_default_denied(tmp_path) -> None:
    """Timeout or missing provider defaults to DENIED (D-08)."""
    db_path = str(tmp_path / "trace.db")
    store = TraceStore(db_path)
    await store.start()

    async def slow_user():
        await asyncio.sleep(0.5)
        return "yes"

    res = await request_spoken_confirmation(
        "reboot_server",
        user_response_provider=slow_user,
        timeout_s=0.1,
        trace=store,
    )
    assert res == ConfirmationResult.DENIED

    await store.stop()

    events = await store.query_custom_events()
    event_types = [e["event_type"] for e in events]
    assert "tool_call_permission_denied" in event_types
