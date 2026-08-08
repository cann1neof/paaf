# SPDX-License-Identifier: Apache-2.0
"""Built-in system tools for paaf-llm."""

from paaf_llm.ports import ToolSpec

from .datetime import date_time_lookup
from .history import history_lookup

DATETIME_LOOKUP_SPEC = ToolSpec(
    name="date_time_lookup",
    description="Look up the current date, time, day of week, timezone, and UTC offset.",
    parameters={"type": "object", "properties": {}},
)

HISTORY_LOOKUP_SPEC = ToolSpec(
    name="history_lookup",
    description="Query past assistant runs, tool calls, and background events from the trace store.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search text"},
            "event_type": {
                "type": "string",
                "description": "Category filter ('conversation', 'tool_call', 'custom_event')",
            },
            "since_seconds_ago": {
                "type": "number",
                "description": "Events within last N seconds",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum records to return",
            },
        },
    },
)

APPROVE_HANDOFF_SPEC = ToolSpec(
    name="approve_handoff",
    description="Approve the handoff attempt as requested without changes.",
    parameters={"type": "object", "properties": {}},
)

VETO_HANDOFF_SPEC = ToolSpec(
    name="veto_handoff",
    description="Veto/refuse the handoff attempt and return control to the caller.",
    parameters={
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Reason for veto"}
        },
    },
)

REROUTE_HANDOFF_SPEC = ToolSpec(
    name="reroute_handoff",
    description="Reroute the handoff attempt to a different peer.",
    parameters={
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target peer name"}
        },
    },
)


def get_handoff_tool_spec(peer: str) -> ToolSpec:
    """Return a transfer_to_<peer> ToolSpec for a given peer name."""
    return ToolSpec(
        name=f"transfer_to_{peer}",
        description=f"Transfer conversation control to peer {peer}.",
        parameters={"type": "object", "properties": {}},
    )


BUILTIN_TOOL_SPECS: list[ToolSpec] = [
    DATETIME_LOOKUP_SPEC,
    HISTORY_LOOKUP_SPEC,
    APPROVE_HANDOFF_SPEC,
    VETO_HANDOFF_SPEC,
    REROUTE_HANDOFF_SPEC,
]

__all__ = [
    "date_time_lookup",
    "history_lookup",
    "DATETIME_LOOKUP_SPEC",
    "HISTORY_LOOKUP_SPEC",
    "APPROVE_HANDOFF_SPEC",
    "VETO_HANDOFF_SPEC",
    "REROUTE_HANDOFF_SPEC",
    "get_handoff_tool_spec",
    "BUILTIN_TOOL_SPECS",
]
