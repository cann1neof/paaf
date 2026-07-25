# SPDX-License-Identifier: Apache-2.0
"""Smoke test: paaf_voice imports and reports its version."""

import paaf_voice


def test_smoke_import_and_version() -> None:
    assert paaf_voice.__version__ == "0.1.0"
