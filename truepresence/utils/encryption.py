"""
Encryption utilities for sensitive data at rest.
Uses Fernet (symmetric encryption) from cryptography library.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Environment variable for encryption key (32-byte base64-encoded Fernet key)
ENCRYPTION_KEY_ENV = "TRUEPRESENCE_ENCRYPTION_KEY"


def _get_encryption_key() -> bytes:
    """Derive or retrieve the encryption key."""
    key = os.environ.get(ENCRYPTION_KEY_ENV)
    if not key:
        raise RuntimeError(
            f"{ENCRYPTION_KEY_ENV} is required for encrypting sensitive data. "
            "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return base64.b64decode(key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, return base64-encoded ciphertext."""
    if not plaintext:
        return plaintext
    key = _get_encryption_key()
    f = Fernet(key)
    ciphertext = f.encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(ciphertext).decode("ascii")


def decrypt_value(ciphertext: Optional[str]) -> str:
    """Decrypt a base64-encoded ciphertext, return plaintext."""
    if not ciphertext:
        return ciphertext
    key = _get_encryption_key()
    f = Fernet(key)
    try:
        plaintext = f.decrypt(base64.b64decode(ciphertext))
        return plaintext.decode("utf-8")
    except Exception as exc:
        logger.error("Failed to decrypt value", exc_info=True)
        raise ValueError("Invalid encrypted value") from exc
