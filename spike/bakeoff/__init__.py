"""Marks ``spike/bakeoff/`` as a package so its ``conftest.py`` cannot shadow ``spike/conftest.py``.

This file is not optional and it is not stylistic. Without it, pytest's default
``prepend`` import mode inserts ``spike/bakeoff/`` into ``sys.path`` and imports
``spike/bakeoff/conftest.py`` under the top-level module name ``conftest`` — the same
name ``spike/conftest.py`` claims. Only one can win. Directory collection is
alphabetical, ``bakeoff`` sorts before ``test_fixtures_smoke.py``, so the bake-off
conftest won, and 01-01's ``from conftest import FakeModel, FakeTool`` resolved to the
wrong file:

    ImportError: cannot import name 'FakeModel' from 'conftest'
                 (.../spike/bakeoff/conftest.py)
    Interrupted: 1 error during collection

That is a collection error, which pytest treats as fatal for the WHOLE run — the 61
stdlib-only tests from 01-01/01-02 stopped executing. Exactly the regression 01-03 hit
from the other direction, in a new disguise.

With ``__init__.py`` present, pytest walks up to the first directory that is *not* a
package (``spike/``), puts **that** on ``sys.path``, and imports the conftest as
``bakeoff.conftest`` — a distinct module name. ``spike/conftest.py`` keeps the plain
``conftest`` name, and 01-01's import is correct again. The cost is that sibling modules
in this directory must be imported as ``bakeoff.<module>`` rather than bare, which
``test_tool_call_sanity.py`` does.

⚠️ ``spike/voice/`` is deliberately NOT given the same treatment. Its tests use bare
``import gate_readiness``, which package-ifying would break, and it is currently safe only
because ``voice`` sorts *after* ``test_fixtures_smoke.py``. That is alphabetical luck, not
design. Any later plan adding a ``spike/a*/conftest.py`` will hit this again — see the
01-04 SUMMARY's carried concerns.

Throwaway spike code (SC#5): dies with ``spike/``.
"""
