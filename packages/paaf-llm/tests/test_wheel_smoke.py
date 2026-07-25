# SPDX-License-Identifier: Apache-2.0
"""Wheel smoke test — discoverable via ``pytest --pyargs paaf_llm``.

Run by ``scripts/check_wheel_independence.sh`` INSIDE a clean off-repo venv that
has only the built ``paaf-llm`` wheel installed. Two assertions:

1. the installed wheel imports and reports its version (positive control);
2. ``import paaf_voice`` raises ``ModuleNotFoundError`` — the negative control
   that flips red the moment paaf-llm gains an undeclared dependency on voice
   (RESEARCH Pitfall 2).
"""

import pytest

import paaf_llm


def test_wheel_imports_and_reports_version() -> None:
    assert paaf_llm.__version__ == "0.1.0"


def test_paaf_voice_not_importable_from_llm_wheel() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("paaf_voice")
