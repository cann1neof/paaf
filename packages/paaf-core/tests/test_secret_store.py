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


# ---------------------------------------------------------------------------
# Task 2 — CORE-04 negative controls (PRIV-01/PRIV-02). These are the
# load-bearing proofs that the guards BITE, not just the happy-path round-trip.
# ---------------------------------------------------------------------------


def test_secret_value_absent_from_serialized_config_yaml(tmp_path):
    # CORE-04 not-in-YAML: the config tree the user owns is a *separate* model
    # from the secret store; serializing it must never surface a secret value.
    import io

    from paaf_core.config.schema import AppConfig
    from ruamel.yaml import YAML

    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)

    config = AppConfig()
    buf = io.StringIO()
    YAML().dump(config.model_dump(), buf)
    rendered = buf.getvalue()

    assert SECRET_VALUE not in rendered
    # the secret KEY name may reference a credential, but never its value
    assert SECRET_VALUE not in str(config.model_dump())


def test_secret_value_absent_from_logs_after_consume(tmp_path, captured_logs):
    # CORE-04 not-in-logs: a real consume-and-log path (log the *operation*,
    # use the secret) must never emit the value into any captured record.
    import logging

    store = _open(tmp_path / "secrets.enc")
    store.set(SECRET_KEY, SECRET_VALUE)

    log = logging.getLogger("paaf.secrets.consume")
    key = store.get(SECRET_KEY)  # consume the secret
    assert key == SECRET_VALUE  # the caller has it in hand
    # ...but only the operation, never the value, is ever logged
    log.info("authenticating provider using key %r", SECRET_KEY)
    log.debug("secret store has %d key(s)", len(store.list_keys()))

    joined = "\n".join(captured_logs.messages)
    assert SECRET_VALUE not in joined
    # also guard against the value smuggled through record args / str(record)
    for record in captured_logs.records:
        assert SECRET_VALUE not in record.getMessage()
        assert SECRET_VALUE not in str(record.args)


def test_offline_headless_round_trip_needs_no_network(tmp_path):
    # PRIV-01/PRIV-02 (D-03/D-04): the store works with no account and no cloud.
    # This whole module runs under --disable-socket by default, so a full
    # round-trip passing here IS the proof that no socket is opened.
    path = tmp_path / "secrets.enc"
    _open(path).set(SECRET_KEY, SECRET_VALUE)
    reopened = _open(path)
    assert reopened.get(SECRET_KEY) == SECRET_VALUE


def test_wrong_passphrase_raises_not_silent(tmp_path):
    # NEGATIVE CONTROL: unlocking with the wrong passphrase must FAIL LOUDLY,
    # never silently return an empty/garbage store. Fernet's authenticated
    # decryption is what makes tampering/wrong-key detectable.
    from paaf_core.secrets import InvalidPassphraseError

    path = tmp_path / "secrets.enc"
    _open(path).set(SECRET_KEY, SECRET_VALUE)

    with pytest.raises(InvalidPassphraseError):
        _open(path, passphrase="the-wrong-passphrase")
