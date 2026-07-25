# SPDX-License-Identifier: Apache-2.0
"""PAAF trace store: append-mostly SQLite event log with a first-class TTFA metric.

The DDL lives in ``schema.sql`` (raw SQL, no ORM — CLAUDE.md). ``read_schema()``
returns it so both the store's single writer and the schema tests apply exactly the
same source of truth.
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

# Path to the raw-SQL schema shipped inside the package.
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def read_schema() -> str:
    """Return the trace-store DDL (``runs`` + ``tool_calls``) as raw SQL text."""
    return SCHEMA_PATH.read_text(encoding="utf-8")


__all__ = ["SCHEMA_PATH", "__version__", "read_schema"]
