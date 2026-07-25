"""Collection guard for the voice-venv-only test modules.

Phase 1 deliberately runs two venvs (01-01, 01-03, 01-04): the base test env at
``spike/.venv`` and the torch-pinned voice env at ``spike/voice/.venv``. 01-01
established that ``spike/conftest.py`` imports stdlib + pytest ONLY so that the whole
quarantine collects cleanly under either interpreter, and made
``uv run --python spike/.venv/bin/python pytest spike/ -q`` the canonical command.

Two modules in this directory break that property because they must import the engine
under test at module scope:

* ``test_lang_ids.py``  — imports ``chatterbox`` for the SUPPORTED_LANGUAGES contract.
* ``test_readiness.py`` — GATE 0; its fixtures load chatterbox and dicta_onnx.
* ``test_transcribe_harness.py`` — SPIKE-04; its fixtures load faster-whisper (large-v3).

Under the base venv those imports raise ``ModuleNotFoundError`` during *collection*,
which pytest treats as a hard error that ABORTS THE ENTIRE RUN — the 61 stdlib-only
tests from 01-01/01-02 stop running too. That is why this guard exists.

Why this is not a blanket ``pytest.importorskip``
-------------------------------------------------
An unconditional import-skip would also skip these modules *inside the voice venv* if
chatterbox were broken or uninstalled there — silently turning GATE 0 green-by-absence.
A readiness gate that can vanish is worse than no gate (the same reasoning that put a
negative control in ``test_readiness.py``). So the guard keys on **which interpreter is
running**, not on whether the import happens to work:

* running under ``spike/voice/.venv``  -> never ignore. A missing chatterbox there is a
  real, loud failure, exactly as it should be.
* running under any other interpreter  -> ignore these two modules, with the reason
  reported, and let the stdlib-only suite proceed.

Throwaway spike code (SC#5): dies with ``spike/``.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path


class VoiceGateNotEvaluated(UserWarning):
    """Emitted when GATE 0 modules are skipped because the voice venv is not active."""

#: Modules that require the voice venv (chatterbox / dicta_onnx / torch / faster-whisper)
#: at import time.
VOICE_ONLY_MODULES = ("test_lang_ids.py", "test_readiness.py", "test_transcribe_harness.py")

#: The voice venv provisioned by 01-03, relative to this file.
VOICE_VENV = Path(__file__).resolve().parent / ".venv"


def _running_under_voice_venv() -> bool:
    """True when the active interpreter belongs to ``spike/voice/.venv``."""
    try:
        return Path(sys.prefix).resolve() == VOICE_VENV.resolve()
    except OSError:
        return False


collect_ignore: list[str] = []

SKIP_NOTICE = (
    f"GATE 0 was NOT evaluated by this run: sys.prefix={sys.prefix} is not the voice "
    f"venv ({VOICE_VENV}), so {list(VOICE_ONLY_MODULES)} were not collected. "
    "A green result here says nothing about Hebrew readiness. Run "
    "`uv run --python spike/voice/.venv/bin/python pytest spike/voice/ -q`."
)

if not _running_under_voice_venv():
    collect_ignore.extend(VOICE_ONLY_MODULES)
    # A warning, not `pytest_report_header`: that hook only fires for *initial*
    # conftests, so under the canonical `pytest spike/` invocation (where this conftest
    # is loaded lazily, mid-collection) the header would never print — precisely the
    # case where a green run is most likely to be misread as "GATE 0 passed". Warnings
    # raised at collection time are reported in the warnings summary, which survives
    # `-q`.
    warnings.warn(SKIP_NOTICE, VoiceGateNotEvaluated, stacklevel=2)


def pytest_report_header(config) -> str:
    """Extra visibility when this directory IS the initial arg (`pytest spike/voice/`)."""
    del config
    if collect_ignore:
        return f"voice: {SKIP_NOTICE}"
    return "voice: running under the voice venv -- GATE 0 modules ARE collected."
