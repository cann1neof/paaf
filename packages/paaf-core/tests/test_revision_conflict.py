# SPDX-License-Identifier: Apache-2.0
"""CORE-03: optimistic monotonic-revision writes reject stale concurrent edits.

The load-bearing negative control submits a stale ``expected_revision`` and
asserts both that a ``ConflictError`` is raised AND that the on-disk revision is
unchanged — a happy-path-only test would pass vacuously (Phase-1's #1 failure).
"""

import pytest
from paaf_core.config import AppConfig
from paaf_core.config.store import (
    ConflictError,
    atomic_write_bytes,
    dump_config,
    load_config,
    write_config,
)


def _seed(tmp_path, revision: int):
    p = tmp_path / "cfg.yaml"
    lock = tmp_path / "cfg.yaml.lock"
    atomic_write_bytes(str(p), dump_config(AppConfig(revision=revision)))
    return str(p), str(lock)


def test_load_config_validates_on_read(tmp_path):
    p, _ = _seed(tmp_path, revision=1)
    cfg = load_config(p)
    assert isinstance(cfg, AppConfig)
    assert cfg.revision == 1


def test_happy_path_bumps_revision_by_one(tmp_path):
    p, lock = _seed(tmp_path, revision=1)
    new = AppConfig(revision=1, persona="changed")
    returned = write_config(p, lock, new, expected_revision=1)
    assert returned == 2
    on_disk = load_config(p)
    assert on_disk.revision == 2
    assert on_disk.persona == "changed"


def test_stale_revision_raises_conflict_and_leaves_file_untouched(tmp_path):
    # NEGATIVE CONTROL (CORE-03): on-disk revision is 5; a writer that read 3
    # must be rejected and must not clobber the file.
    p, lock = _seed(tmp_path, revision=5)
    stale = AppConfig(revision=5, persona="attempted-clobber")

    with pytest.raises(ConflictError):
        write_config(p, lock, stale, expected_revision=3)

    on_disk = load_config(p)
    assert on_disk.revision == 5
    assert on_disk.persona == "assistant"  # default — the stale write did nothing
