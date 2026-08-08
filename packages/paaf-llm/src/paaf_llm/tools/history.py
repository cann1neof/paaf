# SPDX-License-Identifier: Apache-2.0
"""Built-in history lookup tool (TOOL-08)."""

from __future__ import annotations

import sqlite3
import time
from typing import Any


def history_lookup(
    db_path: str = "trace.db",
    query: str | None = None,
    event_type: str | None = None,
    since_seconds_ago: float | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query past assistant runs, tool calls, and background events from the trace store.

    Tool Explainer & Schema Guide:
    ------------------------------
    This tool allows searching past turn history, tool execution logs, and background system events
    off the hot execution path using structured filtering rather than raw SQL.

    Queryable Event Types (`event_type` parameter):
      - 'conversation' (or 'run'): Search past assistant runs, prompts, models used, and token usage.
      - 'tool_call': Search tool invocations, names, arguments, and execution results.
      - 'custom_event': Search background system events, health checks, or observer logs.
      - None / empty: Query across all categories matching the search text and time filter.

    Parameters:
      - query (str, optional): Substring or keyword to search for in prompts, tool args/results, or event summaries.
      - event_type (str, optional): Filter by category ('conversation', 'tool_call', 'custom_event').
      - since_seconds_ago (float, optional): Restrict results to events that occurred within the last N seconds.
      - limit (int, default 50): Maximum number of matching events to return (capped between 1 and 200).

    Returns:
      A list of dictionaries representing matched history records sorted chronologically (most recent first).
      Each record contains:
        - category: 'conversation', 'tool_call', or 'custom_event'
        - timestamp: monotonic or epoch timestamp in seconds
        - details: summary dictionary containing relevant fields (prompts, tool args, event summary, etc.)
    """
    limit = max(1, min(limit, 200))
    min_time = (
        time.time() - since_seconds_ago if since_seconds_ago is not None else None
    )
    results: list[dict[str, Any]] = []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        try:
            conn = sqlite3.connect(db_path)
        except sqlite3.Error:
            return []

    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # 1. Runs (conversation)
        if event_type in (None, "", "conversation", "run"):
            sql = "SELECT id, prompts, model, started_at, ended_at, prompt_tokens, completion_tokens FROM runs"
            conditions: list[str] = []
            params: list[Any] = []
            if min_time is not None:
                conditions.append("started_at >= ?")
                params.append(min_time)
            if query:
                conditions.append("(prompts LIKE ? OR model LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%"])
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY started_at DESC LIMIT ?"
            params.append(limit)

            try:
                for row in cursor.execute(sql, tuple(params)).fetchall():
                    results.append(
                        {
                            "category": "conversation",
                            "timestamp": row["started_at"],
                            "details": {
                                "id": row["id"],
                                "prompts": row["prompts"],
                                "model": row["model"],
                                "prompt_tokens": row["prompt_tokens"],
                                "completion_tokens": row["completion_tokens"],
                            },
                        }
                    )
            except sqlite3.OperationalError:
                pass

        # 2. Tool Calls
        if event_type in (None, "", "tool_call"):
            sql = "SELECT id, run_id, name, args, results FROM tool_calls"
            conditions = []
            params = []
            if query:
                conditions.append(
                    "(name LIKE ? OR args LIKE ? OR results LIKE ?)"
                )
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            try:
                for row in cursor.execute(sql, tuple(params)).fetchall():
                    results.append(
                        {
                            "category": "tool_call",
                            "timestamp": None,
                            "details": {
                                "id": row["id"],
                                "run_id": row["run_id"],
                                "name": row["name"],
                                "args": row["args"],
                                "results": row["results"],
                            },
                        }
                    )
            except sqlite3.OperationalError:
                pass

        # 3. Custom Events
        if event_type in (None, "", "custom_event"):
            sql = "SELECT id, event_type, summary, payload, created_at FROM custom_events"
            conditions = []
            params = []
            if min_time is not None:
                conditions.append("created_at >= ?")
                params.append(min_time)
            if query:
                conditions.append(
                    "(event_type LIKE ? OR summary LIKE ? OR payload LIKE ?)"
                )
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            try:
                for row in cursor.execute(sql, tuple(params)).fetchall():
                    results.append(
                        {
                            "category": "custom_event",
                            "timestamp": row["created_at"],
                            "details": {
                                "id": row["id"],
                                "event_type": row["event_type"],
                                "summary": row["summary"],
                                "payload": row["payload"],
                            },
                        }
                    )
            except sqlite3.OperationalError:
                pass

    finally:
        conn.close()

    results.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)
    return results[:limit]
