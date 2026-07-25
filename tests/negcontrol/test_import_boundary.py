# SPDX-License-Identifier: Apache-2.0
"""Negative controls for the import-linter contracts (FOUND-04).

A guard that cannot fail is not a guard — Phase 1 twice caught contracts passing
vacuously. These tests are the load-bearing proof that each of the three contracts in
the real root `.importlinter` actually turns RED on a deliberate violation, while the
real workspace stays GREEN.

Mechanism: each deliberately-violating fixture package under this directory
(``paaf_voice_violation`` imports ``paaf_llm``; ``paaf_llm_langchain_violation`` imports
``langchain``; ``paaf_trace_net_violation`` imports ``httpx``) is analyzed by a separate
``.importlinter-negcontrol`` config that maps the same three contract types onto them.
import-linter is static AST analysis, so the forbidden externals need not be installed
and no socket is ever opened — the ``--disable-socket`` suite default is irrelevant to a
subprocess anyway. The fixtures live OUTSIDE ``packages/`` so the real contract never
sees them.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

NEGCONTROL_DIR = Path(__file__).resolve().parent
REPO_ROOT = NEGCONTROL_DIR.parents[1]
NEGCONTROL_CONFIG = NEGCONTROL_DIR / ".importlinter-negcontrol"

# lint-imports ships as a console script next to the active interpreter.
_LINT = Path(sys.executable).parent / "lint-imports"
LINT_IMPORTS = str(_LINT) if _LINT.exists() else (shutil.which("lint-imports") or "lint-imports")

# (contract id in the negcontrol config, contract name printed in output)
VIOLATION_CASES = [
    ("independence", "voice-and-llm-are-independent"),
    ("langchain", "langchain-confined-to-adapter"),
    ("no-network", "no-network-client-in-framework"),
]


def _run_negcontrol(contract_id: str) -> subprocess.CompletedProcess:
    """Run lint-imports against the negcontrol config, with fixtures on PYTHONPATH."""
    env = os.environ.copy()
    # The violation fixture packages resolve only when this dir is importable.
    env["PYTHONPATH"] = os.pathsep.join(
        [str(NEGCONTROL_DIR)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    return subprocess.run(
        [
            LINT_IMPORTS,
            "--config",
            str(NEGCONTROL_CONFIG),
            "--contract",
            contract_id,
            "--no-cache",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_real_importlinter_is_green():
    """The real root `.importlinter` must exit 0 — no forbidden import exists yet.

    This is the green half of the pair: the guard is silent on clean input. Run with a
    plain environment (the negcontrol fixtures are NOT on PYTHONPATH) from the repo root
    so default config discovery picks up `.importlinter`.
    """
    result = subprocess.run(
        [LINT_IMPORTS, "--no-cache"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "the real workspace must stay green:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.parametrize("contract_id,contract_name", VIOLATION_CASES)
def test_contract_goes_red_on_violation(contract_id: str, contract_name: str):
    """Each contract must exit NONZERO and name itself when its violation is present."""
    result = _run_negcontrol(contract_id)
    output = result.stdout + result.stderr
    assert result.returncode != 0, (
        f"contract '{contract_name}' failed to fail on its deliberate violation "
        f"(exit {result.returncode}). A guard that cannot fail is not a guard.\n"
        f"output:\n{output}"
    )
    assert contract_name in output, (
        f"expected the broken contract name '{contract_name}' in lint-imports output.\n"
        f"output:\n{output}"
    )
