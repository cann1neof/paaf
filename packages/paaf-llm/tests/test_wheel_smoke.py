# SPDX-License-Identifier: Apache-2.0
"""Wheel smoke test — discoverable via ``pytest --pyargs paaf_llm``.

Run by ``scripts/check_wheel_independence.sh`` INSIDE a clean off-repo venv that
has the built ``paaf-llm`` wheel plus its declared workspace dependencies
(``paaf-core``, ``paaf-trace``) installed — and deliberately WITHOUT the
``[engine]`` extra. Three assertions:

1. the installed wheel imports and reports its version (positive control);
2. ``import paaf_voice`` raises ``ModuleNotFoundError`` — the negative control
   that flips red the moment paaf-llm gains an undeclared dependency on voice
   (RESEARCH Pitfall 2);
3. ``import langchain`` raises ``ModuleNotFoundError`` — the SC#1 negative
   control, at wheel-smoke level, that the agent framework is genuinely absent
   while this suite runs. It flips red if langchain ever moves out of the
   optional ``[engine]`` extra, or if ``paaf_llm/__init__`` starts importing the
   adapter package eagerly instead of lazily (RESEARCH Pitfall 4).

This file is deliberately NOT collected by the ordinary workspace suite — the
root ``conftest.py`` excludes it via ``collect_ignore_glob``, because in the
workspace venv ``paaf_voice`` IS installed and assertion 2 would (correctly) be
false there. The clean venv never loads that conftest, so ``pytest --pyargs
paaf_llm`` still discovers and runs all three assertions where they mean
something. ``scripts/check_wheel_independence.sh`` is the authoritative run.
"""

import paaf_llm
import pytest


def test_wheel_imports_and_reports_version() -> None:
    assert paaf_llm.__version__ == "0.1.0"


def test_paaf_voice_not_importable_from_llm_wheel() -> None:
    with pytest.raises(ModuleNotFoundError):
        __import__("paaf_voice")


def test_langchain_not_importable_from_llm_wheel() -> None:
    """SC#1: the shipped wheel runs with the agent framework uninstalled."""
    with pytest.raises(ModuleNotFoundError):
        __import__("langchain")
