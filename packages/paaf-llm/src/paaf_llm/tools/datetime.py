# SPDX-License-Identifier: Apache-2.0
"""Built-in datetime lookup tool (TOOL-01)."""

from __future__ import annotations

from datetime import datetime, timezone
import time


def date_time_lookup() -> dict[str, str | float]:
    """Look up the current date, time, day of week, timezone, and UTC offset.

    Returns:
        dict containing:
            - local_iso: Local date and time formatted in ISO 8601 format.
            - utc_iso: UTC date and time formatted in ISO 8601 format.
            - local_date: Current local date (YYYY-MM-DD).
            - local_time: Current local time (HH:MM:SS).
            - day_of_week: Day of the week name (e.g. Monday, Tuesday).
            - timezone_name: Name or abbreviation of local timezone.
            - utc_offset: Local timezone offset from UTC (e.g. +03:00).
            - timestamp_epoch: Monotonic unix epoch timestamp in seconds.
    """
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()

    offset_str = now_local.strftime("%z")
    formatted_offset = (
        f"{offset_str[:3]}:{offset_str[3:]}" if len(offset_str) == 5 else offset_str
    )

    return {
        "local_iso": now_local.isoformat(),
        "utc_iso": now_utc.isoformat(),
        "local_date": now_local.strftime("%Y-%m-%d"),
        "local_time": now_local.strftime("%H:%M:%S"),
        "day_of_week": now_local.strftime("%A"),
        "timezone_name": now_local.tzname() or "",
        "utc_offset": formatted_offset,
        "timestamp_epoch": time.time(),
    }
