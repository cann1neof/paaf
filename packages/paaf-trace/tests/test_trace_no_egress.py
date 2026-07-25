# SPDX-License-Identifier: Apache-2.0
"""TRACE-05 runtime no-egress control: the trace store never leaves the device.

Two complementary checks (the runtime half of TRACE-05; the static half is the Plan 02
``no-network-client-in-framework`` import-linter contract, whose negative control already
proves it bites on a deliberate ``import httpx``):

  * The full emit -> write -> read path runs to completion under the suite's
    ``--disable-socket`` default. AF_INET/AF_INET6 sockets are blocked, so any accidental
    network call would raise ``SocketBlockedError`` and fail this test. (aiosqlite uses
    threads + local files, no sockets; the only permitted socket is asyncio's local
    AF_UNIX self-pipe via ``--allow-unix-socket``, which cannot leave the device.)
  * After importing ``paaf_trace`` no outbound HTTP client module is present in
    ``sys.modules`` — the import graph carries no phone-home client.
"""

from __future__ import annotations

import sys

import aiosqlite
from paaf_trace.store import RunEvent, ToolCallEvent, TraceStore

# HTTP/socket client modules that must never appear in the paaf_trace import graph.
_HTTP_CLIENTS = ("httpx", "requests", "aiohttp")


async def test_full_path_runs_with_no_network(tmp_path) -> None:
    """emit -> single-writer WAL write -> read back, all with no AF_INET socket opened."""
    db_path = tmp_path / "trace.db"
    store = TraceStore(str(db_path))
    await store.start()
    store.emit(RunEvent(id=1, prompts="audit me", model="qwen3", time_to_first_audio=0.3))
    store.emit(ToolCallEvent(run_id=1, name="noop", args="{}", results="ok"))
    await store.stop()

    async with aiosqlite.connect(str(db_path)) as db, db.execute(
        "SELECT prompts, time_to_first_audio FROM runs WHERE id = 1"
    ) as cur:
        row = await cur.fetchone()
    # Reaching here under --disable-socket proves the path opened no network socket.
    assert row == ("audit me", 0.3)


def test_no_http_client_in_import_graph() -> None:
    """Importing paaf_trace pulls in no outbound HTTP client module (TRACE-05)."""
    import paaf_trace
    import paaf_trace.metrics
    import paaf_trace.store  # noqa: F401

    present = [name for name in _HTTP_CLIENTS if name in sys.modules]
    assert present == [], f"unexpected HTTP client(s) in import graph: {present}"
