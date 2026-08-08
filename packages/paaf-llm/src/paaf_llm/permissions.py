# SPDX-License-Identifier: Apache-2.0
"""Permission Engine for tool authorization tiers (TOOL-05, TOOL-06)."""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import Any, Callable, Coroutine

from paaf_core.config import AppConfig, PermissionTier


class PermissionEngine:
    """Evaluates effective permission tiers for tools across defaults, config, and overrides."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()
        self._cli_overrides: dict[str, PermissionTier] = {}

    def set_override(self, tool_name: str, tier: PermissionTier) -> None:
        """Set a runtime/CLI permission override for a tool."""
        self._cli_overrides[tool_name] = tier

    def resolve_tier(
        self,
        tool_name: str,
        source: str = "builtin",
        default_tier: PermissionTier | None = None,
    ) -> PermissionTier:
        """Resolve effective permission tier for tool_name.

        Hierarchy: CLI override -> AppConfig.tools.permissions -> default_tier -> source default.
        """
        if tool_name in self._cli_overrides:
            return self._cli_overrides[tool_name]

        if tool_name in self.config.tools.permissions:
            return self.config.tools.permissions[tool_name]

        if default_tier is not None:
            return default_tier

        if tool_name in ("date_time_lookup", "history_lookup"):
            return PermissionTier.OBSERVE

        return PermissionTier.ACT


class ConfirmationResult(str, Enum):
    """Outcome of a spoken confirmation request."""

    GRANTED = "granted"
    DENIED = "denied"


def format_spoken_confirmation_prompt(tool_name: str) -> str:
    """Format clean spoken confirmation prompt (D-06)."""
    return f"Can I use tool {tool_name}?"


async def request_spoken_confirmation(
    tool_name: str,
    user_response_provider: Callable[[], str | Coroutine[Any, Any, str]] | None = None,
    timeout_s: float = 10.0,
    trace: Any = None,
) -> ConfirmationResult:
    """Execute spoken confirmation loop for confirm-tier tools."""
    prompt = format_spoken_confirmation_prompt(tool_name)

    if trace is not None:
        from paaf_trace.store import CustomEvent

        trace.emit(
            CustomEvent(
                event_type="tool_call_permission_requested",
                summary=f"Permission requested for {tool_name}",
                payload=f'{{"tool": "{tool_name}", "prompt": "{prompt}"}}',
            )
        )

    if user_response_provider is None:
        if trace is not None:
            from paaf_trace.store import CustomEvent

            trace.emit(
                CustomEvent(
                    event_type="tool_call_permission_denied",
                    summary=f"Permission denied for {tool_name} (no user response)",
                    payload=f'{{"tool": "{tool_name}", "reason": "no_response"}}',
                )
            )
        return ConfirmationResult.DENIED

    try:
        if asyncio.iscoroutinefunction(user_response_provider):
            res_str = await asyncio.wait_for(
                user_response_provider(), timeout=timeout_s
            )
        else:
            res_str = await asyncio.wait_for(
                asyncio.to_thread(user_response_provider), timeout=timeout_s
            )
    except (asyncio.TimeoutError, Exception):
        if trace is not None:
            from paaf_trace.store import CustomEvent

            trace.emit(
                CustomEvent(
                    event_type="tool_call_permission_denied",
                    summary=f"Permission denied for {tool_name} (timeout)",
                    payload=f'{{"tool": "{tool_name}", "reason": "timeout"}}',
                )
            )
        return ConfirmationResult.DENIED

    cleaned = (res_str or "").strip().lower()
    if cleaned in ("yes", "y", "sure", "ok", "approved", "granted", "confirm", "allow"):
        if trace is not None:
            from paaf_trace.store import CustomEvent

            trace.emit(
                CustomEvent(
                    event_type="tool_call_permission_granted",
                    summary=f"Permission granted for {tool_name}",
                    payload=f'{{"tool": "{tool_name}"}}',
                )
            )
        return ConfirmationResult.GRANTED
    else:
        if trace is not None:
            from paaf_trace.store import CustomEvent

            trace.emit(
                CustomEvent(
                    event_type="tool_call_permission_denied",
                    summary=f"Permission denied for {tool_name}",
                    payload=f'{{"tool": "{tool_name}", "response": "{cleaned}"}}',
                )
            )
        return ConfirmationResult.DENIED
