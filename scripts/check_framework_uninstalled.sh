# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# MODEL-08 / SC#1 — prove the ENTIRE paaf-llm fake-adapter suite passes with the
# agent framework UNINSTALLED.
#
# This is the phase gate, and it is deliberately the last thing Phase 3 builds.
# Plan 03-08 added the real LangChain adapter; the question that matters after
# that is whether adding it quietly made `langchain` load-bearing. The port is
# only a port if the answer is no — otherwise it is a mirror of whatever
# framework happens to be installed, and MODEL-08's swappability promise is
# decoration.
#
# HOW IT PROVES THAT
#   1. Builds the paaf-llm wheel plus its DECLARED workspace deps (paaf-core,
#      paaf-trace — neither exists on PyPI, so pip can only satisfy them locally).
#   2. Asserts the wheel actually SHIPS every fake-adapter test file that exists
#      in the source tree (see "the non-vacuity guard" below).
#   3. Installs all three into a FRESH venv in a temp dir OUTSIDE the repo, with
#      NO `[engine]` extra — so langchain and langgraph are genuinely absent.
#   4. Runs the whole shipped suite via `pytest --pyargs paaf_llm` from a cwd
#      that is NOT the repo, so the repo's `src/` tree is never on sys.path and
#      only the installed wheel is imported (RESEARCH Pitfall 2, "clean-venv job
#      that isn't clean"). Editable installs are deliberately avoided for the
#      same reason — an editable install puts the source tree back on sys.path
#      and defeats the entire test.
#   5. Negative control: `import langchain` and `import langgraph` must BOTH
#      raise ModuleNotFoundError. Positive control: paaf_llm, paaf_core and
#      paaf_trace must all import, so the negative control cannot "pass" merely
#      because nothing got installed (RESEARCH Pitfall 4).
#
# THE NON-VACUITY GUARD (step 2) IS LOAD-BEARING, NOT DECORATION.
# Without it this gate rots silently: the wheel's shipped test set is an
# explicit, hand-maintained force-include list in packages/paaf-llm/pyproject.toml,
# so a future fake-adapter test file that nobody adds to that list would simply
# never run here — and the job would still print a cheerful green "N passed".
# The guard compares the source tree's tests/ against the wheel's contents and
# fails on any non-excluded file that is missing. `test_engine_adapter.py` is the
# one deliberate exclusion: it tests the REAL adapter, opens with
# `pytest.importorskip("langchain")`, and could only ever SKIP in this venv. It
# runs instead in the complementary `engine-adapter` CI job, WITH the extra
# installed, where it actually executes.
#
# WHY THE EXPLICIT PYTEST FLAGS
# `--pyargs` runs the suite from site-packages, where the repo's root
# pyproject.toml is NOT the rootdir — so NONE of its `addopts` are inherited.
# Every setting the suite needs must therefore be passed here, by hand:
#   -o asyncio_mode=auto        the suite's async tests carry no explicit
#                               @pytest.mark.asyncio; without this, pytest 9
#                               FAILS them outright (it does not skip them).
#   --disable-socket
#   --allow-unix-socket         the offline posture (FOUND-03 / PRIV-02) —
#                               AF_INET is blocked, AF_UNIX (asyncio's self-pipe)
#                               is not. Not inheriting these would let this job
#                               run with the network wide open.
#   -p no:langsmith_plugin      a no-op here (langsmith arrives only with the
#                               [engine] extra, which is precisely what this job
#                               does not install) but stated explicitly so the
#                               refusal survives if that ever stops being true.
# Consequence worth knowing: a bare `pip install paaf-llm && pytest --pyargs
# paaf_llm` does NOT pass on its own — it needs pytest-asyncio and
# `-o asyncio_mode=auto`. That is a property of running a shipped suite through
# --pyargs, not a defect in the wheel; this script is the authoritative run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Test files the wheel is NOT expected to ship, and why. Keep this list as short
# as it possibly can be: every entry is a test that the SC#1 gate does not run.
EXCLUDED_FROM_WHEEL=("test_engine_adapter.py")

# --- 1. Build paaf-llm and its DECLARED framework deps into dist/ ---------------
echo "==> Building paaf-llm, paaf-core and paaf-trace wheels"
rm -f dist/paaf_llm-*.whl dist/paaf_core-*.whl dist/paaf_trace-*.whl
uv build --package paaf-llm
uv build --package paaf-core
uv build --package paaf-trace

WHEEL_PATHS=()
for pattern in paaf_llm paaf_core paaf_trace; do
  found="$(ls "dist/${pattern}-"*.whl 2>/dev/null | head -n1 || true)"
  if [[ -z "${found:-}" || ! -f "$found" ]]; then
    echo "FAIL: no ${pattern} wheel found in dist/ after build" >&2
    exit 1
  fi
  WHEEL_PATHS+=("$REPO_ROOT/$found")
  echo "==> Built $found"
done

PAAF_LLM_WHEEL="${WHEEL_PATHS[0]}"

# --- 2. Non-vacuity: the wheel must ship the WHOLE fake suite --------------------
# Compares the source tree against the built wheel. This is what stops the gate
# from quietly measuring three smoke assertions while claiming to measure a suite.
echo "==> Asserting the wheel ships every fake-adapter test file in the source tree"
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
PAAF_LLM_WHEEL="$PAAF_LLM_WHEEL" EXCLUDED="${EXCLUDED_FROM_WHEEL[*]}" "$PY" - <<'PYEOF'
import os
import sys
import zipfile
from pathlib import Path

wheel = Path(os.environ["PAAF_LLM_WHEEL"])
excluded = set(os.environ["EXCLUDED"].split())

source_tests = {
    p.name
    for p in Path("packages/paaf-llm/tests").glob("*.py")
    if p.name not in excluded
}
assert source_tests, "found no test files in packages/paaf-llm/tests — wrong cwd?"

shipped = {
    Path(n).name
    for n in zipfile.ZipFile(wheel).namelist()
    if n.startswith("paaf_llm/tests/") and n.endswith(".py")
}

missing = sorted(source_tests - shipped)
if missing:
    print(
        "FAIL: these fake-adapter test files exist in the source tree but are "
        f"NOT shipped in the wheel: {missing}.\n"
        "      Add them to [tool.hatch.build.targets.wheel.force-include] in "
        "packages/paaf-llm/pyproject.toml, or add them to EXCLUDED_FROM_WHEEL in "
        "this script WITH a reason. An unshipped test is a test this SC#1 gate "
        "silently does not run.",
        file=sys.stderr,
    )
    sys.exit(1)

leaked = sorted(shipped & excluded)
if leaked:
    print(
        f"FAIL: the wheel ships deliberately-excluded test files: {leaked}. "
        "These require the [engine] extra and can only SKIP in a "
        "framework-uninstalled venv, which muddies the gate.",
        file=sys.stderr,
    )
    sys.exit(1)

print(f"ok: all {len(source_tests)} fake-adapter test files ship in the wheel")
print(f"ok: deliberately excluded (runs in the engine-adapter job): {sorted(excluded)}")
PYEOF

# --- 3. Fresh venv in a temp dir OUTSIDE the repo -------------------------------
CLEAN_DIR="$(mktemp -d)"
cleanup() { rm -rf "$CLEAN_DIR"; }
trap cleanup EXIT

case "$CLEAN_DIR" in
  "$REPO_ROOT"|"$REPO_ROOT"/*)
    echo "FAIL: temp dir $CLEAN_DIR is inside the repo — sys.path would leak the source tree" >&2
    exit 1
    ;;
esac

echo "==> Creating clean venv in $CLEAN_DIR"
"$PY" -m venv "$CLEAN_DIR/venv"
VENV_PY="$CLEAN_DIR/venv/bin/python"

# --- 4. Install the wheels + the test runner, and NOTHING resembling a framework -
# NOTE the absent `[engine]` extra. The three test packages are pinned to the
# versions the workspace's own dev group pins, so a CI-only resolution drift
# cannot make this job disagree with `uv run pytest` about what passes.
echo "==> Installing wheels into clean venv (no [engine] extra => no langchain)"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet "${WHEEL_PATHS[@]}" \
  "pytest==9.1.1" "pytest-asyncio==1.4.0" "pytest-socket==0.7.0"

# --- 5. Import from OUTSIDE the repo (cwd = temp dir) ---------------------------
echo "==> Importing paaf_llm from the installed wheel (cwd outside repo)"
cd "$CLEAN_DIR"
"$VENV_PY" -c "import paaf_llm; print('paaf_llm', paaf_llm.__version__)"

# --- 6. THE GATE: run the whole shipped suite, framework-uninstalled ------------
echo "==> Running the FULL fake-adapter suite via pytest --pyargs paaf_llm"
"$VENV_PY" -m pytest --pyargs paaf_llm -q \
  -o asyncio_mode=auto \
  --disable-socket --allow-unix-socket \
  -p no:langsmith_plugin

# --- 7. Negative control: the agent framework must NOT be importable ------------
echo "==> Asserting langchain and langgraph are NOT importable in the clean venv"
"$VENV_PY" - <<'PYEOF'
import sys

leaked = []
for name in ("langchain", "langgraph"):
    try:
        __import__(name)
        leaked.append(name)
    except ModuleNotFoundError:
        print(f"ok: {name} is not importable (as required)")

# Positive control: without this, the negative control above would also "pass"
# in a venv where the install silently failed and nothing at all is present.
for name in ("paaf_llm", "paaf_core", "paaf_trace"):
    __import__(name)
    print(f"ok: {name} is importable (declared dependency)")

if leaked:
    print(
        f"FAIL: the agent framework leaked into the base install: {leaked}. "
        "Either langchain moved out of the optional [engine] extra into the base "
        "dependencies, or paaf_llm started importing its _engine adapter eagerly "
        "instead of lazily. Either way the port is now a mirror: the shipped "
        "fake suite can no longer run with the framework uninstalled, and "
        "MODEL-08's swappability guarantee is void (SC#1 / RESEARCH Pitfall 4).",
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF

echo "==> PASS: the full paaf-llm fake-adapter suite passes with the agent"
echo "==>       framework uninstalled — the port is a port, not a mirror (SC#1)."
