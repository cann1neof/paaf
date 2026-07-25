# SPDX-License-Identifier: Apache-2.0
"""Smoke test: paaf_core imports and reports its version."""

import paaf_core


def test_smoke_import_and_version() -> None:
    assert paaf_core.__version__ == "0.1.0"
