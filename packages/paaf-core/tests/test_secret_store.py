# SPDX-License-Identifier: Apache-2.0
"""CORE-04: encrypted secret store (Fernet + scrypt), passphrase-at-boot.

Task 1 proves the happy path: secrets round-trip through an audited Fernet
backend whose master key is derived from a passphrase at unlock time (scrypt
KDF over a persisted per-store salt), plaintext never lands in the file on
disk, and list_keys exposes names only. The passphrase itself is never at rest
(decision: passphrase-at-boot) — only the salt is.
"""
import base64
import json

import pytest
from paaf_core.secrets import EncryptedFileSecretStore, SecretStore, derive_key

PASSPHRASE = "correct horse battery staple"
SECRET_KEY = "openai_api_key"
SECRET_VALUE = "sk-super-secret-value-1234567890"


def _open(path, passphrase=PASSPHRASE):
    return EncryptedFileSecretStore(str(path), passphrase=passphrase)


def test_set_then_get_round_trips(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)
    assert store.get(SECRET_KEY) == SECRET_VALUE


def test_get_missing_returns_none(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    assert store.get("does-not-exist") is None


def test_delete_removes_secret(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)
    store.delete(SECRET_KEY)
    assert store.get(SECRET_KEY) is None


def test_list_keys_returns_names_only_never_values(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)
    keys = store.list_keys()
    assert keys == [SECRET_KEY]
    # the value must never leak through the key listing
    assert SECRET_VALUE not in keys
    assert all(SECRET_VALUE not in k for k in keys)


def test_persists_across_reopen(tmp_path):
    path = tmp_path / "secrets.enc"
    _open(path).set(SECRET_KEY, SECRET_VALUE)
    # a fresh instance with the same passphrase unlocks the same content
    assert _open(path).get(SECRET_KEY) == SECRET_VALUE


def test_encrypted_file_bytes_do_not_contain_plaintext(tmp_path):
    path = tmp_path / "secrets.enc"
    store = _open(path)
    store.set(SECRET_KEY, SECRET_VALUE)
    raw = path.read_bytes()
    # the plaintext value must be absent from the ciphertext at rest
    assert SECRET_VALUE.encode() not in raw
    # the passphrase is never persisted either (only the salt is)
    assert PASSPHRASE.encode() not in raw


def test_file_created_mode_0600(tmp_path):
    path = tmp_path / "secrets.enc"
    _open(path).set(SECRET_KEY, SECRET_VALUE)
    assert (path.stat().st_mode & 0o777) == 0o600


def test_repr_does_not_leak_values(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)
    # a caller cannot accidentally serialize the store into a log line
    assert SECRET_VALUE not in repr(store)
    assert SECRET_VALUE not in str(store)


def test_derive_key_is_deterministic_for_same_passphrase_and_salt():
    salt = b"\x00" * 16
    k1 = derive_key(b"pw", salt)
    k2 = derive_key(b"pw", salt)
    assert k1 == k2
    # Fernet requires a urlsafe-b64-encoded 32-byte key
    assert len(base64.urlsafe_b64decode(k1)) == 32


def test_derive_key_differs_with_different_salt():
    assert derive_key(b"pw", b"\x00" * 16) != derive_key(b"pw", b"\x01" * 16)


def test_store_satisfies_protocol(tmp_path):
    store = _open(tmp_path / "secrets.enc")
    assert isinstance(store, SecretStore)


def test_salt_is_persisted_in_plaintext_but_value_is_not(tmp_path):
    # the on-disk format keeps the salt readable (needed to re-derive the key)
    # while the secrets blob stays encrypted.
    path = tmp_path / "secrets.enc"
    store = _open(path)
    store.set(SECRET_KEY, SECRET_VALUE)
    payload = json.loads(path.read_text())
    assert "salt" in payload  # salt at rest is fine
    assert SECRET_VALUE not in json.dumps(payload)  # value is not
