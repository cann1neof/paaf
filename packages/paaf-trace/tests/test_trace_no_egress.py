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
  * After importing ``paaf_trace`` in a PRISTINE interpreter, no outbound HTTP
    client module is present in ``sys.modules`` — the import graph carries no
    phone-home client. The fresh process matters: read over the running pytest
    session instead, this would report on whatever every other test happened to
    import rather than on ``paaf_trace``.
"""

from __future__ import annotations

import subprocess
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
    store.emit(
        RunEvent(id=1, prompts="audit me", model="qwen3", time_to_first_audio=0.3)
    )
    store.emit(ToolCallEvent(run_id=1, name="noop", args="{}", results="ok"))
    await store.stop()

    async with (
        aiosqlite.connect(str(db_path)) as db,
        db.execute("SELECT prompts, time_to_first_audio FROM runs WHERE id = 1") as cur,
    ):
        row = await cur.fetchone()
    # Reaching here under --disable-socket proves the path opened no network socket.
    assert row == ("audit me", 0.3)


def test_no_http_client_in_import_graph() -> None:
    """Importing paaf_trace pulls in no outbound HTTP client module (TRACE-05).

    Measured in a FRESH interpreter, not over this process's ``sys.modules``.
    Reading the running pytest process answers "has anything in this session
    imported an HTTP client?", which is a different — and much weaker — question
    than the one this test's name asks. It also turns red for reasons that have
    nothing to do with the trace store: installing the optional
    ``paaf-llm[engine]`` extra brings ``langsmith``, ``openai``, and ``ollama``
    into the environment, and any test that legitimately imports one of them
    would fail this assertion while ``paaf_trace`` remained perfectly clean.

    The child process is immune to that. The positive control (``paaf_trace``
    really was imported) keeps the absence assertion from passing vacuously on a
    child that failed before it got started.
    """
    probe = (
        "import sys, paaf_trace, paaf_trace.metrics, paaf_trace.store; "
        "print('\\n'.join(sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr

    loaded = set(result.stdout.split())
    assert "paaf_trace.store" in loaded, "the probe did not import the trace store"
    present = sorted(name for name in _HTTP_CLIENTS if name in loaded)
    assert present == [], f"unexpected HTTP client(s) in import graph: {present}"
