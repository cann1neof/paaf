# SPDX-License-Identifier: Apache-2.0
"""DELIBERATE VIOLATION fixture — do NOT import this at runtime.

This package exists ONLY so import-linter can prove the `no-network-client-in-framework`
forbidden contract actually fails when a framework module pulls in an outbound HTTP
client. It lives outside packages/ so the real `.importlinter` stays green. It is never
executed (static AST analysis only, so httpx need not be installed); the paired test
asserts this import turns the contract RED — the architectural guard behind TRACE-05.
"""

import httpx  # noqa: F401  — an egress client entering the framework graph; must fail CI
