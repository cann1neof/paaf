# SPDX-License-Identifier: Apache-2.0
"""CORE-04: Fernet-backed encrypted-file secret store (D-01/D-02).

Crypto is audited pyca ``cryptography`` only — Fernet (AES-128-CBC + HMAC-SHA256,
authenticated) for the payload and ``Scrypt`` for the KDF. No primitive is
assembled by hand: there is no ``hashlib``-based key stretching and no manual
cipher wiring. ``pyrage``/``age`` is the documented swappable alternative behind
the ``SecretStore`` interface — it would slot in without touching a caller.

Master-key provisioning source (decided at the plan checkpoint): **passphrase-at-boot**.
The Fernet key is derived from a caller-supplied passphrase via scrypt at unlock
time. Only a per-store salt is persisted at rest; the passphrase and the derived
key are NEVER written to disk. This is the strongest option — the key is never at
rest — at the documented cost that unattended headless restart needs the
passphrase re-supplied by an operator or an external secrets manager (Phase 9 /
APP-* owns boot-time delivery).
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# scrypt work factors (RFC 7914 interactive-login class): n=2**14, r=8, p=1.
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_KEY_LEN = 32
_SALT_LEN = 16


class InvalidPassphraseError(Exception):
    """Raised when a store cannot be unlocked with the supplied passphrase.

    A wrong passphrase must fail loudly here, never silently return garbage —
    Fernet's authenticated decryption is what makes this detectable.
    """


def derive_key(passphrase: bytes, salt: bytes) -> bytes:
    """Derive a urlsafe-b64-encoded 32-byte Fernet key from ``passphrase``.

    Deterministic for a given (passphrase, salt); a different salt yields a
    different key. Uses scrypt (n=2**14, r=8, p=1) from pyca ``cryptography``.
    """
    if isinstance(passphrase, str):  # tolerate str for ergonomic callers
        passphrase = passphrase.encode("utf-8")
    kdf = Scrypt(salt=salt, length=_KEY_LEN, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    raw = kdf.derive(passphrase)
    return base64.urlsafe_b64encode(raw)


class EncryptedFileSecretStore:
    """A ``SecretStore`` persisting a Fernet-encrypted ``{key: value}`` blob.

    On-disk format is a small JSON envelope ``{"salt": <b64>, "blob": <token>}``:
    the salt is plaintext (needed to re-derive the key), the blob is the Fernet
    token over the secrets JSON. The file is created ``0600``. The passphrase is
    accepted at construction (passphrase-at-boot) and only the derived key is
    held in memory — never persisted.
    """

    def __init__(self, path: str, passphrase: str | bytes) -> None:
        self._path = Path(path)
        if isinstance(passphrase, str):
            passphrase = passphrase.encode("utf-8")

        if self._path.exists():
            envelope = json.loads(self._path.read_text())
            salt = base64.b64decode(envelope["salt"])
            self._fernet = Fernet(derive_key(passphrase, salt))
            self._salt = salt
            try:
                self._data: dict[str, str] = json.loads(
                    self._fernet.decrypt(envelope["blob"].encode("ascii")).decode("utf-8")
                )
            except InvalidToken as exc:  # wrong passphrase / tampered file
                raise InvalidPassphraseError(
                    "could not unlock secret store with the supplied passphrase"
                ) from exc
        else:
            self._salt = os.urandom(_SALT_LEN)
            self._fernet = Fernet(derive_key(passphrase, self._salt))
            self._data = {}
            # Persist immediately so the salt is fixed and a wrong passphrase is
            # detectable on the next open even before any secret is set.
            self._flush()

    # --- SecretStore API -------------------------------------------------

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        self._flush()

    def get(self, key: str) -> str | None:
        return self._data.get(key)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._flush()

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    # --- persistence -----------------------------------------------------

    def _flush(self) -> None:
        blob = self._fernet.encrypt(json.dumps(self._data).encode("utf-8"))
        envelope = {
            "salt": base64.b64encode(self._salt).decode("ascii"),
            "blob": blob.decode("ascii"),
        }
        # Create with 0600 from the outset (no world-readable window), then write.
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, json.dumps(envelope).encode("utf-8"))
        finally:
            os.close(fd)
        # Enforce 0600 even if the file pre-existed with looser bits.
        os.chmod(self._path, 0o600)

    # --- leak guards -----------------------------------------------------

    def __repr__(self) -> str:  # never emit values into a log/repr
        return f"EncryptedFileSecretStore(path={self._path!s}, keys={len(self._data)})"

    __str__ = __repr__
