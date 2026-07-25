# SPDX-License-Identifier: Apache-2.0
"""Workspace-root pytest fixtures shared by every package's tests.

Three fixtures are exported:

* ``frozen_clock`` — a deterministic, settable clock (NOT wall-clock). Plan 09's
  TTFA accuracy assertion needs ``abs(recorded_ttfa - injected_delay) < tol`` to be
  reproducible, so the clock is driven by an internal counter you advance explicitly.
* ``tmp_config_path`` — a writable temp file path for config read/write tests
  (atomic-write and revision-conflict tests in Plan 04).
* ``captured_logs`` — captures emitted log records so secret-absence assertions
  (Plan 05, CORE-04) can prove a secret value never reached the logs.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

# FOUND-02 / Plan 03: the wheel-independence smoke test asserts that paaf_voice /
# paaf_core are NOT importable. That is only true inside the isolated clean venv
# built by scripts/check_wheel_independence.sh (run via `pytest --pyargs paaf_llm`).
# In THIS workspace those packages are installed, so the assertion would (correctly)
# be false — exclude the file from the workspace suite. The clean venv never loads
# this conftest, so `--pyargs paaf_llm` still discovers and runs the test there.
collect_ignore_glob = ["**/test_wheel_smoke.py"]


class FrozenClock:
    """A controllable monotonic clock backed by a settable counter.

    ``now()`` and ``monotonic()`` both read the same internal value; ``advance()``
    moves it forward. Nothing here reads the wall clock, so tests are deterministic.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._t = float(start)

    def now(self) -> float:
        return self._t

    def monotonic(self) -> float:
        return self._t

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("frozen_clock cannot move backwards")
        self._t += float(seconds)
        return self._t


@pytest.fixture
def frozen_clock() -> FrozenClock:
    """A deterministic clock with .now(), .monotonic(), and .advance(seconds)."""
    return FrozenClock()


@pytest.fixture
def tmp_config_path(tmp_path: Path) -> Path:
    """A writable temp file path for config tests (file need not exist yet)."""
    return tmp_path / "config.yaml"


class _ListLogHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class CapturedLogs:
    """Holds captured log records; ``.messages`` renders them for substring checks."""

    def __init__(self, handler: _ListLogHandler) -> None:
        self._handler = handler

    @property
    def records(self) -> list[logging.LogRecord]:
        return self._handler.records

    @property
    def messages(self) -> list[str]:
        return [r.getMessage() for r in self._handler.records]


@pytest.fixture
def captured_logs() -> Iterator[CapturedLogs]:
    """Capture records emitted on the root logger for the duration of a test."""
    handler = _ListLogHandler()
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield CapturedLogs(handler)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)
