# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# FOUND-02 / SC#2 — prove the built paaf-llm wheel stands alone.
#
# This script builds the paaf-llm wheel, installs it into a FRESH venv created
# in a temp dir OUTSIDE the repo tree, and runs its smoke tests via
# `pytest --pyargs paaf_llm` from a cwd that is NOT the repo — so the repo's
# `src/` tree is never on sys.path and only the installed wheel is imported
# (RESEARCH Pitfall 2: "Clean-venv wheel job that isn't clean").
#
# Negative control (the load-bearing half): after installing ONLY the paaf-llm
# wheel, assert that `import paaf_voice` and `import paaf_core` both raise
# ModuleNotFoundError. If either import unexpectedly succeeds, a hidden
# dependency has leaked in and this script exits nonzero — flipping the CI job
# RED the instant paaf-llm gains an undeclared coupling.
#
# Deliberately avoids editable installs (the Pitfall-2 warning sign — an editable
# install puts the repo source tree back on sys.path and defeats the whole test).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- 1. Build the wheel (only paaf-llm) into dist/ ------------------------------
echo "==> Building paaf-llm wheel"
rm -f dist/paaf_llm-*.whl
uv build --package paaf-llm

WHEEL="$(ls dist/paaf_llm-*.whl | head -n1)"
if [[ -z "${WHEEL:-}" || ! -f "$WHEEL" ]]; then
  echo "FAIL: no paaf-llm wheel found in dist/ after build" >&2
  exit 1
fi
WHEEL_ABS="$REPO_ROOT/$WHEEL"
echo "==> Built $WHEEL"

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

# --- 3. Install ONLY the built wheel (plus pytest to run the smoke tests) -------
echo "==> Installing wheel into clean venv"
"$VENV_PY" -m pip install --quiet --upgrade pip
"$VENV_PY" -m pip install --quiet "$WHEEL_ABS" pytest

# --- 4. Import + version from OUTSIDE the repo (cwd = temp dir) ------------------
echo "==> Importing paaf_llm from the installed wheel (cwd outside repo)"
cd "$CLEAN_DIR"
"$VENV_PY" -c "import paaf_llm; print('paaf_llm', paaf_llm.__version__)"

# --- 5. Run the smoke suite against the INSTALLED package, not the source tree ---
echo "==> Running smoke tests via pytest --pyargs paaf_llm"
"$VENV_PY" -m pytest --pyargs paaf_llm -q

# --- 6. Negative control: forbidden packages must NOT be importable -------------
echo "==> Asserting paaf_voice and paaf_core are NOT importable in the clean venv"
"$VENV_PY" - <<'PYEOF'
import sys

leaked = []
for name in ("paaf_voice", "paaf_core"):
    try:
        __import__(name)
        leaked.append(name)
    except ModuleNotFoundError:
        print(f"ok: {name} is not importable (as required)")

if leaked:
    print(
        "FAIL: the following packages leaked into the paaf-llm wheel's "
        f"environment: {leaked}. paaf-llm gained an undeclared dependency "
        "(RESEARCH Pitfall 2).",
        file=sys.stderr,
    )
    sys.exit(1)
PYEOF

echo "==> PASS: paaf-llm wheel installs standalone and carries neither paaf_voice nor paaf_core"
