# SPDX-License-Identifier: Apache-2.0
"""DELIBERATE VIOLATION fixture — do NOT import this at runtime.

This package exists ONLY so import-linter can prove the `voice-and-llm-are-independent`
independence contract actually fails on a real paaf_voice->paaf_llm edge. It lives
OUTSIDE packages/ so the real `.importlinter` never sees it and stays green. It is
never executed (import-linter is static AST analysis); the paired test in
tests/negcontrol/test_import_boundary.py runs lint-imports against
.importlinter-negcontrol and asserts this edge turns the contract RED.
"""

import paaf_llm  # noqa: F401  — the forbidden voice->llm coupling this fixture proves is caught
