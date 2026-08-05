# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# FOUND-02 / SC#1 / SC#2 — prove paaf-llm installs with its framework deps
# (paaf-core, paaf-trace) but WITHOUT the agent framework (langchain).
#
# This script builds the paaf-llm, paaf-core and paaf-trace wheels, installs all
# three into a FRESH venv created in a temp dir OUTSIDE the repo tree, and runs
# paaf-llm's smoke tests via `pytest --pyargs paaf_llm` from a cwd that is NOT
# the repo — so the repo's `src/` tree is never on sys.path and only the
# installed wheels are imported (RESEARCH Pitfall 2: "Clean-venv wheel job that
# isn't clean").
#
# Crucially it installs paaf-llm WITHOUT the `[engine]` extra, so no LangChain
# is present. That is the SC#1 proof: the shipped wheel runs its fake-adapter
# suite with the agent framework uninstalled.
#
# Negative control (the load-bearing half): assert that `import paaf_voice` and
# `import langchain` both raise ModuleNotFoundError. If either import succeeds,
# this script exits nonzero — flipping the CI job RED the instant paaf-llm gains
# a coupling to voice or a hard dependency on the agent framework.
#
# `paaf_core` is NOT in that set. Phase 3 made paaf-core (and paaf-trace)
# DECLARED dependencies of paaf-llm — ModelProfile reuses paaf-core's ReloadTier
# and Endpoint — so their presence in this venv is correct, not a leak. Asserting
# them absent would now fail on a legitimate, deliberate dependency.
#
# Deliberately avoids editable installs (the Pitfall-2 warning sign — an editable
# install puts the repo source tree back on sys.path and defeats the whole test).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- 1. Build paaf-llm and its DECLARED framework deps into dist/ ---------------
# paaf-core and paaf-trace are workspace packages: they do not exist on PyPI, so
# pip can only satisfy paaf-llm's dependency on them from locally built wheels.
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

# --- 2. Fresh venv in a temp dir OUTSIDE the repo -------------------------------
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
# Fresh venv via the stdlib `python -m venv`. Prefer `python3` (always present on
# macOS/Linux); fall back to an unversioned `python` on minimal CI images.
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
"$PY" -m venv "$CLEAN_DIR/venv"
VENV_PY="$CLEAN_DIR/venv/bin/python"

# --- 3. Install the built wheels (plus pytest to run the smoke tests) -----------
# NOTE the absent `[engine]` extra: langchain is deliberately NOT installed, so
# the smoke suite below runs framework-uninstalled (SC#1).
echo "==> Installing wheels into clean venv (no [engine] extra => no langchain)"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet "${WHEEL_PATHS[@]}" pytest

# --- 4. Import + version from OUTSIDE the repo (cwd = temp dir) ------------------
echo "==> Importing paaf_llm from the installed wheel (cwd outside repo)"
cd "$CLEAN_DIR"
"$VENV_PY" -c "import paaf_llm; print('paaf_llm', paaf_llm.__version__)"

# --- 5. Run the smoke suite against the INSTALLED package, not the source tree ---
echo "==> Running smoke tests via pytest --pyargs paaf_llm"
"$VENV_PY" -m pytest --pyargs paaf_llm -q

# --- 6. Negative control: forbidden packages must NOT be importable -------------
# paaf_voice: paaf-llm must never couple to the voice half (FOUND-02).
# langchain:  the agent framework lives behind the optional [engine] extra, so a
#             base install must not carry it (SC#1 / MODEL-08 / Pitfall 4).
# paaf_core / paaf_trace are deliberately ABSENT from this set: they are declared
# dependencies as of Phase 3, so their presence is correct rather than a leak.
echo "==> Asserting paaf_voice and langchain are NOT importable in the clean venv"
"$VENV_PY" - <<'PYEOF'
import sys

leaked = []
for name in ("paaf_voice", "langchain"):
    try:
        __import__(name)
        leaked.append(name)
    except ModuleNotFoundError:
        print(f"ok: {name} is not importable (as required)")

# Positive control: the declared deps MUST be here, otherwise the negative
# control above could "pass" simply because nothing at all got installed.
for name in ("paaf_llm", "paaf_core", "paaf_trace"):
    __import__(name)
    print(f"ok: {name} is importable (declared dependency)")

if leaked:
    print(
        "FAIL: the following packages leaked into the paaf-llm wheel's "
        f"environment: {leaked}. paaf-llm gained either a coupling to voice or "
        "a hard dependency on the agent framework (RESEARCH Pitfall 2 / 4).",
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF

echo "==> PASS: paaf-llm installs with its framework deps (paaf-core, paaf-trace)"
echo "==>       but WITHOUT the agent framework (langchain) or paaf-voice"
