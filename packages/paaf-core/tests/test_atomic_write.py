# SPDX-License-Identifier: Apache-2.0
"""CORE-02: config writes are atomic and crash-safe.

The load-bearing negative control simulates a failure BETWEEN the temp write and
the rename: the original file must survive intact and no temp file may be left
behind. Without temp+fsync+rename a crash mid-write would corrupt the one YAML
tree the user owns.
"""

import glob

import pytest
from paaf_core.config.store import atomic_write_bytes


def test_atomic_write_creates_and_replaces_content(tmp_path):
    p = tmp_path / "cfg.yaml"
    atomic_write_bytes(str(p), b"hello")
    assert p.read_bytes() == b"hello"
    atomic_write_bytes(str(p), b"world")
    assert p.read_bytes() == b"world"


def test_failure_before_rename_leaves_original_intact(tmp_path, monkeypatch):
    # NEGATIVE CONTROL (CORE-02): inject a crash exactly at os.replace. The temp
    # file has already been written+fsynced, but the swap never happens.
    p = tmp_path / "cfg.yaml"
    p.write_bytes(b"ORIGINAL")

    def boom(src, dst):
        raise OSError("simulated crash before rename")

    monkeypatch.setattr("paaf_core.config.store.os.replace", boom)

    with pytest.raises(OSError):
        atomic_write_bytes(str(p), b"NEWDATA")

    # the durable contract is untouched: readers still see the old-or-new file,
    # never a partial one — here, the old one.
    assert p.read_bytes() == b"ORIGINAL"
    # and the aborted temp file was cleaned up, not left dangling next to it.
    leftovers = glob.glob(str(tmp_path / ".cfg.*"))
    assert leftovers == []
