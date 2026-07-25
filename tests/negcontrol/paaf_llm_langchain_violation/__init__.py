# SPDX-License-Identifier: Apache-2.0
"""DELIBERATE VIOLATION fixture — do NOT import this at runtime.

This package exists ONLY so import-linter can prove the `langchain-confined-to-adapter`
forbidden contract actually fails when a framework module imports langchain from
OUTSIDE the paaf_llm._engine adapter subpackage. It lives outside packages/ so the
real `.importlinter` stays green. It is never executed (static AST analysis only, so
langchain need not be installed); the paired test asserts this import turns the
contract RED.
"""

import langchain  # noqa: F401  — langchain escaping the _engine adapter; must fail CI
