#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Clean-venv release verification script (OSS-01 / T-06-07).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== Building PAAF packages ==="
cd "${REPO_ROOT}"
uv build --package paaf-core
uv build --package paaf-trace
uv build --package paaf-llm
uv build --package paaf

TMP_VENV=$(mktemp -d "/tmp/paaf_venv_check_XXXXXX")
trap 'rm -rf "${TMP_VENV}"' EXIT

echo "=== Creating clean virtualenv in ${TMP_VENV} ==="
python3 -m venv "${TMP_VENV}"
source "${TMP_VENV}/bin/activate"

echo "=== Installing built wheels into clean virtualenv ==="
pip install --quiet "${REPO_ROOT}/dist"/paaf_core-*.whl
pip install --quiet "${REPO_ROOT}/dist"/paaf_trace-*.whl
pip install --quiet "${REPO_ROOT}/dist"/paaf_llm-*.whl
pip install --quiet "${REPO_ROOT}/dist"/paaf-*.whl

echo "=== Running CLI smoke tests in isolated directory ==="
TEST_WORK_DIR=$(mktemp -d "/tmp/paaf_test_work_XXXXXX")
trap 'rm -rf "${TMP_VENV}" "${TEST_WORK_DIR}"' EXIT

cd "${TEST_WORK_DIR}"

paaf --help > /dev/null
echo "✓ paaf --help passed"

cat << 'EOF' > paaf.yaml
active_profile: cloud
profiles:
  cloud:
    provider: ollama
    model: llama3.1
EOF

paaf prompt --config paaf.yaml > /dev/null
echo "✓ paaf prompt passed"

paaf skill list > /dev/null
echo "✓ paaf skill list passed"

echo "=== All release venv smoke tests passed cleanly ==="
