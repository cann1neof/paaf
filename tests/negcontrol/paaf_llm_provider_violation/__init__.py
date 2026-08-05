# SPDX-License-Identifier: Apache-2.0
"""DELIBERATE VIOLATION fixture — do NOT import this at runtime.

Sibling of ``paaf_llm_langchain_violation``, aimed at the PROVIDER half of the
`langchain-confined-to-adapter` contract. Phase 2 forbade `langchain`/`langgraph`/
`langchain_core`/`langchain_mcp_adapters` but NOT the provider bindings
(`langchain_ollama`/`langchain_anthropic`/`langchain_openai`), so until Phase 3 those
could be imported anywhere in the framework and leak the agent framework's types
silently. This package exists ONLY so import-linter can prove the extended contract
actually fails when a provider binding is imported from OUTSIDE the
``paaf_llm._engine`` adapter subpackage.

It lives outside packages/ so the real `.importlinter` stays green. It is never
executed (import-linter is static AST analysis, so langchain-ollama need not be
installed); the paired test asserts this import turns the contract RED.
"""

import langchain_ollama  # noqa: F401  — provider escaping the _engine adapter; must fail CI
