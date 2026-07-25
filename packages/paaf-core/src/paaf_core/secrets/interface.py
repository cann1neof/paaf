# SPDX-License-Identifier: Apache-2.0
"""CORE-04: the pluggable ``SecretStore`` contract (D-04).

Secrets live behind this interface, never in the Pydantic ``AppConfig`` tree and
never in a log line. The Fernet-backed file store is the v1 implementation, but
the interface is the durable contract: an ``age``/``pyrage`` backend, a
``key-file-0600`` master-key source, or a ``systemd-credential`` source can all
be added later without changing a single caller.

``list_keys`` returns NAMES only — a value must never be reachable through the
listing API.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretStore(Protocol):
    """A write-only-over-the-API, encrypted-at-rest secret store.

    Implementations MUST NOT expose secret values through ``__repr__``/``__str__``
    or through ``list_keys`` — only key names are observable without an explicit
    ``get``.
    """

    def set(self, key: str, value: str) -> None:
        """Store ``value`` under ``key`` (overwriting any existing value)."""
        ...

    def get(self, key: str) -> str | None:
        """Return the value for ``key``, or ``None`` if it is not present."""
        ...

    def delete(self, key: str) -> None:
        """Remove ``key`` if present; a no-op when it is absent."""
        ...

    def list_keys(self) -> list[str]:
        """Return the stored key NAMES only — never their values."""
        ...
