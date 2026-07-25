# SPDX-License-Identifier: Apache-2.0
"""Smoke test: paaf_llm imports and reports its version."""

import paaf_llm


def test_smoke_import_and_version() -> None:
    assert paaf_llm.__version__ == "0.1.0"
