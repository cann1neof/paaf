# SPDX-License-Identifier: Apache-2.0
"""PAAF LLM management: model profiles, the chat port, and the shipped fake.

This is the whole public surface, and every name in :data:`__all__` is a PAAF
type. That is MODEL-08 stated as code rather than as a promise: a caller can
depend on this module without ever naming — or installing — the agent framework
underneath.

Two rules govern what may appear here:

* **PAAF types only.** ``tests/test_no_leak.py`` walks every public signature
  and fails if an annotation resolves to a framework module, so a leak is a red
  build rather than a review comment.
* **The adapter package is never imported here.** The real framework-backed
  adapter lives behind an optional ``[engine]`` extra and is imported LAZILY,
  only when it is actually constructed. Importing it from this module would make
  the framework a hard dependency of ``import paaf_llm`` and break the promise
  that ``pip install paaf-llm`` runs the fake-adapter suite standalone (SC#1).
"""

from __future__ import annotations

from .ports import (
    AdapterError,
    AllProvidersFailed,
    ChatAdapter,
    ConnectionFailed,
    FallbackReason,
    Message,
    RateLimited,
    RequestTimedOut,
    Role,
    ServerError,
    TurnResult,
    Usage,
)
from .profiles import LlmConfig, ModelProfile

__version__ = "0.1.0"

__all__ = [
    "AdapterError",
    "AllProvidersFailed",
    "ChatAdapter",
    "ConnectionFailed",
    "FallbackReason",
    "LlmConfig",
    "Message",
    "ModelProfile",
    "RateLimited",
    "RequestTimedOut",
    "Role",
    "ServerError",
    "TurnResult",
    "Usage",
]
