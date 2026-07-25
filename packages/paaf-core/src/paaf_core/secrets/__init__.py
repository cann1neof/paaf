# SPDX-License-Identifier: Apache-2.0
"""CORE-04: encrypted secret store — pluggable interface + Fernet backend.

Secrets live behind :class:`SecretStore`, encrypted at rest with audited pyca
``cryptography`` (Fernet + scrypt), never in the config YAML tree and never in a
log. The master key is derived from a passphrase at unlock (passphrase-at-boot).
"""
from __future__ import annotations

from paaf_core.secrets.fernet_backend import (
    EncryptedFileSecretStore,
    InvalidPassphraseError,
    derive_key,
)
from paaf_core.secrets.interface import SecretStore

__all__ = [
    "SecretStore",
    "EncryptedFileSecretStore",
    "InvalidPassphraseError",
    "derive_key",
]
