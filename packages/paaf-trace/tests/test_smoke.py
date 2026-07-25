# SPDX-License-Identifier: Apache-2.0
"""Smoke test: paaf_trace imports and reports its version."""

import paaf_trace


def test_smoke_import_and_version() -> None:
    assert paaf_trace.__version__ == "0.1.0"
