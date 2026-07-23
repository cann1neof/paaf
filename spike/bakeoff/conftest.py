"""Collection guard for the bake-off-venv-only test modules.

Same shape, and the same reasoning, as ``spike/voice/conftest.py`` (01-03). Phase 1 runs
three venvs: the stdlib-only base env at ``spike/.venv``, the torch-pinned voice env at
``spike/voice/.venv`` (01-03), and the LangChain/Pydantic-AI env at
``spike/bakeoff/.venv`` (01-04). 01-01 made
``uv run --python spike/.venv/bin/python pytest spike/ -q`` the canonical command and kept
``spike/conftest.py`` importing stdlib + pytest ONLY so the whole quarantine collects under
any interpreter.

``test_tool_call_sanity.py`` breaks that property: it imports ``tool_call_sanity``, which
imports ``langchain`` and ``ollama``. Under the base venv that raises
``ModuleNotFoundError`` during *collection*, which pytest treats as a hard error that
ABORTS THE ENTIRE RUN — exactly the regression 01-03 hit and fixed. Without this guard the
61 stdlib-only tests from 01-01/01-02 would stop executing the moment this plan landed.

Why not ``pytest.importorskip``
-------------------------------
An import-keyed skip would also skip this module *inside the bake-off venv* if langchain
were broken there — silently turning the tool-call gate green by absence. A capability
gate that can vanish is worse than no gate; SPIKE-06 would then attribute a weak model's
failure to the framework, which is the precise misattribution this gate exists to prevent
(RESEARCH §Assumptions Log A5). So the guard keys on **which interpreter is running**, not
on whether the import happens to work:

* running under ``spike/bakeoff/.venv``  -> never ignore. A missing langchain there is a
  real, loud failure.
* running under any other interpreter    -> ignore, announce the reason, and let the
  stdlib-only suite proceed.

Throwaway spike code (SC#5): dies with ``spike/``.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path


class BakeoffGateNotEvaluated(UserWarning):
    """Emitted when the tool-call gate is skipped because the bake-off venv is not active."""


#: Modules requiring the bake-off venv (langchain / pydantic-ai / ollama) at import time.
BAKEOFF_ONLY_MODULES = ("test_tool_call_sanity.py",)

#: The bake-off venv provisioned by 01-04, relative to this file.
BAKEOFF_VENV = Path(__file__).resolve().parent / ".venv"


def _running_under_bakeoff_venv() -> bool:
    """True when the active interpreter belongs to ``spike/bakeoff/.venv``."""
    try:
        return Path(sys.prefix).resolve() == BAKEOFF_VENV.resolve()
    except OSError:
        return False


collect_ignore: list[str] = []

SKIP_NOTICE = (
    f"The TOOL-CALL SANITY GATE was NOT evaluated by this run: sys.prefix={sys.prefix} is "
    f"not the bake-off venv ({BAKEOFF_VENV}), so {list(BAKEOFF_ONLY_MODULES)} were not "
    "collected. A green result here says nothing about whether the local model can emit a "
    "well-formed tool call, and therefore nothing about whether SPIKE-06's MCP tracing "
    "result would be attributable to the framework. Run "
    "`uv run --python spike/bakeoff/.venv/bin/python pytest spike/bakeoff/ -q`."
)

if not _running_under_bakeoff_venv():
    collect_ignore.extend(BAKEOFF_ONLY_MODULES)
    # A warning, not `pytest_report_header`: that hook fires only for *initial* conftests,
    # so under the canonical `pytest spike/` invocation this conftest loads lazily,
    # mid-collection, and the header would never print — precisely the case where a green
    # run is most likely to be misread as "the gate passed". Collection-time warnings
    # appear in the warnings summary, which survives `-q`. (01-03, deviation 2.)
    warnings.warn(SKIP_NOTICE, BakeoffGateNotEvaluated, stacklevel=2)


def pytest_report_header(config) -> str:
    """Extra visibility when this directory IS the initial arg (`pytest spike/bakeoff/`)."""
    del config
    if collect_ignore:
        return f"bakeoff: {SKIP_NOTICE}"
    return "bakeoff: running under the bake-off venv -- the tool-call gate IS collected."
