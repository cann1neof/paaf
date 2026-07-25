# SPDX-License-Identifier: Apache-2.0
"""Smoke test: paaf_session imports and reports its version."""

import paaf_session


def test_smoke_import_and_version() -> None:
    assert paaf_session.__version__ == "0.1.0"
