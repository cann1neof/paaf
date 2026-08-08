# SPDX-License-Identifier: Apache-2.0
"""Config persistence: atomic writes (CORE-02) + optimistic revision guard (CORE-03).

Two invariants this module exists to hold:

1. A crash mid-write can never corrupt the config. Every persist goes to a temp
   file in the *same* directory, is fsynced, atomically renamed over the target,
   and the directory itself is fsynced (Pattern 1). Readers always see the whole
   old file or the whole new file, never a partial one.

2. Two writers cannot silently clobber each other. The read-modify-write is
   wrapped in a cross-process ``FileLock`` and gated on a monotonic ``revision``:
   a writer submits the revision it read; if the on-disk revision has moved, the
   write is rejected with ``ConflictError`` (Pattern 2). The lock is what makes
   the guard non-vacuous — without it two processes could both read rev N and
   both write rev N+1 (the documented anti-pattern).
"""

from __future__ import annotations

import io
import os
import tempfile

from filelock import FileLock
from ruamel.yaml import YAML

from .schema import AppConfig

_yaml = YAML()
_yaml.default_flow_style = False


class ConflictError(Exception):
    """Raised when a write's ``expected_revision`` is stale versus on-disk."""


def dump_config(model: AppConfig) -> bytes:
    """Serialize a validated model to YAML bytes (round-trippable by load_config)."""
    buf = io.BytesIO()
    _yaml.dump(model.model_dump(mode="json"), buf)
    return buf.getvalue()


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Durably, atomically write ``data`` to ``path`` (temp + fsync + rename + dirfsync).

    On any failure before the rename, the temp file is removed and the original
    target is left untouched.
    """
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".cfg.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # durability of file contents
        os.replace(tmp, path)  # atomic swap; readers see old-or-new, never partial
        dfd = os.open(d, os.O_DIRECTORY)
        try:
            os.fsync(dfd)  # durability of the rename itself
        finally:
            os.close(dfd)
    except Exception:
        # Clean up the aborted temp file; never leave a dangling partial next to
        # the real config. The original target is still intact (replace failed).
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def load_config(path: str) -> AppConfig:
    """Read YAML from ``path`` and validate it through the typed schema (CORE-01)."""
    with open(path, "rb") as f:
        parsed = _yaml.load(io.BytesIO(f.read()))
    return AppConfig.model_validate(parsed)


def write_config(
    path: str, lock_path: str, new_model: AppConfig, expected_revision: int
) -> int:
    """Atomically persist ``new_model`` iff no one else has written since ``expected_revision``.

    Serializes the read-modify-write behind ``FileLock(lock_path)``. Returns the
    new (bumped) revision. Raises ``ConflictError`` — leaving the file untouched —
    if the on-disk revision no longer equals ``expected_revision``.
    """
    with FileLock(lock_path):
        current = load_config(path)
        if current.revision != expected_revision:
            raise ConflictError(
                f"stale write: expected {expected_revision}, on disk {current.revision}"
            )
        new_model.revision = current.revision + 1  # monotonic
        atomic_write_bytes(path, dump_config(new_model))
        return new_model.revision
